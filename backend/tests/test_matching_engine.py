"""
Exhaustive Test Suite for Blood Donor Matching Engine.
Tests compatibility matrix, hard eligibility rules, weighted scorer, and engine orchestration.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import date, timedelta
from app.matching.blood_matrix import (
    is_blood_compatible,
    get_compatible_donor_types,
    normalize_blood_type,
    RBC_COMPATIBILITY_MAP,
    PLASMA_COMPATIBILITY_MAP
)
from app.matching.hard_filters import evaluate_hard_filters, calculate_haversine_distance_km
from app.matching.scorer import calculate_donor_score
from app.matching.engine import MatchingEngine

# ---------------------------------------------------------
# 1. Blood Matrix Tests
# ---------------------------------------------------------

def test_blood_matrix_rbc_compatibility_exhaustive():
    """Verify RBC / Whole blood compatibility rules for all combinations."""
    # O- is universal red cell donor
    for recipient in ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]:
        assert is_blood_compatible("O-", recipient, "WHOLE_BLOOD") is True
        assert is_blood_compatible("O-", recipient, "RBC") is True

    # O+ can donate to Rh+ recipients only
    for recipient in ["O+", "A+", "B+", "AB+"]:
        assert is_blood_compatible("O+", recipient, "RBC") is True
    for recipient in ["O-", "A-", "B-", "AB-"]:
        assert is_blood_compatible("O+", recipient, "RBC") is False

    # AB+ can only donate RBCs to AB+
    assert is_blood_compatible("AB+", "AB+", "RBC") is True
    assert is_blood_compatible("AB+", "A+", "RBC") is False
    assert is_blood_compatible("AB+", "O+", "RBC") is False

    # AB+ is universal recipient for RBC
    all_donors = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
    assert get_compatible_donor_types("AB+", "RBC") == all_donors


def test_blood_matrix_plasma_compatibility():
    """Verify Plasma donor compatibility (AB is universal donor for plasma)."""
    # AB+ and AB- can donate plasma to anyone
    for recipient in ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]:
        assert is_blood_compatible("AB+", recipient, "PLASMA") is True
        assert is_blood_compatible("AB-", recipient, "PLASMA") is True

    # O- plasma can only go to O recipients
    assert is_blood_compatible("O-", "O+", "PLASMA") is True
    assert is_blood_compatible("O-", "A+", "PLASMA") is False


def test_invalid_blood_type_handling():
    """Verify invalid blood strings fail gracefully."""
    assert is_blood_compatible("XYZ", "O+", "RBC") is False
    with pytest.raises(ValueError):
        normalize_blood_type("INVALID")

# ---------------------------------------------------------
# 2. Hard Filters Tests
# ---------------------------------------------------------

def test_hard_filters_eligibility_window():
    """Verify 56-day donation interval restriction."""
    today = date(2026, 7, 29)
    req = {
        "blood_type": "A+",
        "donation_type": "WHOLE_BLOOD",
        "latitude": 37.7749,
        "longitude": -122.4194
    }

    # Donor donated 30 days ago -> INELIGIBLE
    recent_donor = {
        "id": "d1",
        "blood_type": "A+",
        "is_active": True,
        "is_available": True,
        "last_donation_date": today - timedelta(days=30),
        "latitude": 37.7750,
        "longitude": -122.4195
    }
    is_elig, audit = evaluate_hard_filters(recent_donor, req, reference_date=today)
    assert is_elig is False
    assert any("Donated 30 days ago" in r for r in audit["reasons"])

    # Donor donated 60 days ago -> ELIGIBLE
    eligible_donor = {
        "id": "d2",
        "blood_type": "A+",
        "is_active": True,
        "is_available": True,
        "last_donation_date": today - timedelta(days=60),
        "latitude": 37.7750,
        "longitude": -122.4195
    }
    is_elig2, audit2 = evaluate_hard_filters(eligible_donor, req, reference_date=today)
    assert is_elig2 is True
    assert audit2["passed_all"] is True


def test_hard_filters_medical_disqualifications():
    """Verify donor with medical flags is rejected."""
    donor = {
        "id": "d3",
        "blood_type": "O-",
        "is_active": True,
        "is_available": True,
        "medical_disqualifications": ["Low hemoglobin"],
        "latitude": 37.7749,
        "longitude": -122.4194
    }
    req = {"blood_type": "O-", "latitude": 37.7749, "longitude": -122.4194}
    is_elig, audit = evaluate_hard_filters(donor, req)
    assert is_elig is False
    assert any("Disqualifying medical flags" in r for r in audit["reasons"])


def test_hard_filters_distance_boundary():
    """Verify donors outside max search radius are filtered out."""
    req = {"blood_type": "O+", "latitude": 37.7749, "longitude": -122.4194} # SF
    
    # Near donor (~1 km)
    near_donor = {
        "id": "near",
        "blood_type": "O+",
        "is_active": True,
        "is_available": True,
        "latitude": 37.7800,
        "longitude": -122.4200
    }
    is_elig1, audit1 = evaluate_hard_filters(near_donor, req, max_radius_km=10.0)
    assert is_elig1 is True

    # Far donor (~50 km)
    far_donor = {
        "id": "far",
        "blood_type": "O+",
        "is_active": True,
        "is_available": True,
        "latitude": 37.3382,
        "longitude": -121.8863 # San Jose (~65km away)
    }
    is_elig2, audit2 = evaluate_hard_filters(far_donor, req, max_radius_km=25.0)
    assert is_elig2 is False
    assert any("exceeds max search radius" in r for r in audit2["reasons"])

# ---------------------------------------------------------
# 3. Weighted Scorer Tests
# ---------------------------------------------------------

def test_scorer_proximity_and_scarcity():
    """Verify closer donors and rare blood types get higher scores."""
    req = {"blood_type": "AB-", "latitude": 37.7749, "longitude": -122.4194}
    
    donor_close_rare = {
        "blood_type": "AB-",
        "last_donation_date": date.today() - timedelta(days=200),
        "reliability_score": 0.95
    }
    score1, b1 = calculate_donor_score(donor_close_rare, req, distance_km=2.0, max_radius_km=25.0)
    
    donor_far_common = {
        "blood_type": "O+",
        "last_donation_date": date.today() - timedelta(days=60),
        "reliability_score": 0.70
    }
    score2, b2 = calculate_donor_score(donor_far_common, req, distance_km=20.0, max_radius_km=25.0)

    assert score1 > score2
    assert b1["subscores"]["proximity"] > b2["subscores"]["proximity"]
    assert b1["subscores"]["scarcity"] > b2["subscores"]["scarcity"]

# ---------------------------------------------------------
# 4. End-to-End Matching Engine Orchestrator
# ---------------------------------------------------------

def test_matching_engine_end_to_end_ring_allocation():
    """Verify engine filters, scores, sorts, and assigns rings correctly."""
    engine = MatchingEngine()
    req = {
        "id": "req-101",
        "blood_type": "B+",
        "latitude": 37.7749,
        "longitude": -122.4194
    }

    donor_pool = [
        # Ineligible (Incompatible blood type)
        {"id": "d_incompat", "blood_type": "AB+", "is_active": True, "is_available": True, "latitude": 37.775, "longitude": -122.419},
        # Ineligible (Donated recently)
        {"id": "d_recent", "blood_type": "B+", "is_active": True, "is_available": True, "last_donation_date": date.today() - timedelta(days=10), "latitude": 37.775, "longitude": -122.419},
        # Eligible 1 (High score, close)
        {"id": "d_top", "blood_type": "B+", "is_active": True, "is_available": True, "reliability_score": 0.98, "latitude": 37.776, "longitude": -122.420},
        # Eligible 2 (Universal donor O-)
        {"id": "d_universal", "blood_type": "O-", "is_active": True, "is_available": True, "reliability_score": 0.90, "latitude": 37.780, "longitude": -122.430},
        # Eligible 3 (Farther away)
        {"id": "d_far", "blood_type": "B+", "is_active": True, "is_available": True, "reliability_score": 0.80, "latitude": 37.800, "longitude": -122.450},
    ]

    result = engine.match_donors(req, donor_pool, search_radius_km=25.0, ring_size=2)

    assert result["total_donors_evaluated"] == 5
    assert result["eligible_donors_count"] == 3

    ranked = result["ranked_candidates"]
    assert len(ranked) == 3
    assert ranked[0]["donor"]["id"] in ["d_top", "d_universal"]
    
    # Check ring distribution (ring_size = 2 -> 2 donors in ring 1, 1 donor in ring 2)
    assert len(result["rings"][1]) == 2
    assert len(result["rings"][2]) == 1
    assert "audit_log" in result
    assert len(result["audit_log"]["evaluations"]) == 5
