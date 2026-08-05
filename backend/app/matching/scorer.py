"""
Weighted Ranking Scorer for Blood Donors.
Calculates a transparent, explainable ranking score (0.0 to 100.0) based on configurable feature weights.
"""

from typing import Dict, Any, Tuple
from datetime import date, datetime

DEFAULT_SCORING_WEIGHTS = {
    "distance": 0.65,               # Proximity heavily prioritized (65%)
    "days_since_donation": 0.15,    # Recovery time buffer (15%)
    "reliability_score": 0.10,      # Historical response rate (10%)
    "scarcity_bonus": 0.10          # Rare blood group bonus (10%)
}

# Population rarity index (0.0 = common O+, 1.0 = rare AB- / O-)
BLOOD_SCARCITY_INDEX = {
    "AB-": 1.00,
    "B-":  0.85,
    "A-":  0.80,
    "O-":  0.95,  # High demand universal donor
    "AB+": 0.50,
    "B+":  0.30,
    "A+":  0.20,
    "O+":  0.10
}

def calculate_donor_score(
    donor: Dict[str, Any],
    request: Dict[str, Any],
    distance_km: float,
    max_radius_km: float = 25.0,
    weights: Dict[str, float] = None,
    reference_date: date = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculates weighted score for an eligible donor.
    
    Returns:
        (total_score: float, score_breakdown: dict)
    """
    if weights is None:
        weights = DEFAULT_SCORING_WEIGHTS
        
    if reference_date is None:
        reference_date = date.today()

    # 1. Proximity Sub-score (0 - 100)
    # 0 km -> 100, max_radius_km -> 0
    clamped_distance = min(distance_km, max_radius_km)
    proximity_subscore = max(0.0, (1.0 - (clamped_distance / max_radius_km)) * 100.0)

    # 2. Days Since Donation Sub-score (0 - 100)
    # Donated 56 days ago -> 50, Donated 180+ days ago -> 100
    last_donation = donor.get("last_donation_date")
    if last_donation:
        if isinstance(last_donation, str):
            last_donation_dt = datetime.strptime(last_donation, "%Y-%m-%d").date()
        elif isinstance(last_donation, datetime):
            last_donation_dt = last_donation.date()
        else:
            last_donation_dt = last_donation
        days_since = (reference_date - last_donation_dt).days
    else:
        days_since = 365  # Default for first time donors
        
    readiness_subscore = min(100.0, max(0.0, (days_since / 180.0) * 100.0))

    # 3. Reliability Sub-score (0 - 100)
    rel_rating = donor.get("reliability_score", 0.8)  # default 0.8 / 1.0
    reliability_subscore = min(100.0, max(0.0, rel_rating * 100.0))

    # 4. Scarcity Sub-score (0 - 100)
    donor_bt = donor.get("blood_type", "O+")
    scarcity_subscore = BLOOD_SCARCITY_INDEX.get(donor_bt, 0.2) * 100.0

    # Total Weighted Calculation
    w_dist = weights.get("distance", 0.40)
    w_ready = weights.get("days_since_donation", 0.25)
    w_rel = weights.get("reliability_score", 0.20)
    w_scar = weights.get("scarcity_bonus", 0.15)
    
    total_weight = w_dist + w_ready + w_rel + w_scar
    if total_weight == 0:
        total_weight = 1.0

    final_score = (
        (proximity_subscore * w_dist) +
        (readiness_subscore * w_ready) +
        (reliability_subscore * w_rel) +
        (scarcity_subscore * w_scar)
    ) / total_weight

    score_breakdown = {
        "final_score": round(final_score, 2),
        "subscores": {
            "proximity": round(proximity_subscore, 2),
            "readiness": round(readiness_subscore, 2),
            "reliability": round(reliability_subscore, 2),
            "scarcity": round(scarcity_subscore, 2)
        },
        "weights_used": {
            "distance": w_dist,
            "days_since_donation": w_ready,
            "reliability_score": w_rel,
            "scarcity_bonus": w_scar
        },
        "raw_metrics": {
            "distance_km": distance_km,
            "days_since_donation": days_since,
            "reliability_rating": rel_rating,
            "blood_type": donor_bt
        }
    }

    return round(final_score, 2), score_breakdown
