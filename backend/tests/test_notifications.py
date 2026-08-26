import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_repository, DatabaseRepository, SessionLocal
from app.services.notification_service import notification_service
import firebase_admin
from firebase_admin import messaging
import uuid

@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch):
    """Mocks Firebase Admin SDK to prevent actual network calls during tests."""
    mock_app = MagicMock()
    monkeypatch.setattr(notification_service, "fcm_app", mock_app)
    
    mock_send = MagicMock()
    # By default, pretend success
    success_response = MagicMock()
    success_response.success_count = 1
    success_response.failure_count = 0
    success_response.responses = [MagicMock(success=True)]
    mock_send.return_value = success_response
    
    monkeypatch.setattr(messaging, "send_each_for_multicast", mock_send)
    return mock_send

@pytest.mark.asyncio
async def test_register_device_token():
    session = SessionLocal()
    repo = DatabaseRepository(session)
    unique_suffix = uuid.uuid4().hex[:8]
    user = repo.create_user({
        "full_name": "Test User",
        "email": f"testfcm2_{unique_suffix}@example.com",
        "mobile_number": f"+1234567{unique_suffix[:4]}",
        "password_hash": "hash"
    })
    
    # Mock authentication
    app.dependency_overrides[get_repository] = lambda: DatabaseRepository(SessionLocal())
    
    from app.api.auth import get_current_user_required
    app.dependency_overrides[get_current_user_required] = lambda: user
    
    token = f"test-token-{uuid.uuid4().hex[:8]}"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/notifications/device-token",
            json={"token": token, "platform": "web"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Register same token again (idempotent)
        response = await ac.post(
            "/api/v1/notifications/device-token",
            json={"token": token, "platform": "web"}
        )
        assert response.status_code == 200
    
    app.dependency_overrides.clear()
    
    # Verify in DB
    session = SessionLocal()
    repo = DatabaseRepository(session)
    tokens = repo.get_user_tokens(user["id"])
    assert token in tokens

@pytest.mark.asyncio
async def test_fcm_send_success(mock_firebase):
    session = SessionLocal()
    repo = DatabaseRepository(session)
    unique_suffix = uuid.uuid4().hex[:8]
    user = repo.create_user({
        "full_name": "Test User 2",
        "email": f"testfcm3_{unique_suffix}@example.com",
        "mobile_number": f"+1234568{unique_suffix[:4]}",
        "password_hash": "hash"
    })
    token = f"valid-token-{unique_suffix}"
    repo.add_device_token(user["id"], token)
    
    donor = {"id": "d-123", "user_id": user["id"], "phone": "+123", "name": "Test Donor"}
    request = {"id": "r-123", "blood_type": "O+", "hospital_name": "UCSF", "urgency_level": "CRITICAL"}
    
    res = await notification_service.send_emergency_push_notification(donor, request, "m-123")
    assert res["status"] == "SENT"
    mock_firebase.assert_called_once()
    
    # Verify notification record was created
    from app.models.db_models import NotificationRecordDB
    records = session.query(NotificationRecordDB).filter_by(user_id=user["id"]).all()
    assert len(records) == 1
    assert records[0].status == "SENT"

@pytest.mark.asyncio
async def test_fcm_send_invalid_token_cleanup(mock_firebase):
    session = SessionLocal()
    repo = DatabaseRepository(session)
    unique_suffix = uuid.uuid4().hex[:8]
    user = repo.create_user({
        "full_name": "Test User 3",
        "email": f"testfcm4_{unique_suffix}@example.com",
        "mobile_number": f"+1234569{unique_suffix[:4]}",
        "password_hash": "hash"
    })
    token = f"invalid-token-{unique_suffix}"
    repo.add_device_token(user["id"], token)
    
    # Mock failure with UnregisteredError
    failure_response = MagicMock()
    failure_response.success_count = 0
    failure_response.failure_count = 1
    
    resp_obj = MagicMock()
    resp_obj.success = False
    resp_obj.exception = messaging.UnregisteredError("Unregistered")
    failure_response.responses = [resp_obj]
    
    mock_firebase.return_value = failure_response
    
    donor = {"id": "d-123", "user_id": user["id"], "phone": "+123", "name": "Test Donor"}
    request = {"id": "r-123", "blood_type": "O+", "hospital_name": "UCSF"}
    
    res = await notification_service.send_emergency_push_notification(donor, request, "m-123")
    assert res["status"] == "FAILED"
    
    # Verify token was removed
    session = SessionLocal()
    repo = DatabaseRepository(session)
    tokens = repo.get_user_tokens(user["id"])
    assert token not in tokens
    
@pytest.mark.asyncio
async def test_fcm_not_configured(monkeypatch):
    monkeypatch.setattr(notification_service, "fcm_app", None)
    
    session = SessionLocal()
    repo = DatabaseRepository(session)
    unique_suffix = uuid.uuid4().hex[:8]
    user = repo.create_user({
        "full_name": "Test User 4",
        "email": f"testfcm5_{unique_suffix}@example.com",
        "mobile_number": f"+1234560{unique_suffix[:4]}",
        "password_hash": "hash"
    })
    token = f"valid-token-{unique_suffix}"
    repo.add_device_token(user["id"], token)
    
    donor = {"id": "d-123", "user_id": user["id"], "phone": "+123", "name": "Test Donor"}
    request = {"id": "r-123", "blood_type": "O+", "hospital_name": "UCSF"}
    
    res = await notification_service.send_emergency_push_notification(donor, request, "m-123")
    assert res["status"] == "SIMULATED_DELIVERED"
