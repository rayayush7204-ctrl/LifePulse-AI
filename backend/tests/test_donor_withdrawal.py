import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import SessionLocal, DatabaseRepository
from sqlalchemy import text
from app.services.emergency_state_machine import EmergencyState

TEST_DONOR_USER = {
    "email": "donorwithdraw@example.com",
    "password": "securepassword123",
    "full_name": "Withdraw Tester",
    "mobile_number": "+14155550011"
}

TEST_OTHER_USER = {
    "email": "otherdonor@example.com",
    "password": "securepassword123",
    "full_name": "Other Donor Tester",
    "mobile_number": "+14155550012"
}

async def _get_auth_headers(ac: AsyncClient, user_data: dict) -> dict:
    reg_resp = await ac.post("/api/v1/auth/signup", json=user_data)
    if reg_resp.status_code not in (200, 201, 400):
        raise Exception(f"Register failed: {reg_resp.status_code} - {reg_resp.json()}")
    resp = await ac.post("/api/v1/auth/login", json={
        "email_or_mobile": user_data["email"],
        "password": user_data["password"]
    })
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}

async def _create_active_request(ac: AsyncClient, headers: dict) -> str:
    payload = {
        "blood_type": "O-",
        "units_needed": 2,
        "hospital_name": "Test Hospital",
        "urgency_level": "CRITICAL",
        "latitude": 37.7749,
        "longitude": -122.4194
    }
    response = await ac.post("/api/v1/requests/", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()["request"]["id"]

async def _setup_donor(ac: AsyncClient, headers: dict) -> str:
    payload = {
        "name": "Withdraw Tester",
        "phone": "+14155550011",
        "blood_type": "O-",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "is_active": True,
        "is_available": True
    }
    resp = await ac.post("/api/v1/donors/", json=payload, headers=headers)
    assert resp.status_code == 200
    return resp.json()["id"]

def _create_match_in_db(req_id: str, donor_id: str, status: str = "ACCEPTED") -> str:
    with SessionLocal() as session:
        repo = DatabaseRepository(session)
        match = repo.add_match({
            "request_id": req_id,
            "donor_id": donor_id,
            "status": status,
            "distance_km": 1.5,
            "score": 0.95
        })
        # Set request state to DONOR_ACCEPTED to simulate actual matching state
        if status in ["ACCEPTED", "EN_ROUTE", "ARRIVED"]:
            session.execute(
                text("UPDATE emergency_requests SET status = 'DONOR_ACCEPTED' WHERE id = :id"),
                {"id": req_id}
            )
            session.commit()
        return match["match_id"]


@pytest.mark.asyncio
async def test_successful_withdrawal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_DONOR_USER)
        req_id = await _create_active_request(ac, headers)
        donor_id = await _setup_donor(ac, headers)
        
        match_id = _create_match_in_db(req_id, donor_id, "ACCEPTED")

        response = await ac.patch(f"/api/v1/donors/matches/{match_id}/withdraw", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "WITHDRAWN"

        with SessionLocal() as session:
            db_req = session.execute(
                text("SELECT status FROM emergency_requests WHERE id = :id"),
                {"id": req_id}
            ).fetchone()
            assert db_req[0] == "MATCHING"

            db_match = session.execute(
                text("SELECT status FROM donor_matches WHERE match_id = :mid"),
                {"mid": match_id}
            ).fetchone()
            assert db_match[0] == "WITHDRAWN"


@pytest.mark.asyncio
async def test_unauthorized_withdrawal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_DONOR_USER)
        other_headers = await _get_auth_headers(ac, TEST_OTHER_USER)
        req_id = await _create_active_request(ac, headers)
        donor_id = await _setup_donor(ac, headers)
        await _setup_donor(ac, other_headers)
        
        match_id = _create_match_in_db(req_id, donor_id, "ACCEPTED")

        response = await ac.patch(f"/api/v1/donors/matches/{match_id}/withdraw", headers=other_headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_invalid_state_withdrawal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_DONOR_USER)
        req_id = await _create_active_request(ac, headers)
        donor_id = await _setup_donor(ac, headers)
        
        match_id = _create_match_in_db(req_id, donor_id, "DONATION_STARTED")

        response = await ac.patch(f"/api/v1/donors/matches/{match_id}/withdraw", headers=headers)
        assert response.status_code == 400
        assert "Cannot withdraw after donation has started" in response.json()["detail"]
