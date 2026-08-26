"""
Escalation Engine for Emergency Donor Matching.
Handles ring timeout escalation, radius expansion, voice call outreach, and blood bank fallback.
Operates strictly on real persistent database records.
"""

from typing import Dict, Any, List
import asyncio
import logging
from datetime import datetime, timezone
from app.database import DatabaseRepository
from app.matching.engine import MatchingEngine
from app.matching.hard_filters import calculate_haversine_distance_km, calculate_bounding_box
from app.services.notification_service import notification_service
from app.services.audit_logger import audit_logger

logger = logging.getLogger("escalation_engine")

class EscalationEngine:
    def __init__(self):
        self.matching_engine = MatchingEngine()

    async def execute_request_matching_and_fanout(
        self,
        repo: DatabaseRepository,
        request: Dict[str, Any],
        initial_radius_km: float = 25.0
    ) -> Dict[str, Any]:
        """
        Executes matching engine for request, saves matches in persistent DB, logs audit,
        and fans out Ring 1 notifications to real registered donors.
        """
        req_id = request["id"]
        req_lat = request["latitude"]
        req_lon = request["longitude"]
        
        # O(N) Optimization: SQL-level bounding box filter before fetching into Python
        bbox = calculate_bounding_box(req_lat, req_lon, initial_radius_km)
        donor_pool = repo.list_donors(bbox=bbox)
        
        # 1. Run deterministic matching engine on real database donors
        match_summary = self.matching_engine.match_donors(
            request=request,
            donor_pool=donor_pool,
            search_radius_km=initial_radius_km,
            ring_size=5
        )

        # 2. Record full audit log
        audit_logger.record_match_audit(repo, request, match_summary)

        ranked = match_summary["ranked_candidates"]
        if not ranked:
            # If no eligible registered donors found in radius, surface blood bank fallback
            fallback_banks = self.find_nearby_blood_banks(repo, request)
            repo.update_request_status(req_id, "NO_DONORS_FOUND")
            return {
                "request_id": req_id,
                "status": "NO_DONORS_FOUND",
                "notified_count": 0,
                "blood_bank_fallbacks": fallback_banks,
                "matched_candidates": []
            }

        # 3. Create match records in persistent database
        ring1_matches = []
        for candidate in ranked:
            donor = candidate["donor"]
            match_rec = {
                "match_id": f"match-{req_id[:6]}-{donor['id'][:6]}",
                "request_id": req_id,
                "donor_id": donor["id"],
                "donor_name": donor["name"],
                "donor_phone": donor["phone"],
                "donor_blood_type": donor["blood_type"],
                "ring_number": candidate["ring"],
                "score": candidate["score"],
                "distance_km": candidate["distance_km"],
                "status": "NOTIFIED",
                "score_breakdown": candidate["score_breakdown"],
                "donor_latitude": donor["latitude"],
                "donor_longitude": donor["longitude"],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            repo.add_match(match_rec)
            candidate["match_id"] = match_rec["match_id"]
            
            if candidate["ring"] == 1:
                ring1_matches.append(candidate)

        # 4. Update request status to MATCHING
        repo.update_request_status(req_id, "MATCHING")

        # 5. Fan-out Ring 1 notifications
        await notification_service.fan_out_notifications(ring1_matches, request)

        return {
            "request_id": req_id,
            "status": "MATCHING",
            "eligible_count": len(ranked),
            "ring_1_notified_count": len(ring1_matches),
            "matched_candidates": ranked,
            "blood_bank_fallbacks": self.find_nearby_blood_banks(repo, request)
        }

    async def check_and_escalate_ring(self, repo: DatabaseRepository, req_id: str) -> Dict[str, Any]:
        """
        Escalates matching ring if accepted donors < units_needed.
        Fires Ring 2 notifications and triggers voice call fallback for unresponsive Ring 1 donors.
        """
        request = repo.get_request(req_id)
        if not request or request["status"] in ("FULFILLED", "CANCELLED"):
            return {"status": "NO_ACTION_REQUIRED"}

        all_matches = repo.get_matches_for_request(req_id)
        accepted = [m for m in all_matches if m["status"] in ("ACCEPTED", "EN_ROUTE", "ARRIVED")]
        units_needed = request.get("units_needed", 1)

        if len(accepted) >= units_needed:
            repo.update_request_status(req_id, "FULFILLED")
            return {"status": "FULFILLED", "accepted_count": len(accepted)}

        ring2_matches = [m for m in all_matches if m["ring_number"] == 2 and m["status"] == "NOTIFIED"]
        unresponsive_ring1 = [m for m in all_matches if m["ring_number"] == 1 and m["status"] == "NOTIFIED"]

        for m in unresponsive_ring1:
            donor = repo.get_donor(m["donor_id"])
            if donor:
                await notification_service.trigger_exotel_voice_call(donor, request, m["match_id"])

        for m in ring2_matches:
            donor = repo.get_donor(m["donor_id"])
            if donor:
                cand = {"donor": donor, "match_id": m["match_id"]}
                await notification_service.fan_out_notifications([cand], request)

        fallback_banks = self.find_nearby_blood_banks(repo, request)

        return {
            "status": "ESCALATED_RING_2",
            "ring_2_notified_count": len(ring2_matches),
            "voice_calls_triggered": len(unresponsive_ring1),
            "blood_bank_fallbacks": fallback_banks
        }

    def find_nearby_blood_banks(self, repo: DatabaseRepository, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Finds nearest blood banks with available stock of the requested blood group.
        """
        req_lat = request["latitude"]
        req_lon = request["longitude"]
        req_bt = request.get("blood_type", "O-")
        
        # Pre-filter hospitals within a reasonable radius (e.g., 100km max for a fallback)
        bbox = calculate_bounding_box(req_lat, req_lon, 100.0)
        all_banks = repo.list_hospitals(bbox=bbox)
        results = []

        for bank in all_banks:
            dist = round(calculate_haversine_distance_km(req_lat, req_lon, bank["latitude"], bank["longitude"]), 2)
            inventory = bank.get("inventory", {})
            stock = inventory.get(req_bt, 0)
            
            results.append({
                "id": bank["id"],
                "name": bank["name"],
                "phone": bank["phone"],
                "address": bank["address"],
                "distance_km": dist,
                "stock_available": stock,
                "inventory": inventory,
                "latitude": bank["latitude"],
                "longitude": bank["longitude"]
            })

        results.sort(key=lambda x: x["distance_km"])
        return results

escalation_engine = EscalationEngine()
