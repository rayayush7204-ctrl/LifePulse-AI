"""
Comprehensive Feature Verification Suite.
Tests all 10 core features of the AI Smart Blood Donor Matcher platform against the running backend server.
"""

import sys
import httpx
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api/v1"

def print_result(feature_name: str, passed: bool, details: str = ""):
    status_str = "[PASS]" if passed else "[FAIL]"
    print(f"{status_str} {feature_name}")
    if details:
        print(f"    └── Details: {details}")


def verify_all_features():
    print("=" * 70)
    print("AI SMART BLOOD DONOR MATCHER - END-TO-END FEATURE VERIFICATION")
    print("=" * 70)

    client = httpx.Client(timeout=10.0)

    # 1. Health Check
    try:
        r = client.get("http://127.0.0.1:8000/health")
        passed = r.status_code == 200 and r.json().get("status") == "healthy"
        print_result("1. Health Check & Core Services", passed, f"Status: {r.status_code}, Donors: {r.json().get('donors_count')}")
    except Exception as e:
        print_result("1. Health Check & Core Services", False, str(e))

    # 2. AI Free-Text NLP Request Parser
    try:
        r = client.post(f"{BASE_URL}/ai/parse-request", json={"text": "Urgent! Need 2 bags B positive blood at Manipal Hospital!"})
        data = r.json()
        passed = r.status_code == 200 and data.get("blood_type") == "B+" and data.get("units_needed") == 2
        print_result("2. AI Free-Text Request Parser (LLM/Regex)", passed, f"Extracted: Blood={data.get('blood_type')}, Units={data.get('units_needed')}, Urgency={data.get('urgency_level')}")
    except Exception as e:
        print_result("2. AI Free-Text Request Parser", False, str(e))

    # 3. Phase 1: Voice SOS Speech Parser
    try:
        r = client.post(f"{BASE_URL}/ai/voice-sos", json={"transcript": "Urgent! Need 3 bags of O negative blood at UCSF hospital immediately for trauma patient!"})
        data = r.json()
        passed = r.status_code == 200 and data.get("blood_type") == "O-" and data.get("units_needed") == 3 and data.get("is_voice_sos") is True
        print_result("3. Phase 1: One-Tap Voice SOS Speech Parser", passed, f"Parsed Spoken Dictation: Blood={data.get('blood_type')}, Units={data.get('units_needed')}, Hospital={data.get('hospital_name')}")
    except Exception as e:
        print_result("3. Phase 1: Voice SOS Speech Parser", False, str(e))

    # 4. Donor Registration & Listing
    donor_id = "donor-verify-101"
    try:
        r_reg = client.post(f"{BASE_URL}/donors/", json={
            "name": "Verify Tester",
            "phone": "+14155559999",
            "email": "verify@example.com",
            "blood_type": "O-",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "city": "San Francisco"
        })
        d_data = r_reg.json()
        if r_reg.status_code == 200:
            donor_id = d_data.get("id", donor_id)

        r_list = client.get(f"{BASE_URL}/donors/")
        passed = r_reg.status_code == 200 and r_list.status_code == 200 and len(r_list.json()) >= 1
        print_result("4. Donor Registration & Pool Directory", passed, f"Registered Donor ID: {donor_id}, Total Donors: {len(r_list.json())}")
    except Exception as e:
        print_result("4. Donor Registration & Pool Directory", False, str(e))

    # 5. Emergency Request Submission & Matching Engine
    req_id = None
    match_id = None
    try:
        req_payload = {
            "patient_name": "Emergency Patient Alex",
            "requester_phone": "+14155550000",
            "hospital_name": "UCSF Medical Center",
            "blood_type": "O-",
            "donation_type": "WHOLE_BLOOD",
            "units_needed": 2,
            "urgency_level": "CRITICAL",
            "latitude": 37.7631,
            "longitude": -122.4578,
            "notes": "Trauma surgery ICU bed 4"
        }
        r = client.post(f"{BASE_URL}/requests/", json=req_payload)
        data = r.json()
        req_id = data.get("request", {}).get("id")
        
        import time
        time.sleep(6) # wait for background task to complete (it has 4 sleeps of 1s each)

        r_status = client.get(f"{BASE_URL}/requests/{req_id}")
        status_data = r_status.json()
        matched_candidates = status_data.get("matches", [])

        if matched_candidates:
            match_id = matched_candidates[0].get("match_id")
            # Extract the correct donor_id from the match to use in later tests
            donor_id = matched_candidates[0].get("donor_id") or matched_candidates[0].get("donor", {}).get("id") or donor_id

        passed = r.status_code == 200 and req_id is not None and len(matched_candidates) >= 1
        print_result("5. Deterministic Hard Filters & Weighted Matching Engine", passed, f"Created Req ID: {req_id}, Matched Candidates: {len(matched_candidates)}")
    except Exception as e:
        print_result("5. Emergency Request Submission & Matching Engine", False, str(e))

    # 6. Request Status & Medical Compliance Audit Trail
    try:
        r_status = client.get(f"{BASE_URL}/requests/{req_id}")
        r_audit = client.get(f"{BASE_URL}/requests/{req_id}/audit")
        passed = r_status.status_code == 200 and r_audit.status_code == 200 and len(r_audit.json()) >= 1
        print_result("6. Medical Compliance & Explainable Audit Log", passed, f"Audit Logs Recorded: {len(r_audit.json())} entries with pass/fail reasons.")
    except Exception as e:
        print_result("6. Medical Compliance & Audit Log", False, str(e))

    # 7. Donor Response Action (1-Tap Accept / Decline)
    try:
        target_match = match_id or f"match-{donor_id}"
        r = client.post(f"{BASE_URL}/donors/respond", json={
            "match_id": target_match,
            "action": "ACCEPTED",
            "eta_minutes": 12,
            "latitude": 37.7749,
            "longitude": -122.4194
        })
        data = r.json()
        updated_status = data.get("match", {}).get("status")
        passed = r.status_code == 200 and updated_status in ("ACCEPTED", "EN_ROUTE")
        print_result("7. Donor Response Action (ACCEPT / EN_ROUTE)", passed, f"Match {target_match} status updated to '{updated_status}'")
    except Exception as e:
        print_result("7. Donor Response Action", False, str(e))

    # 8. Phase 2: Live Donor GPS Radar & Telemetry Stream
    try:
        r = client.post(f"{BASE_URL}/donors/location?donor_id={donor_id}", json={
            "latitude": 37.7680,
            "longitude": -122.4400,
            "speed_kmh": 42.0,
            "request_id": req_id
        })
        data = r.json()
        loc_updates = data.get("location_updates", [])
        passed = r.status_code == 200 and len(loc_updates) >= 1
        first_up = loc_updates[0] if loc_updates else {}
        print_result("8. Phase 2: Live Donor GPS Radar & Dynamic ETA Stream", passed, f"Telemetry: Dist={first_up.get('distance_km')} km, Dynamic ETA={first_up.get('eta_minutes')} mins, Speed={first_up.get('speed_kmh')} km/h")
    except Exception as e:
        print_result("8. Phase 2: Live Donor GPS Radar", False, str(e))

    # 9. Ring Escalation & Voice Call Blast Trigger
    try:
        r = client.post(f"{BASE_URL}/requests/{req_id}/escalate")
        data = r.json()
        passed = r.status_code == 200 and "ring_2_notified_count" in data
        print_result("9. Ring Escalation Engine & Voice Blast", passed, f"Status: {data.get('status')}, Ring 2 Notified: {data.get('ring_2_notified_count')}")
    except Exception as e:
        print_result("9. Ring Escalation Engine", False, str(e))

    # 10. Automated Voice Script Generator & Blood Banks Inventory
    try:
        r_script = client.post(f"{BASE_URL}/ai/voice-script?request_id={req_id}&donor_name=Jane")
        r_banks = client.get(f"{BASE_URL}/hospitals/")
        passed = r_script.status_code == 200 and r_banks.status_code == 200 and len(r_banks.json()) >= 1
        script_str = r_script.json().get("script", "N/A")
        script_snippet = script_str[:30] + "..." if isinstance(script_str, str) else "N/A"
        print_result("10. IVR Voice Agent Script Generator & Blood Banks Directory", passed, f"Blood Banks Count: {len(r_banks.json())}, Voice Script: {script_snippet}")
    except Exception as e:
        print_result("10. Voice Script & Blood Banks Directory", False, str(e))

    print("=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    verify_all_features()
