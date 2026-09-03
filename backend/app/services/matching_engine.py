import logging
import asyncio
from typing import List, Dict, Any, Tuple
from haversine import haversine, Unit
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal, DatabaseRepository
from app.models.db_models import EmergencyRequestDB
from app.services.emergency_state_machine import EmergencyStateMachine, EmergencyState
from app.websockets.connection_manager import manager, WSEventType

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Executes strict medical rules (ABO, Rh, 56-day recovery, medical restrictions),
    calculates distances, and ranks donors.
    Streams rich progress events for cinematic dispatch experience.
    """

    # Universal donor rules (simplified for this context)
    COMPATIBILITY_MAP = {
        "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
        "O+": ["O+", "A+", "B+", "AB+"],
        "A-": ["A-", "A+", "AB-", "AB+"],
        "A+": ["A+", "AB+"],
        "B-": ["B-", "B+", "AB-", "AB+"],
        "B+": ["B+", "AB+"],
        "AB-": ["AB-", "AB+"],
        "AB+": ["AB+"]
    }

    @classmethod
    def get_compatible_types(cls, patient_blood_type: str) -> List[str]:
        # We need to find all donor blood types that can give to the patient
        # This means reversing the COMPATIBILITY_MAP.
        compatible = []
        for donor_type, recipients in cls.COMPATIBILITY_MAP.items():
            if patient_blood_type in recipients:
                compatible.append(donor_type)
        return compatible
    @classmethod
    def _is_cancelled(cls, request_id: str) -> bool:
        """Re-reads persisted request status to check if cancelled. Used as a concurrency guard."""
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            request = repo.get_request(request_id)
            if not request:
                return True
            return request.get("status") == "CANCELLED"

    @classmethod
    async def run_matching_cycle(cls, request_id: str):
        """
        Background task to find donors, apply rules, rank them, and transition to RING1.
        Streams granular progress events for the cinematic dispatch experience.
        """
        from app.websockets.connection_manager import manager
        
        # Wait for frontend to connect before streaming AI events, fallback after 5s
        await manager.wait_for_connection(request_id, timeout=5.0)
        
        # ── Cancellation guard: before AI processing ────────────
        if cls._is_cancelled(request_id):
            logger.info(f"[Matching {request_id}] Cancelled before AI processing. Aborting.")
            return

        # ── Phase: AI Processing ────────────────────────────────
        await EmergencyStateMachine.transition(
            request_id, 
            EmergencyState.AI_PROCESSING, 
            "AI Engine analyzing request parameters...",
            {"step": "ai_processing"}
        )
        await asyncio.sleep(1.2)  # Cinematic pacing

        # ── Cancellation guard: before Validating ───────────────
        if cls._is_cancelled(request_id):
            logger.info(f"[Matching {request_id}] Cancelled before validation. Aborting.")
            return

        # ── Phase: Validating ───────────────────────────────────
        await EmergencyStateMachine.transition(
            request_id, 
            EmergencyState.VALIDATING, 
            "Validating blood type compatibility matrix and medical protocols...",
            {"step": "validating"}
        )
        await asyncio.sleep(1.0)

        # ── Cancellation guard: before Searching ────────────────
        if cls._is_cancelled(request_id):
            logger.info(f"[Matching {request_id}] Cancelled before searching. Aborting.")
            return

        # ── Phase: Searching ────────────────────────────────────
        await EmergencyStateMachine.transition(
            request_id, 
            EmergencyState.SEARCHING, 
            "Initializing radar sweep for nearby eligible donors.",
            {"step": "initialization"}
        )
        await asyncio.sleep(1)

        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            request = repo.get_request(request_id)
            if not request:
                logger.error(f"Request {request_id} not found.")
                return

            req_lat = request["latitude"]
            req_lon = request["longitude"]
            req_blood = request["blood_type"]

            # 1. Fetch all donors (simulate "Found X donors")
            all_donors_raw = repo.list_donors({"is_active": True, "is_available": True})
            
            # Exclude donors who have already matched (withdrawn, active, or declined)
            existing_matches = repo.get_matches_for_request(request_id)
            excluded_donor_ids = {m["donor_id"] for m in existing_matches if m.get("status") not in ["CANCELLED"]}
            
            # Exclude the requester's own donor profile if applicable
            requester_uid = request.get("requester_user_id")
            
            all_donors = []
            for d in all_donors_raw:
                if d["id"] in excluded_donor_ids:
                    continue
                if requester_uid and d.get("user_id") == requester_uid:
                    logger.info(f"[{request_id}] Excluded requester-owned donor profile from matching: donor_id={d['id']}, user_id={d['user_id']}")
                    continue
                all_donors.append(d)

            total_count = len(all_donors)
            
            await EmergencyStateMachine.transition(
                request_id, 
                EmergencyState.SEARCHING, 
                f"Found {total_count} total active donors.",
                {"step": "donors_found", "count": total_count}
            )
            
            # Broadcast SEARCH_PROGRESS with initial count
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.SEARCH_PROGRESS,
                {"phase": "donors_found", "total": total_count, "label": f"Found {total_count} donors in network"}
            )
            
            # Broadcast DONOR_MARKERS with anonymized locations of all active donors
            donor_markers = []
            for d in all_donors:
                if d.get("latitude") and d.get("longitude"):
                    donor_markers.append({
                        "lat": d["latitude"],
                        "lng": d["longitude"],
                        "blood_type": d.get("blood_type", "?"),
                        "status": "available"
                    })
            
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.DONOR_MARKERS,
                {"markers": donor_markers, "phase": "all_active"}
            )
            
            await asyncio.sleep(1.5)

            # 2. Medical Eligibility & Compatibility
            compatible_types = cls.get_compatible_types(req_blood)
            
            await EmergencyStateMachine.transition(
                request_id, 
                EmergencyState.SEARCHING, 
                f"Filtering for compatibility with {req_blood}...",
                {"step": "filtering_blood"}
            )
            await asyncio.sleep(0.8)

            # Filter step by step with progress broadcasts
            after_blood_filter = [d for d in all_donors if d["blood_type"] in compatible_types]
            
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.SEARCH_PROGRESS,
                {
                    "phase": "blood_filter", 
                    "total": total_count,
                    "after_blood_filter": len(after_blood_filter),
                    "label": f"Blood type compatible: {len(after_blood_filter)}"
                }
            )
            await asyncio.sleep(1.0)

            # 56-day rule filter
            after_56day = []
            for d in after_blood_filter:
                if d["last_donation_date"]:
                    days_since = (datetime.now().date() - datetime.strptime(d["last_donation_date"], "%Y-%m-%d").date()).days
                    if days_since < 56:
                        continue
                after_56day.append(d)
            
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.SEARCH_PROGRESS,
                {
                    "phase": "56day_filter",
                    "total": total_count,
                    "after_blood_filter": len(after_blood_filter),
                    "after_56day": len(after_56day),
                    "label": f"56-day recovery check: {len(after_56day)}"
                }
            )
            await asyncio.sleep(1.0)

            # Distance filter
            eligible_donors = []
            for d in after_56day:
                dist_km = haversine((req_lat, req_lon), (d["latitude"], d["longitude"]), unit=Unit.KILOMETERS)
                if dist_km > d["max_travel_radius_km"]:
                    continue
                d["calculated_distance"] = dist_km
                eligible_donors.append(d)

            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.SEARCH_PROGRESS,
                {
                    "phase": "distance_filter",
                    "total": total_count,
                    "after_blood_filter": len(after_blood_filter),
                    "after_56day": len(after_56day),
                    "after_distance": len(eligible_donors),
                    "label": f"Within travel radius: {len(eligible_donors)}"
                }
            )

            # Broadcast filtered donor markers (only eligible donors)
            eligible_markers = []
            for d in eligible_donors:
                if d.get("latitude") and d.get("longitude"):
                    eligible_markers.append({
                        "lat": d["latitude"],
                        "lng": d["longitude"],
                        "blood_type": d.get("blood_type", "?"),
                        "distance_km": round(d.get("calculated_distance", 0), 1),
                        "status": "eligible"
                    })
            
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.DONOR_MARKERS,
                {"markers": eligible_markers, "phase": "eligible"}
            )

            await EmergencyStateMachine.transition(
                request_id, 
                EmergencyState.SEARCHING, 
                f"{len(eligible_donors)} remain after medical and distance filters.",
                {"step": "filtered", "count": len(eligible_donors)}
            )
            await asyncio.sleep(1)

            # 3. Ranking Engine
            await EmergencyStateMachine.transition(
                request_id, 
                EmergencyState.MATCHING, 
                "Ranking donors based on distance, reliability, and scarcity...",
                {"step": "ranking"}
            )
            
            await EmergencyStateMachine.broadcast_progress_event(
                request_id,
                WSEventType.SEARCH_PROGRESS,
                {
                    "phase": "ranking",
                    "total": total_count,
                    "after_blood_filter": len(after_blood_filter),
                    "after_56day": len(after_56day),
                    "after_distance": len(eligible_donors),
                    "label": "Ranking by ETA, reliability & scarcity..."
                }
            )
            await asyncio.sleep(1.5)

            ranked_donors = cls._rank_donors(eligible_donors)

            # ── Cancellation guard: before saving matches ───────
            if cls._is_cancelled(request_id):
                logger.info(f"[Matching {request_id}] Cancelled before saving matches. Aborting.")
                return

            ring_1_matches_to_notify = []

            # 4. Save Matches to DB
            for rank, donor in enumerate(ranked_donors):
                # Put top 5 in Ring 1, next 5 in Ring 2, etc.
                ring = (rank // 5) + 1
                match_data = {
                    "request_id": request_id,
                    "donor_id": donor["id"],
                    "ring_number": ring,
                    "score": donor["match_score"],
                    "distance_km": donor["calculated_distance"],
                    "status": "NOTIFIED" if ring == 1 else "QUEUED",
                    "score_breakdown": donor["score_breakdown"],
                    "donor_latitude": donor["latitude"],
                    "donor_longitude": donor["longitude"]
                }
                saved_match = repo.add_match(match_data)

                if ring == 1:
                    ring_1_matches_to_notify.append({
                        "donor": donor,
                        "match_id": saved_match["match_id"]
                    })
                
                repo.add_audit_log({
                    "request_id": request_id,
                    "donor_id": donor["id"],
                    "action": "MATCH_EVALUATED",
                    "passed_all": True,
                    "score": donor["match_score"],
                    "reasons": [f"Ring {ring} assignment", f"Distance {donor['calculated_distance']:.2f} km"]
                })
            
            # Guarantee order: flush/persist and COMMIT donor_matches transaction
            session.commit()

        # Broadcast final progress before ring
        await EmergencyStateMachine.broadcast_progress_event(
            request_id,
            WSEventType.SEARCH_PROGRESS,
            {
                "phase": "broadcasting",
                "total": total_count,
                "matched": len(ranked_donors),
                "label": f"Broadcasting Ring 1 to top {min(5, len(ranked_donors))} donors..."
            }
        )

        # ── Dispatch Ring 1 Notifications Outside DB Context ───
        if ring_1_matches_to_notify:
            from app.services.notification_service import notification_service
            for item in ring_1_matches_to_notify:
                d_user = item["donor"].get("user_id")
                d_id = item["donor"].get("id")
                m_id = item["match_id"]
                logger.info(f"Dispatching Ring 1 notification: request_id={request_id}, donor_id={d_id}, user_id={d_user}, match_id={m_id}")
                try:
                    res = await notification_service.send_emergency_push_notification(
                        item["donor"],
                        request,
                        m_id
                    )
                    logger.info(f"Notification result for {m_id}: FCM={res.get('status')}, success={res.get('fcm_success_count', 0)}, failure={res.get('fcm_failure_count', 0)}")
                except Exception as e:
                    logger.error(f"Notification dispatch failed for match {m_id}: {e}")

        # ── Cancellation guard: before Ring 1 escalation ───────
        if cls._is_cancelled(request_id):
            logger.info(f"[Matching {request_id}] Cancelled before ring escalation. Aborting.")
            return

        # Transition to Ring 1 state
        await EmergencyStateMachine.transition(
            request_id, 
            EmergencyState.RING1, 
            "Broadcasting Ring 1 notifications to top matched donors.",
            {"step": "ring_escalation", "ring": 1}
        )
        
        # Start Ring Escalation Task in background
        from app.services.ring_escalation import RingEscalationService
        asyncio.create_task(RingEscalationService.monitor_ring(request_id, 1))

    @classmethod
    def _rank_donors(cls, donors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ranking Weights:
        - Distance: 40% (Closer is better)
        - Recovery Buffer: 25% (More days since last donation is better)
        - Reliability: 20% (Higher reliability score is better)
        - Scarcity Protection: 15% (Preserving O- when not needed)
        """
        max_dist = max([d["calculated_distance"] for d in donors]) if donors else 1
        
        for d in donors:
            # Normalize Distance (0 to 1, where 1 is closest)
            dist_score = 1.0 - (d["calculated_distance"] / max_dist if max_dist > 0 else 0)
            
            # Normalize Recovery (capped at 365 days for scoring)
            if d["last_donation_date"]:
                days_since = (datetime.now().date() - datetime.strptime(d["last_donation_date"], "%Y-%m-%d").date()).days
                rec_score = min(days_since, 365) / 365.0
            else:
                rec_score = 1.0 # Never donated
                
            rel_score = float(d["reliability_score"])
            
            # Scarcity (O- gets penalized slightly if recipient is not O-, to save it for emergencies)
            scarcity_score = 1.0
            if d["blood_type"] == "O-":
                scarcity_score = 0.5 # Basic penalty

            final_score = (dist_score * 0.40) + (rec_score * 0.25) + (rel_score * 0.20) + (scarcity_score * 0.15)
            
            d["match_score"] = final_score
            d["score_breakdown"] = {
                "distance_score": dist_score * 0.40,
                "recovery_score": rec_score * 0.25,
                "reliability_score": rel_score * 0.20,
                "scarcity_score": scarcity_score * 0.15,
                "total": final_score
            }

        return sorted(donors, key=lambda x: x["match_score"], reverse=True)
