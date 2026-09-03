import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

from app.database import get_db_session, get_repository, DatabaseRepository
from app.main import app
from app.models.db_models import EmergencyRequestDB, DonorMatchDB, DonorProfileDB, DonationHistoryDB
from app.services.emergency_state_machine import EmergencyState

@pytest.fixture
def mock_donor_auth_headers():
    return {"Authorization": "Bearer fake-token-for-user1"}

from app.database import SessionLocal, get_repository, DatabaseRepository

@pytest.fixture
def mock_repo_for_donation():
    session = SessionLocal()
    repo = DatabaseRepository(session)
    
    # Mock authentication to bypass JWT check
    async def override_get_current_user():
        return {"id": "user1", "email": "test@example.com"}
    app.dependency_overrides[get_repository] = lambda: repo
    
    yield repo
    
    session.close()

import uuid
from httpx import ASGITransport

@pytest.mark.asyncio
async def test_donation_lifecycle_authorization_failure(mock_repo_for_donation):
    session = mock_repo_for_donation.session
    req_id = str(uuid.uuid4())
    don_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    req = EmergencyRequestDB(id=req_id, blood_type="A+", latitude=0.0, longitude=0.0, status="ARRIVED", location_name="H")
    session.add(req)
    donor = DonorProfileDB(id=don_id, user_id=user_id, name="Wrong Donor", phone=str(uuid.uuid4()), email=f"{uuid.uuid4()}@a.com", blood_type="A+", latitude=0.0, longitude=0.0)
    session.add(donor)
    match = DonorMatchDB(match_id=str(uuid.uuid4()), request_id=req_id, donor_id=don_id, status="ARRIVED")
    session.add(match)
    session.commit()
    
    # Override auth to simulate user1
    async def override_auth(): return {"id": "user1"}
    from app.api.auth import get_current_user_required
    app.dependency_overrides[get_current_user_required] = override_auth
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/donors/{don_id}/emergency/{req_id}/start-donation")
    
    assert res.status_code == 403
    assert "Not authorized" in res.json()["detail"]
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_donation_lifecycle_invalid_transition(mock_repo_for_donation):
    session = mock_repo_for_donation.session
    req_id = str(uuid.uuid4())
    don_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    req = EmergencyRequestDB(id=req_id, blood_type="A+", latitude=0.0, longitude=0.0, status="TRACKING", location_name="H")
    session.add(req)
    donor = DonorProfileDB(id=don_id, user_id=user_id, name="Right Donor", phone=str(uuid.uuid4()), email=f"{uuid.uuid4()}@b.com", blood_type="A+", latitude=0.0, longitude=0.0)
    session.add(donor)
    match = DonorMatchDB(match_id=str(uuid.uuid4()), request_id=req_id, donor_id=don_id, status="EN_ROUTE")
    session.add(match)
    session.commit()
    
    async def override_auth(): return {"id": user_id}
    from app.api.auth import get_current_user_required
    app.dependency_overrides[get_current_user_required] = override_auth
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/donors/{don_id}/emergency/{req_id}/start-donation")
    
    assert res.status_code == 409
    assert "Must be ARRIVED" in res.json()["detail"]
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_donation_lifecycle_success_flow(mock_repo_for_donation):
    session = mock_repo_for_donation.session
    req_id = str(uuid.uuid4())
    don_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    req = EmergencyRequestDB(id=req_id, blood_type="A+", latitude=0.0, longitude=0.0, status="ARRIVED", location_name="H")
    session.add(req)
    donor = DonorProfileDB(id=don_id, user_id=user_id, name="Good Donor", phone=str(uuid.uuid4()), email=f"{uuid.uuid4()}@c.com", blood_type="A+", latitude=0.0, longitude=0.0)
    session.add(donor)
    match = DonorMatchDB(match_id=str(uuid.uuid4()), request_id=req_id, donor_id=don_id, status="ARRIVED")
    session.add(match)
    session.commit()
    
    async def override_auth(): return {"id": user_id}
    from app.api.auth import get_current_user_required
    app.dependency_overrides[get_current_user_required] = override_auth
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Start
        res = await ac.post(f"/api/v1/donors/{don_id}/emergency/{req_id}/start-donation")
        assert res.status_code == 200
        
        session.expire_all()
        # Verify state transitioned
        r_db = session.query(EmergencyRequestDB).filter_by(id=req_id).first()
        assert r_db.status == "DONATION_STARTED"
        
        # Complete
        res2 = await ac.post(f"/api/v1/donors/{don_id}/emergency/{req_id}/complete-donation")
        assert res2.status_code == 200
        
        session.expire_all()
        # Verify final state
        r_db2 = session.query(EmergencyRequestDB).filter_by(id=req_id).first()
        assert r_db2.status == "CLOSED"
        
        # Verify donation history
        history = session.query(DonationHistoryDB).filter_by(donor_id=don_id).first()
        assert history is not None
        assert history.status == "COMPLETED"
        assert history.request_id == req_id
        
        # Verify donor last_donation_date updated
        donor_db = session.query(DonorProfileDB).filter_by(id=don_id).first()
        assert donor_db.last_donation_date == datetime.now(timezone.utc).date()
        
    app.dependency_overrides.clear()
