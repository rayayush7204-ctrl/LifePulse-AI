import asyncio
import httpx
import random
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_e2e_workflow():
    print("Starting E2E Workflow Test...\n")
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. Signup Requester (USER A)
        req_suffix = random.randint(1000, 9999)
        requester_data = {
            "full_name": "Requester Alice",
            "email": f"alice{req_suffix}@test.com",
            "mobile_number": f"123456{req_suffix}",
            "password": "password123"
        }
        res = await client.post("/auth/signup", json=requester_data)
        assert res.status_code == 200, f"Requester signup failed: {res.text}"
        requester_token = res.json()["token"]
        print("[SUCCESS] User A (Requester) signed up.")

        # 2. Signup Donor (USER B)
        don_suffix = random.randint(1000, 9999)
        donor_data = {
            "full_name": "Donor Bob",
            "email": f"bob{don_suffix}@test.com",
            "mobile_number": f"987654{don_suffix}",
            "password": "password123"
        }
        res = await client.post("/auth/signup", json=donor_data)
        assert res.status_code == 200, f"Donor signup failed: {res.text}"
        donor_token = res.json()["token"]
        print("[SUCCESS] User B (Donor) signed up.")

        # 3. Register Donor Profile for User B
        donor_profile_data = {
            "name": "Donor Bob",
            "phone": f"987654{don_suffix}",
            "blood_type": "O-",
            "city": "San Francisco",
            "latitude": 37.7700,
            "longitude": -122.4200,
            "is_active": True,
            "is_available": True
        }
        headers_donor = {"Authorization": f"Bearer {donor_token}"}
        res = await client.post("/donors/", json=donor_profile_data, headers=headers_donor)
        assert res.status_code == 200, f"Donor registration failed: {res.text}"
        donor_id = res.json()["id"]
        print(f"[SUCCESS] User B registered as Donor: {donor_id} (O-, {donor_profile_data['latitude']}, {donor_profile_data['longitude']})")

        # 4. User A requests blood
        emergency_request_data = {
            "patient_name": "Alice Patient",
            "requester_phone": f"123456{req_suffix}",
            "hospital_name": "Emergency Hospital",
            "blood_type": "O-",
            "donation_type": "WHOLE_BLOOD",
            "units_needed": 1,
            "urgency_level": "CRITICAL",
            "latitude": 37.7750,
            "longitude": -122.4190, # very close to donor
            "notes": "Urgent O- needed"
        }
        headers_req = {"Authorization": f"Bearer {requester_token}"}
        res = await client.post("/requests/", json=emergency_request_data, headers=headers_req)
        assert res.status_code == 200, f"Emergency request failed: {res.text}"
        req_id = res.json()["request"]["id"]
        print(f"[SUCCESS] User A requested blood. Request ID: {req_id}")

        # Check matches in the response
        matches = res.json()["matching_summary"]["matched_candidates"]
        bob_match = next((m for m in matches if m.get("donor_id") == donor_id or m.get("donor", {}).get("id") == donor_id), None)
        assert bob_match is not None, "Donor Bob was not matched!"
        match_id = bob_match["match_id"]
        print(f"[SUCCESS] Match created between User A and User B. Match ID: {match_id}")
        print(f"        (Distance: {bob_match.get('distance_km', 'unknown')}km)")
        
        # Verify unmasked data is NOT returned initially (or only partial)
        assert bob_match.get("donor_phone", "").endswith("X") or bob_match.get("donor_phone") == "Consent Required" or "X" in bob_match.get("donor_phone", ""), f"Phone not masked! {bob_match.get('donor_phone')}"
        print("[SUCCESS] Donor phone is properly masked before acceptance.")

        # 5. User B accepts the request
        accept_payload = {
            "match_id": match_id,
            "action": "ACCEPTED",
            "eta_minutes": 15,
            "latitude": 37.7700,
            "longitude": -122.4200
        }
        res = await client.post("/donors/respond", json=accept_payload, headers=headers_donor)
        assert res.status_code == 200, f"Donor acceptance failed: {res.text}"
        print("[SUCCESS] User B Accepted the request.")

        # 6. User A checks request status again
        res = await client.get(f"/requests/{req_id}", headers=headers_req)
        assert res.status_code == 200, f"Get request status failed: {res.text}"
        data = res.json()
        assert data["request"]["status"] == "DONOR_ACCEPTED" or data["request"]["status"] == "FULFILLED", f"Request status not updated: {data['request']['status']}"
        
        updated_matches = data["matches"]
        bob_updated = next(m for m in updated_matches if m["match_id"] == match_id)
        assert bob_updated["status"] == "ACCEPTED", f"Match status not ACCEPTED: {bob_updated['status']}"
        print(f"[SUCCESS] Request status correctly updated to {data['request']['status']}")
        print("[SUCCESS] ALL END-TO-END VERIFICATIONS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_e2e_workflow())
