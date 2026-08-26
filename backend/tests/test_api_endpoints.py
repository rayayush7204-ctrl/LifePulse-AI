"""
Integration Test Suite for FastAPI Endpoints.
Tests emergency request submission, donor matching, status updates, escalation, and audit trail.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import DatabaseRepository, SessionLocal

@pytest.mark.asyncio
async def test_full_emergency_request_flow():
    # Pre-populate 1 donor
    session = SessionLocal()
    repo = DatabaseRepository(session)
    repo.add_donor({
        "id": "donor-test-01",
        "name": "Alex Smith",
        "phone": "+14155550199",
        "blood_type": "O-",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True
    })
    session.commit()
    session.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Submit Request
        req_payload = {
            "patient_name": "Test Patient",
            "requester_phone": "+14155550999",
            "hospital_name": "SF General Hospital",
            "blood_type": "O-",
            "donation_type": "WHOLE_BLOOD",
            "units_needed": 1,
            "urgency_level": "CRITICAL",
            "latitude": 37.7750,
            "longitude": -122.4195,
            "notes": "Surgery ICU"
        }
        res = await ac.post("/api/v1/requests/", json=req_payload)
        assert res.status_code == 200
        data = res.json()
        req_id = data["request"]["id"]
        # The engine runs asynchronously; initial count is 0
        assert data["matching_summary"]["eligible_count"] == 0

        # 2. Wait and Poll for Request Status
        import asyncio
        matches = []
        for _ in range(40):  # Poll up to 20 seconds (wait_for_connection + cinematic sleeps)
            status_res = await ac.get(f"/api/v1/requests/{req_id}")
            assert status_res.status_code == 200
            matches = status_res.json()["matches"]
            if len(matches) >= 1:
                break
            await asyncio.sleep(0.5)
            
        assert len(matches) >= 1, "Matching engine did not find matches in time."
        match_id = matches[0]["match_id"]

        # 3. Donor Accepts Match
        respond_res = await ac.post("/api/v1/donors/respond", json={
            "match_id": match_id,
            "action": "ACCEPTED",
            "eta_minutes": 15
        })
        assert respond_res.status_code == 200
        assert respond_res.json()["match"]["status"] == "ACCEPTED"

        # 4. Wait for Simulation to complete (Terminal state is CLOSED)
        for _ in range(20):  # Poll up to 10 seconds for simulation to finish
            check_res = await ac.get(f"/api/v1/requests/{req_id}")
            if check_res.json()["request"]["status"] == "CLOSED":
                break
            await asyncio.sleep(0.5)
        
        assert check_res.json()["request"]["status"] == "CLOSED"

        # 5. Check Audit Trail
        audit_res = await ac.get(f"/api/v1/requests/{req_id}/audit")
        assert audit_res.status_code == 200
        assert len(audit_res.json()) >= 1

@pytest.mark.asyncio
async def test_ai_parse_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/ai/parse-request", json={
            "text": "Urgent! Need 2 bags B positive blood at Manipal Hospital!"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["blood_type"] == "B+"
        assert data["units_needed"] == 2

@pytest.mark.asyncio
async def test_voice_sos_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/ai/voice-sos", json={
            "transcript": "Urgent! Need 3 bags of O negative blood at UCSF hospital immediately!"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["blood_type"] == "O-"
        assert data["units_needed"] == 3
        assert data["is_voice_sos"] is True

@pytest.mark.asyncio
async def test_donor_location_update_and_gps_radar():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Update location for donor
        res = await ac.post("/api/v1/donors/location?donor_id=donor-test-01", json={
            "latitude": 37.7700,
            "longitude": -122.4200,
            "speed_kmh": 40.0
        })
@pytest.mark.asyncio
async def test_emergency_request_normalization_and_fail_open():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "patient_name": "",
            "requester_phone": "",
            "hospital_name": "",
            "blood_type": "o negative",  # non-standard string
            "donation_type": "whole blood",
            "units_needed": "3",         # stringified int
            "urgency_level": "CRITICAL",
            "latitude": "37.7631",       # stringified float
            "longitude": "-122.4578",
            "notes": "Test normalizing non-standard request inputs"
        }
        res = await ac.post("/api/v1/requests/", json=req_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["request"]["blood_type"] == "O-"
        assert data["request"]["units_needed"] == 3
        assert data["request"]["patient_name"] == "Emergency Patient"


