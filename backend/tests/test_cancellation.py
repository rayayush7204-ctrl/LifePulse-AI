import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import MatchStatusEnum
from app.database import SessionLocal, DatabaseRepository
from app.services.matching_engine import MatchingEngine

# Test data
TEST_USER = {
    "email": "canceltest@example.com",
    "password": "securepassword123",
    "full_name": "Cancel Tester",
    "mobile_number": "+14155550001"
}

TEST_OTHER_USER = {
    "email": "otheruser@example.com",
    "password": "securepassword123",
    "full_name": "Other Tester",
    "mobile_number": "+14155550002"
}

async def _get_auth_headers(ac: AsyncClient, user_data: dict) -> dict:
    """Helper to register and login a user, returning auth headers."""
    # Register (ignore if already exists)
    reg_resp = await ac.post("/api/v1/auth/signup", json=user_data)
    if reg_resp.status_code not in (200, 201, 400):
        raise Exception(f"Register failed: {reg_resp.status_code} - {reg_resp.json()}")
    elif reg_resp.status_code == 400 and "already exists" not in reg_resp.json().get("detail", "").lower():
        raise Exception(f"Register failed with unexpected 400: {reg_resp.json()}")
    # Login
    resp = await ac.post("/api/v1/auth/login", json={
        "email_or_mobile": user_data["email"],
        "password": user_data["password"]
    })
    
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.status_code} - {resp.json()}")
        
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


@pytest.mark.asyncio
async def test_successful_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        req_id = await _create_active_request(ac, headers)

        # Cancel the request
        response = await ac.patch(f"/api/v1/requests/{req_id}/cancel", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "CANCELLED"
        assert data["request_id"] == req_id

        # Verify status in database
        with SessionLocal() as session:
            db_req = session.execute(
                text("SELECT status FROM emergency_requests WHERE id = :id"),
                {"id": req_id}
            ).fetchone()
            assert db_req[0] == "CANCELLED"


@pytest.mark.asyncio
async def test_unauthorized_user_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        other_headers = await _get_auth_headers(ac, TEST_OTHER_USER)
        req_id = await _create_active_request(ac, headers)

        # Attempt to cancel with a different user
        response = await ac.patch(f"/api/v1/requests/{req_id}/cancel", headers=other_headers)
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_legacy_request_authorization():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        
        # Create a legacy request (no requester_user_id) by skipping auth headers
        payload = {
            "blood_type": "A+",
            "units_needed": 1,
            "hospital_name": "Legacy Hospital",
            "urgency_level": "HIGH",
            "latitude": 37.0,
            "longitude": -122.0
        }
        create_response = await ac.post("/api/v1/requests/", json=payload)
        assert create_response.status_code == 200
        legacy_request_id = create_response.json()["request"]["id"]

        # Try to cancel it with a regular authenticated user
        cancel_response = await ac.patch(f"/api/v1/requests/{legacy_request_id}/cancel", headers=headers)
        assert cancel_response.status_code == 403
        assert "no registered owner" in cancel_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_nonexistent_request_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        response = await ac.patch("/api/v1/requests/nonexistent-id/cancel", headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_terminal_request_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        req_id = await _create_active_request(ac, headers)

        # Force the request to a terminal state
        with SessionLocal() as session:
            session.execute(
                text("UPDATE emergency_requests SET status = 'CLOSED' WHERE id = :id"),
                {"id": req_id}
            )
            session.commit()

        # Attempt to cancel
        response = await ac.patch(f"/api/v1/requests/{req_id}/cancel", headers=headers)
        assert response.status_code == 409
        assert "cannot be cancelled" in response.json()["detail"].lower()


from sqlalchemy import text

@pytest.mark.asyncio
async def test_cancellation_during_active_matching():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        req_id = await _create_active_request(ac, headers)

        # Verify the matching engine stops processing
        # Create the task without awaiting it immediately
        matching_task = asyncio.create_task(MatchingEngine.run_matching_cycle(req_id))
        
        # Cancel it quickly before AI_PROCESSING is done
        await asyncio.sleep(0.2) 
        
        # Simulate DB cancel (bypassing route for direct async test)
        with SessionLocal() as session:
            session.execute(
                text("UPDATE emergency_requests SET status = 'CANCELLED' WHERE id = :id"),
                {"id": req_id}
            )
            session.commit()

        # Wait for engine to finish
        await matching_task
        
        # It should have aborted and NOT created match records or escalated to RING1
        with SessionLocal() as session:
            db_req = session.execute(
                text("SELECT status FROM emergency_requests WHERE id = :id"),
                {"id": req_id}
            ).fetchone()
            assert db_req[0] == "CANCELLED" # Status remains CANCELLED, not overwritten

            matches_count = session.execute(
                text("SELECT count(*) FROM donor_matches WHERE request_id = :id"),
                {"id": req_id}
            ).fetchone()[0]
            assert matches_count == 0


@pytest.mark.asyncio
async def test_pending_match_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        req_id = await _create_active_request(ac, headers)

        with SessionLocal() as session:
            # Setup some fake matches in various states
            import uuid
            unique_suffix = uuid.uuid4().hex[:8]
            donor_id = f"test-donor-{unique_suffix}"
            profile_id = f"profile-{unique_suffix}"
            session.execute(
                text("INSERT INTO donor_profiles (id, user_id, name, phone, blood_type, latitude, longitude, is_available) VALUES (:did, :uid, :name, :phone, :bt, :lat, :lon, 1)"),
                {"did": profile_id, "uid": donor_id, "name": "Test Donor", "phone": "+14155550000", "bt": "O-", "lat": 37.0, "lon": -122.0}
            )
            
            statuses = ["QUEUED", "NOTIFIED", "VIEWED", "ACCEPTED", "DECLINED"]
            match_ids = []
            for i, st in enumerate(statuses):
                match_uuid = uuid.uuid4().hex[:8]
                match_id = f"match-{match_uuid}"
                match_ids.append(match_id)
                session.execute(
                    text("INSERT INTO donor_matches (id, match_id, request_id, donor_id, status) VALUES (:id, :mid, :req, :don, :st)"),
                    {"id": f"dm-{match_uuid}", "mid": match_id, "req": req_id, "don": donor_id, "st": st}
                )
            session.commit()

        # Cancel the request
        response = await ac.patch(f"/api/v1/requests/{req_id}/cancel", headers=headers)
        assert response.status_code == 200
        
        # Verify matches in DB
        with SessionLocal() as session:
            updated_matches = session.execute(
                text("SELECT match_id, status FROM donor_matches WHERE request_id = :id"),
                {"id": req_id}
            ).fetchall()
            
            status_map = {m[0]: m[1] for m in updated_matches}
            
            # Actionable ones should be CANCELLED
            assert status_map[match_ids[0]] == "CANCELLED" # QUEUED -> CANCELLED
            assert status_map[match_ids[1]] == "CANCELLED" # NOTIFIED -> CANCELLED
            assert status_map[match_ids[2]] == "CANCELLED" # VIEWED -> CANCELLED
            
            # Historical ones should be preserved
            assert status_map[match_ids[3]] == "ACCEPTED"
            assert status_map[match_ids[4]] == "DECLINED"


@pytest.mark.asyncio
async def test_websocket_cancellation_event():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    # We must use TestClient for websocket connections, but we need auth token first
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac, TEST_USER)
        req_id = await _create_active_request(ac, headers)

    # Connect websocket to listen for the event
    with client.websocket_connect(f"/ws/requests/{req_id}?token={headers['Authorization'].split(' ')[1]}") as ws:
        # Perform cancel using the TestClient since we are in a synchronous block with ws
        response = client.patch(f"/api/v1/requests/{req_id}/cancel", headers=headers)
        assert response.status_code == 200
        
        # Read messages until we get REQUEST_CANCELLED
        found_cancel_event = False
        for _ in range(10): # Wait for up to 10 messages
            try:
                msg = ws.receive_json()
                if msg.get("type") == "REQUEST_CANCELLED":
                    found_cancel_event = True
                    assert msg["new_status"] == "CANCELLED"
                    break
            except Exception:
                pass
        
        assert found_cancel_event
