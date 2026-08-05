"""
AI-Assisted Medical Pre-Screening & Donor Eligibility Engine.
Evaluates structured questionnaire responses using deterministic clinical rules + AI risk flags.
NOTE: Final donation clearance is ALWAYS performed by the hospital/blood bank.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

PRE_SCREENING_DISCLAIMER = (
    "AI-assisted preliminary screening. Final eligibility for blood donation is determined by "
    "the hospital/blood bank before collection."
)

def evaluate_medical_prescreening(screening_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates donor medical pre-screening questionnaire using validated clinical rules.
    
    Returns structured eligibility status, pass/fail reasons, risk flags, and disclaimer.
    """
    reasons = []
    flags = []
    status = "POTENTIALLY_ELIGIBLE"

    age = int(screening_data.get("age", 25))
    weight_kg = float(screening_data.get("weight_kg", 65.0))
    has_fever = bool(screening_data.get("has_fever_or_illness", False))
    recent_meds = bool(screening_data.get("recent_medication", False))
    recent_surgery = bool(screening_data.get("recent_surgery", False))
    recent_vaccine = bool(screening_data.get("recent_vaccination", False))
    is_pregnant = bool(screening_data.get("pregnancy_status", False))
    recent_tattoo = bool(screening_data.get("recent_tattoo_or_piercing", False))
    travel_history = bool(screening_data.get("travel_exposure_history", False))

    # Rule 1: Age Check (18 - 65)
    if age < 18 or age > 65:
        reasons.append(f"FAIL: Age {age} is outside the standard 18-65 donation age window.")
        status = "TEMPORARILY_INELIGIBLE"
    else:
        reasons.append(f"PASS: Age {age} within standard donation window.")

    # Rule 2: Minimum Weight (45 kg)
    if weight_kg < 45.0:
        reasons.append(f"FAIL: Weight {weight_kg}kg is below the 45kg minimum safety threshold.")
        status = "TEMPORARILY_INELIGIBLE"
    else:
        reasons.append(f"PASS: Weight {weight_kg}kg satisfies minimum threshold.")

    # Rule 3: Active Fever / Illness
    if has_fever:
        reasons.append("FAIL: Currently reporting active fever or acute infection.")
        status = "TEMPORARILY_INELIGIBLE"
    else:
        reasons.append("PASS: No active fever or acute infection reported.")

    # Rule 4: Recent Surgery
    if recent_surgery:
        reasons.append("FAIL: Major surgical procedure in the last 6 months requires recovery deferral.")
        status = "TEMPORARILY_INELIGIBLE"
    else:
        reasons.append("PASS: No recent major surgical procedures.")

    # Rule 5: Tattoo / Piercing
    if recent_tattoo:
        reasons.append("FAIL: Recent tattoo or body piercing (< 6 months) requires standard safety gap.")
        status = "TEMPORARILY_INELIGIBLE"
    else:
        reasons.append("PASS: No recent body tattoos or piercings.")

    # Rule 6: Pregnancy Status
    if is_pregnant:
        reasons.append("FAIL: Active pregnancy or recent childbirth requires deferral.")
        status = "TEMPORARILY_INELIGIBLE"

    # Flag 1: Recent Medication
    if recent_meds:
        flags.append("FLAG: Taking prescription medications. Specific drug screening required at blood bank.")
        if status == "POTENTIALLY_ELIGIBLE":
            status = "REQUIRES_ADDITIONAL_SCREENING"

    # Flag 2: Recent Vaccination
    if recent_vaccine:
        flags.append("FLAG: Vaccination received in last 14 days. Vaccine type verification required.")
        if status == "POTENTIALLY_ELIGIBLE":
            status = "REQUIRES_ADDITIONAL_SCREENING"

    # Flag 3: Endemic Travel Exposure
    if travel_history:
        flags.append("FLAG: Recent travel to malaria/endemic region reported. Hospital travel screening needed.")
        if status == "POTENTIALLY_ELIGIBLE":
            status = "REQUIRES_ADDITIONAL_SCREENING"

    return {
        "eligibility_status": status,
        "eligibility_reasons": reasons,
        "eligibility_flags": flags,
        "disclaimer": PRE_SCREENING_DISCLAIMER,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }
