"""
Test Fixture Seed / Teardown
============================
Seeds deterministic synthetic donors into the running backend before the E2E
and hardening test suites run, then removes them afterward.

Rules:
  - ONLY called by run_tests.py, never by production startup code.
  - All test donor IDs are prefixed with "TEST_" so they are distinguishable
    from real registered donors.
  - Seeds exactly the donors required for the tests to be deterministic:
      • Blood type O-  (universal donor — required by every test emergency)
      • 5+ donors so the race test can find >=2 matches in Ring 1
      • All placed within ~5 km of UCSF (37.7631, -122.4578), which is the
        coordinates used by e2e_test.py and test_concurrent.py
  - All donors have last_donation_date=None (never donated) so they pass
    the 56-day filter 100% of the time.
  - is_active=True, is_available=True.

Usage (internal — invoked by run_tests.py):
  python test_seed.py seed
  python test_seed.py teardown
"""

import sys
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api/v1"

# 8 deterministic test donors, all O- (universal), within 3 km of UCSF test coords.
# is_active & is_available are set to True. last_donation_date is None.
# max_travel_radius_km is 25 km so all pass the distance filter.
TEST_DONORS = [
    {
        "id": "TEST_donor_001",
        "name": "Test Donor Alpha",
        "phone": "+14155550001",
        "email": "test_donor_001@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7625,
        "longitude": -122.4560,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.98,
    },
    {
        "id": "TEST_donor_002",
        "name": "Test Donor Bravo",
        "phone": "+14155550002",
        "email": "test_donor_002@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7640,
        "longitude": -122.4590,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.97,
    },
    {
        "id": "TEST_donor_003",
        "name": "Test Donor Charlie",
        "phone": "+14155550003",
        "email": "test_donor_003@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7610,
        "longitude": -122.4570,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.96,
    },
    {
        "id": "TEST_donor_004",
        "name": "Test Donor Delta",
        "phone": "+14155550004",
        "email": "test_donor_004@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7650,
        "longitude": -122.4550,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.95,
    },
    {
        "id": "TEST_donor_005",
        "name": "Test Donor Echo",
        "phone": "+14155550005",
        "email": "test_donor_005@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7630,
        "longitude": -122.4600,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.94,
    },
    {
        "id": "TEST_donor_006",
        "name": "Test Donor Foxtrot",
        "phone": "+14155550006",
        "email": "test_donor_006@test.invalid",
        "blood_type": "O-",
        "latitude": 37.7618,
        "longitude": -122.4545,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.93,
    },
    {
        "id": "TEST_donor_007",
        "name": "Test Donor Golf",
        "phone": "+14155550007",
        "email": "test_donor_007@test.invalid",
        "blood_type": "O+",
        "latitude": 37.7655,
        "longitude": -122.4580,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.92,
    },
    {
        "id": "TEST_donor_008",
        "name": "Test Donor Hotel",
        "phone": "+14155550008",
        "email": "test_donor_008@test.invalid",
        "blood_type": "A+",
        "latitude": 37.7600,
        "longitude": -122.4565,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True,
        "max_travel_radius_km": 25.0,
        "reliability_score": 0.91,
    },
]


def seed():
    """POST all test donors to the running backend. Idempotent — re-seeding updates existing records."""
    print(f"\n[test_seed] Seeding {len(TEST_DONORS)} test donors into {API}/donors/...")
    seeded = 0
    with httpx.Client(timeout=15.0) as client:
        for donor in TEST_DONORS:
            resp = client.post(f"{API}/donors/", json=donor)
            if resp.status_code in (200, 201):
                seeded += 1
            else:
                print(f"  [WARN] Failed to seed {donor['id']}: HTTP {resp.status_code} — {resp.text}")
    print(f"[test_seed] Seeded {seeded}/{len(TEST_DONORS)} donors. Database is ready for tests.\n")
    return seeded == len(TEST_DONORS)


def teardown():
    """Mark all TEST_ donors as inactive so they don't pollute subsequent queries.
    The API does not expose a DELETE /donors endpoint, so we deactivate via PUT/re-POST with is_active=False."""
    print(f"\n[test_seed] Deactivating {len(TEST_DONORS)} test donors...")
    removed = 0
    with httpx.Client(timeout=15.0) as client:
        for donor in TEST_DONORS:
            deactivated = {**donor, "is_active": False, "is_available": False}
            resp = client.post(f"{API}/donors/", json=deactivated)
            if resp.status_code in (200, 201):
                removed += 1
            else:
                print(f"  [WARN] Failed to deactivate {donor['id']}: HTTP {resp.status_code}")
    print(f"[test_seed] Deactivated {removed}/{len(TEST_DONORS)} test donors.\n")


def wait_for_backend(retries: int = 10, delay: float = 2.0) -> bool:
    """Poll /health until the backend responds, or timeout."""
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
            if resp.status_code == 200:
                print(f"[test_seed] Backend is up (attempt {attempt}).")
                return True
        except Exception:
            pass
        print(f"[test_seed] Waiting for backend... attempt {attempt}/{retries}")
        time.sleep(delay)
    print("[test_seed] ERROR: Backend did not become available in time.")
    return False


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if cmd == "seed":
        if not wait_for_backend():
            sys.exit(1)
        ok = seed()
        sys.exit(0 if ok else 1)
    elif cmd == "teardown":
        teardown()
        sys.exit(0)
    else:
        print(f"Usage: python test_seed.py [seed|teardown]")
        sys.exit(1)
