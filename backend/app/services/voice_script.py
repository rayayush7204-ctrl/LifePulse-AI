"""
Voice Agent Script Generator.
Generates dynamic, urgency-tailored IVR scripts for Exotel automated calls to unresponsive donors.
"""

from typing import Dict, Any

def generate_voice_agent_script(request: Dict[str, Any], donor_name: str) -> str:
    """
    Generates IVR audio script tailored to blood type, hospital, and urgency level.
    """
    blood_type = request.get("blood_type", "compatible")
    hospital = request.get("hospital_name", "the local hospital")
    urgency = request.get("urgency_level", "HIGH")
    units = request.get("units_needed", 1)

    if urgency == "CRITICAL":
        return (
            f"Hello {donor_name}. This is an urgent medical alert from the Blood Donation Network. "
            f"A patient in critical condition at {hospital} urgently requires {units} units of {blood_type} blood. "
            f"You are a top compatible donor located nearby. "
            f"Press 1 on your phone right now to accept and receive turn-by-turn navigation. "
            f"Press 9 if you are unable to donate today. Thank you for helping save a life."
        )
    else:
        return (
            f"Hello {donor_name}. An urgent request for {blood_type} blood has been made for a patient at {hospital}. "
            f"If you are available to donate today, please press 1 to accept. Press 9 to decline."
        )
