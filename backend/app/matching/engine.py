"""
Main Matching Engine Orchestrator.
Combines hard filters, medical pre-screening rules, nearest-first ranking, multi-ring allocation, and audit logging.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timezone
from app.matching.hard_filters import evaluate_hard_filters, calculate_haversine_distance_km
from app.matching.scorer import calculate_donor_score, DEFAULT_SCORING_WEIGHTS

class MatchingEngine:
    """
    Deterministic & explainable blood donor matching engine.
    Applies hard medical rules, distance calculations, and ranks nearest-to-farthest.
    """
    
    def __init__(self, scoring_weights: Optional[Dict[str, float]] = None):
        self.weights = scoring_weights or DEFAULT_SCORING_WEIGHTS

    def match_donors(
        self,
        request: Dict[str, Any],
        donor_pool: List[Dict[str, Any]],
        search_radius_km: float = 25.0,
        ring_size: int = 5,
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Runs the full matching pipeline against real database donors for an emergency request.
        """
        if reference_date is None:
            reference_date = date.today()

        audit_entries = []
        eligible_candidates = []

        for donor in donor_pool:
            is_eligible, hard_filter_audit = evaluate_hard_filters(
                donor=donor,
                request=request,
                max_radius_km=search_radius_km,
                reference_date=reference_date
            )
            audit_entries.append(hard_filter_audit)
            
            if is_eligible:
                dist_km = hard_filter_audit["distance_km"]
                score, breakdown = calculate_donor_score(
                    donor=donor,
                    request=request,
                    distance_km=dist_km,
                    max_radius_km=search_radius_km,
                    weights=self.weights,
                    reference_date=reference_date
                )
                eligible_candidates.append({
                    "donor": donor,
                    "score": score,
                    "distance_km": dist_km,
                    "score_breakdown": breakdown
                })

        # Sort eligible candidates: Nearest -> Farthest, then highest match score
        eligible_candidates.sort(key=lambda x: (x["distance_km"], -x["score"]))

        # Assign candidate rings
        rings: Dict[int, List[Dict[str, Any]]] = {}
        for idx, candidate in enumerate(eligible_candidates):
            ring_number = (idx // ring_size) + 1
            candidate["ring"] = ring_number
            rings.setdefault(ring_number, []).append(candidate)

        match_summary = {
            "request_id": request.get("id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_radius_km": search_radius_km,
            "total_donors_evaluated": len(donor_pool),
            "eligible_donors_count": len(eligible_candidates),
            "ranked_candidates": eligible_candidates,
            "rings": rings,
            "audit_log": {
                "request_id": request.get("id"),
                "total_evaluated": len(donor_pool),
                "total_eligible": len(eligible_candidates),
                "evaluations": audit_entries
            }
        }
        return match_summary
