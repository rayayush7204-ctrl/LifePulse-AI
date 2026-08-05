"""
Blood Type Medical Compatibility Matrix.
Deterministic rules based on WHO / Red Cross clinical guidelines for Whole Blood, RBC, Plasma, and Platelets.
"""

from typing import List, Dict, Set

# Valid ABO & Rh Blood Types
VALID_BLOOD_TYPES: Set[str] = {
    "O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"
}

# Red Blood Cell / Whole Blood Compatibility: Key = Recipient, Value = Compatible Donor Types
RBC_COMPATIBILITY_MAP: Dict[str, List[str]] = {
    "O-":  ["O-"],
    "O+":  ["O-", "O+"],
    "A-":  ["O-", "A-"],
    "A+":  ["O-", "O+", "A-", "A+"],
    "B-":  ["O-", "B-"],
    "B+":  ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
}

# Plasma Compatibility (Inverse of RBC): Key = Recipient, Value = Compatible Donor Types
PLASMA_COMPATIBILITY_MAP: Dict[str, List[str]] = {
    "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "A-":  ["A-", "A+", "AB-", "AB+"],
    "A+":  ["A-", "A+", "AB-", "AB+"],
    "B-":  ["B-", "B+", "AB-", "AB+"],
    "B+":  ["B-", "B+", "AB-", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB-", "AB+"]
}

# Platelets Compatibility: Key = Recipient, Value = Compatible Donor Types
PLATELET_COMPATIBILITY_MAP: Dict[str, List[str]] = {
    "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "A-":  ["A-", "A+", "AB-", "AB+"],
    "A+":  ["A-", "A+", "AB-", "AB+"],
    "B-":  ["B-", "B+", "AB-", "AB+"],
    "B+":  ["B-", "B+", "AB-", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB-", "AB+"]
}

def normalize_blood_type(bt: str) -> str:
    """Clean and validate blood type string format."""
    cleaned = bt.strip().upper().replace(" ", "")
    if cleaned not in VALID_BLOOD_TYPES:
        raise ValueError(f"Invalid blood type '{bt}'. Must be one of {sorted(VALID_BLOOD_TYPES)}")
    return cleaned

def get_compatible_donor_types(recipient_type: str, donation_type: str = "WHOLE_BLOOD") -> List[str]:
    """
    Returns list of donor blood types compatible with the given recipient type.
    """
    rec_type = normalize_blood_type(recipient_type)
    dtype = donation_type.upper()
    
    if dtype in ("WHOLE_BLOOD", "RBC", "RED_BLOOD_CELLS"):
        return RBC_COMPATIBILITY_MAP[rec_type]
    elif dtype == "PLASMA":
        return PLASMA_COMPATIBILITY_MAP[rec_type]
    elif dtype == "PLATELETS":
        return PLATELET_COMPATIBILITY_MAP[rec_type]
    else:
        # Default to RBC compatibility for safety
        return RBC_COMPATIBILITY_MAP[rec_type]

def is_blood_compatible(donor_type: str, recipient_type: str, donation_type: str = "WHOLE_BLOOD") -> bool:
    """
    Checks if a donor's blood type is medically compatible with recipient.
    """
    try:
        d_type = normalize_blood_type(donor_type)
        r_type = normalize_blood_type(recipient_type)
        compatible_types = get_compatible_donor_types(r_type, donation_type)
        return d_type in compatible_types
    except ValueError:
        return False
