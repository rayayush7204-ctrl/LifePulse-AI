"""
Audit Logger for Life-Critical Blood Donor Matching Decisions.
Provides full accountability & transparency for medical hard-filtering and weighted ranking decisions.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import json
import logging
from app.database import DatabaseRepository

logger = logging.getLogger("audit_logger")

class AuditLogger:
    @staticmethod
    def record_match_audit(
        repo: DatabaseRepository,
        request: Dict[str, Any],
        match_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Creates an unalterable audit log entry containing:
        - Request details & timestamp
        - Total donors evaluated vs eligible
        - Hard filter reasons for every donor (pass & fail)
        - Scoring weights and exact subscore breakdown for ranked candidates
        """
        now_utc = datetime.now(timezone.utc)
        audit_entry = {
            "audit_id": f"audit-{request.get('id')}-{int(now_utc.timestamp())}",
            "request_id": request.get("id"),
            "timestamp": now_utc.isoformat(),
            "request_snapshot": {
                "blood_type": request.get("blood_type"),
                "units_needed": request.get("units_needed"),
                "hospital_name": request.get("hospital_name"),
                "urgency_level": request.get("urgency_level"),
                "latitude": request.get("latitude"),
                "longitude": request.get("longitude")
            },
            "matching_results": {
                "search_radius_km": match_summary.get("search_radius_km"),
                "total_donors_evaluated": match_summary.get("total_donors_evaluated"),
                "eligible_donors_count": match_summary.get("eligible_donors_count"),
                "ranked_candidates_summary": [
                    {
                        "donor_id": c["donor"].get("id"),
                        "donor_name": c["donor"].get("name"),
                        "blood_type": c["donor"].get("blood_type"),
                        "final_score": c["score"],
                        "distance_km": c["distance_km"],
                        "ring": c.get("ring", 1),
                        "score_subscores": c["score_breakdown"]["subscores"]
                    }
                    for c in match_summary.get("ranked_candidates", [])
                ]
            },
            "hard_filter_evaluations": match_summary.get("audit_log", {}).get("evaluations", [])
        }
        
        # Persist to database
        repo.add_audit_log(audit_entry)
        logger.info(f"[AUDIT LOGGED] Audit {audit_entry['audit_id']} saved for request {request.get('id')}")
        return audit_entry

audit_logger = AuditLogger()
