"""
Hard Filter Logic for Blood Donor Matching.
Evaluates deterministic medical eligibility, blood compatibility, spatial radius, and health disqualifications.
Every decision logs a clear reason for pass/fail.
"""

from datetime import datetime, date, timedelta
from math import radians, cos, sin, asin, sqrt
from typing import Dict, Any, Tuple, Optional
from app.matching.blood_matrix import is_blood_compatible

MIN_DONATION_INTERVAL_DAYS = 56  # standard 8-week gap for whole blood

def calculate_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two points in kilometers using Haversine formula.
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2.0)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0)**2
    c = 2.0 * asin(sqrt(a))
    r = 6371.0  # Radius of earth in kilometers
    return c * r

def calculate_bounding_box(lat: float, lon: float, radius_km: float) -> Dict[str, float]:
    """
    Calculates a rough bounding box (min/max lat/lon) around a given coordinate and radius.
    Used for fast SQL pre-filtering before accurate Haversine distance calculations.
    """
    # 1 degree of latitude is roughly 111.32 km
    lat_diff = radius_km / 111.32
    # 1 degree of longitude is roughly 111.32 * cos(lat) km
    # Handle division by zero at poles just in case
    cos_lat = cos(radians(lat))
    lon_diff = radius_km / (111.32 * cos_lat) if cos_lat != 0 else 0
    
    return {
        "min_lat": lat - lat_diff,
        "max_lat": lat + lat_diff,
        "min_lon": lon - lon_diff,
        "max_lon": lon + lon_diff
    }

def evaluate_hard_filters(
    donor: Dict[str, Any],
    request: Dict[str, Any],
    max_radius_km: float = 25.0,
    reference_date: Optional[date] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Evaluates hard rules for a donor against a specific request.
    
    Returns:
        (is_eligible: bool, audit_trail: dict)
    """
    if reference_date is None:
        reference_date = date.today()
        
    audit = {
        "donor_id": donor.get("id"),
        "passed_all": False,
        "reasons": [],
        "distance_km": None
    }
    
    # Rule 1: Active & Available status
    if not donor.get("is_active", True):
        audit["reasons"].append("FAIL: Donor profile is inactive.")
        return False, audit
        
    if not donor.get("is_available", True):
        audit["reasons"].append("FAIL: Donor currently set as unavailable.")
        return False, audit
        
    # Rule 2: Disqualifying medical flags
    disqualifications = donor.get("medical_disqualifications", [])
    if disqualifications:
        audit["reasons"].append(f"FAIL: Disqualifying medical flags: {', '.join(disqualifications)}")
        return False, audit

    # Rule 3: Blood Type Compatibility
    donor_bt = donor.get("blood_type")
    req_bt = request.get("blood_type")
    donation_type = request.get("donation_type", "WHOLE_BLOOD")
    
    if not is_blood_compatible(donor_bt, req_bt, donation_type):
        audit["reasons"].append(f"FAIL: Incompatible blood type {donor_bt} for recipient {req_bt} ({donation_type}).")
        return False, audit
    audit["reasons"].append(f"PASS: Compatible blood type ({donor_bt} -> {req_bt}).")

    # Rule 4: Minimum Donation Interval (56 days)
    last_donation = donor.get("last_donation_date")
    if last_donation:
        if isinstance(last_donation, str):
            last_donation_dt = datetime.strptime(last_donation, "%Y-%m-%d").date()
        elif isinstance(last_donation, datetime):
            last_donation_dt = last_donation.date()
        else:
            last_donation_dt = last_donation
            
        days_since = (reference_date - last_donation_dt).days
        if days_since < MIN_DONATION_INTERVAL_DAYS:
            days_remaining = MIN_DONATION_INTERVAL_DAYS - days_since
            audit["reasons"].append(
                f"FAIL: Donated {days_since} days ago. Must wait {days_remaining} more days (min {MIN_DONATION_INTERVAL_DAYS} days)."
            )
            return False, audit
        audit["reasons"].append(f"PASS: Eligible donation interval ({days_since} days since last donation).")
    else:
        audit["reasons"].append("PASS: First-time or eligible donor (no previous donation recorded).")

    # Rule 5: Spatial Proximity (Distance)
    d_lat, d_lon = donor.get("latitude"), donor.get("longitude")
    r_lat, r_lon = request.get("latitude"), request.get("longitude")
    
    if d_lat is None or d_lon is None or r_lat is None or r_lon is None:
        audit["reasons"].append("FAIL: Missing spatial coordinates for donor or request.")
        return False, audit
        
    distance_km = round(calculate_haversine_distance_km(d_lat, d_lon, r_lat, r_lon), 2)
    audit["distance_km"] = distance_km
    
    if distance_km > max_radius_km:
        audit["reasons"].append(f"FAIL: Distance {distance_km}km exceeds max search radius of {max_radius_km}km.")
        return False, audit
    audit["reasons"].append(f"PASS: Within search radius ({distance_km}km <= {max_radius_km}km).")

    audit["passed_all"] = True
    return True, audit
