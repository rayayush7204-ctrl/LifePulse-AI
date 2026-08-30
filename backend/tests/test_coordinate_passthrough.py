"""
Coordinate Passthrough Verification Test for Emergency Dispatch Location System.

Proves that:
  1. The matching engine uses ONLY the submitted coordinates (Location B), 
     NOT the requester's GPS position (Location A).
  2. All three location_source values (gps, map_pin, search) pass coordinates correctly.
  3. Distances are independently verifiable using the Haversine formula.

Each test uses controlled coordinates with a known donor, so the expected
distance can be hand-computed and compared to the engine's output.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from math import radians, cos, sin, asin, sqrt
from datetime import date, timedelta

from app.matching.engine import MatchingEngine
from app.matching.hard_filters import evaluate_hard_filters, calculate_haversine_distance_km
from app.models.schemas import BloodRequestCreate


# ── Reference Haversine (independent of app code) ────────────

def ref_haversine_km(lat1, lon1, lat2, lon2):
    """Independent haversine implementation for cross-checking."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2.0) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0) ** 2
    return 2.0 * 6371.0 * asin(sqrt(a))


# ── Fixed Coordinates ────────────────────────────────────────

# Location A: Requester's actual GPS position (SHOULD NOT be used after override)
LOC_A_LAT, LOC_A_LON = 28.6139, 77.2090  # New Delhi, India

# Location B: Requester selects a DIFFERENT location for the emergency
LOC_B_LAT, LOC_B_LON = 19.0760, 72.8777  # Mumbai, India  (~1,150 km away from A)

# Location C: Yet another override test point
LOC_C_LAT, LOC_C_LON = 12.9716, 77.5946  # Bangalore, India (~1,750 km from A)

# Donor: Fixed position near Location B (Mumbai)
DONOR_LAT, DONOR_LON = 19.0830, 72.8900   # ~1.5 km from B, ~1,150 km from A

# ── Shared donor fixture ─────────────────────────────────────

def make_donor(donor_id="donor-1", lat=DONOR_LAT, lon=DONOR_LON, blood_type="O-"):
    return {
        "id": donor_id,
        "blood_type": blood_type,
        "is_active": True,
        "is_available": True,
        "latitude": lat,
        "longitude": lon,
        "reliability_score": 0.90,
        "last_donation_date": date.today() - timedelta(days=200),
    }


# ═══════════════════════════════════════════════════════════════
# TEST 1: Matching engine uses submitted coordinates (Location B)
#          and NOT the requester's GPS (Location A)
# ═══════════════════════════════════════════════════════════════

def test_matching_uses_submitted_location_not_gps():
    """
    Scenario:
      - Requester's GPS = Location A (New Delhi: 28.6139, 77.2090)
      - Requester submits request for Location B (Mumbai: 19.0760, 72.8777)
      - Donor is located near Mumbai (19.0830, 72.8900)
    
    Expected:
      - Distance from DONOR to Location B ≈ 1.5 km   → Donor IS ELIGIBLE (within 25km)
      - Distance from DONOR to Location A ≈ 1,150 km  → Would be INELIGIBLE if GPS were used
    
    This proves the engine uses Location B (submitted), NOT Location A (GPS).
    """
    engine = MatchingEngine()
    
    # The request carries Location B's coordinates
    request = {
        "id": "req-coord-verify-001",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "latitude": LOC_B_LAT,
        "longitude": LOC_B_LON,
        "location_name": "Mumbai Emergency",
        "location_source": "search",
    }
    
    donor = make_donor()
    
    # Pre-calculate expected distances using independent reference function
    expected_dist_from_B = ref_haversine_km(DONOR_LAT, DONOR_LON, LOC_B_LAT, LOC_B_LON)
    expected_dist_from_A = ref_haversine_km(DONOR_LAT, DONOR_LON, LOC_A_LAT, LOC_A_LON)
    
    # Sanity: B should be close, A should be very far
    assert expected_dist_from_B < 5.0, f"Donor-to-B should be ~1.5km, got {expected_dist_from_B:.2f}"
    assert expected_dist_from_A > 1000.0, f"Donor-to-A should be >1000km, got {expected_dist_from_A:.2f}"
    
    # Run engine with default 25km radius
    result = engine.match_donors(request, [donor], search_radius_km=25.0)
    
    # CRITICAL ASSERTION: Donor must be matched (engine used Location B)
    assert result["eligible_donors_count"] == 1, (
        f"Engine should find 1 eligible donor from Location B, found {result['eligible_donors_count']}. "
        f"If 0, the engine may be using Location A (GPS) instead of submitted coordinates."
    )
    
    # Verify the calculated distance matches our independent reference
    actual_distance = result["ranked_candidates"][0]["distance_km"]
    assert abs(actual_distance - expected_dist_from_B) < 0.1, (
        f"Distance mismatch: engine={actual_distance:.2f}km, reference={expected_dist_from_B:.2f}km"
    )
    
    # Double-check: If engine had used Location A, donor would be OUT of radius
    _, audit_with_A = evaluate_hard_filters(donor, {
        "blood_type": "O-",
        "latitude": LOC_A_LAT,
        "longitude": LOC_A_LON
    }, max_radius_km=25.0)
    
    assert audit_with_A["passed_all"] is False, (
        "Sanity check failed: donor should be OUT of range from Location A (Delhi)"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 2: Verify all three location_source values pass through
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("source,lat,lon,loc_name", [
    ("gps", LOC_B_LAT, LOC_B_LON, "GPS Location"),
    ("map_pin", LOC_B_LAT, LOC_B_LON, "Dropped Pin"),
    ("search", LOC_B_LAT, LOC_B_LON, "Searched Location"),
])
def test_all_location_sources_use_submitted_coordinates(source, lat, lon, loc_name):
    """
    Verify that regardless of location_source (gps, map_pin, search),
    the matching engine uses the submitted lat/lon.
    """
    engine = MatchingEngine()
    
    request = {
        "id": f"req-source-{source}",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "latitude": lat,
        "longitude": lon,
        "location_name": loc_name,
        "location_source": source,
    }
    
    donor = make_donor()
    result = engine.match_donors(request, [donor], search_radius_km=25.0)
    
    assert result["eligible_donors_count"] == 1, (
        f"source={source}: Engine should find donor with submitted coords, got {result['eligible_donors_count']}"
    )
    
    actual_dist = result["ranked_candidates"][0]["distance_km"]
    expected_dist = ref_haversine_km(DONOR_LAT, DONOR_LON, lat, lon)
    assert abs(actual_dist - expected_dist) < 0.1, (
        f"source={source}: Distance mismatch engine={actual_dist:.2f} vs ref={expected_dist:.2f}"
    )


# ═══════════════════════════════════════════════════════════════
# TEST 3: Schema validation – coordinates are required and preserved
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("source", ["gps", "map_pin", "search"])
def test_schema_preserves_coordinates_for_all_sources(source):
    """
    Verify the Pydantic BloodRequestCreate schema preserves exact coordinates
    and location_source values through validation.
    """
    payload = BloodRequestCreate(
        patient_name="Test Patient",
        requester_phone="+910000000000",
        location_name="Test Location",
        location_address="Test Address",
        location_source=source,
        blood_type="O-",
        units_needed=2,
        urgency_level="CRITICAL",
        latitude=LOC_C_LAT,
        longitude=LOC_C_LON,
        notes="Test note"
    )
    
    assert payload.latitude == LOC_C_LAT, f"Latitude not preserved: {payload.latitude}"
    assert payload.longitude == LOC_C_LON, f"Longitude not preserved: {payload.longitude}"
    assert payload.location_source.value == source, f"Source not preserved: {payload.location_source}"
    assert payload.location_name == "Test Location"
    assert payload.location_address == "Test Address"


# ═══════════════════════════════════════════════════════════════
# TEST 4: Map Pin override – different location from GPS
# ═══════════════════════════════════════════════════════════════

def test_map_pin_override_distance():
    """
    Requester GPS is in Delhi, but pins Bangalore on the map.
    A donor near Bangalore (~2 km) should match.
    A donor near Delhi should NOT match (out of radius from Bangalore).
    """
    engine = MatchingEngine()
    
    request = {
        "id": "req-pin-override",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "latitude": LOC_C_LAT,   # Bangalore (pinned)
        "longitude": LOC_C_LON,
        "location_source": "map_pin",
    }
    
    donor_near_bangalore = make_donor("d-bang", lat=12.9750, lon=77.5980, blood_type="O-")
    donor_near_delhi = make_donor("d-delhi", lat=28.6200, lon=77.2100, blood_type="O-")
    
    result = engine.match_donors(
        request, [donor_near_bangalore, donor_near_delhi], search_radius_km=25.0
    )
    
    assert result["eligible_donors_count"] == 1, (
        f"Only Bangalore donor should match, got {result['eligible_donors_count']}"
    )
    assert result["ranked_candidates"][0]["donor"]["id"] == "d-bang"
    
    actual_dist = result["ranked_candidates"][0]["distance_km"]
    expected_dist = ref_haversine_km(12.9750, 77.5980, LOC_C_LAT, LOC_C_LON)
    assert abs(actual_dist - expected_dist) < 0.1


# ═══════════════════════════════════════════════════════════════
# TEST 5: Search override – search for "Red Fort" selects Delhi coords
# ═══════════════════════════════════════════════════════════════

def test_search_override_uses_selected_coordinates():
    """
    User searches for "Red Fort" and selects coordinates near Delhi.
    A donor near Delhi should match.
    A donor near Mumbai should NOT.
    """
    engine = MatchingEngine()
    
    # User selected Red Fort from search results
    RED_FORT_LAT, RED_FORT_LON = 28.6562, 77.2410
    
    request = {
        "id": "req-search-override",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "latitude": RED_FORT_LAT,
        "longitude": RED_FORT_LON,
        "location_name": "Red Fort",
        "location_source": "search",
    }
    
    donor_near_delhi = make_donor("d-delhi-rf", lat=28.6600, lon=77.2400, blood_type="O-")
    donor_near_mumbai = make_donor("d-mumbai-rf", lat=19.0760, lon=72.8777, blood_type="O-")
    
    result = engine.match_donors(
        request, [donor_near_delhi, donor_near_mumbai], search_radius_km=25.0
    )
    
    assert result["eligible_donors_count"] == 1
    assert result["ranked_candidates"][0]["donor"]["id"] == "d-delhi-rf"
    
    actual_dist = result["ranked_candidates"][0]["distance_km"]
    expected_dist = ref_haversine_km(28.6600, 77.2400, RED_FORT_LAT, RED_FORT_LON)
    assert abs(actual_dist - expected_dist) < 0.1
