import pytest
import asyncio
from app.services.notification_service import NotificationService

@pytest.mark.asyncio
async def test_emergency_push_notification_payload_types():
    """
    Test that the NotificationService constructs the FCM data payload with ALL expected strings.
    This guarantees no React Error Boundary crashes occur due to missing locations,
    and Firebase won't reject the push for non-string values.
    """
    service = NotificationService()
    
    donor = {
        "id": "donor123",
        "phone": "+15550000000",
        "user_id": "user123"
    }
    
    request = {
        "id": "req-999",
        "blood_type": "A+",
        "location_name": "General Hospital",
        "location_address": "123 Main St",
        "latitude": 37.7749,  # float
        "longitude": -122.4194, # float
        "units_needed": 3,    # int
        "urgency_level": "CRITICAL"
    }
    
    match_id = "match-abc"
    
    # Send notification (this will simulate if FCM is not configured, returning the payload)
    result = await service.send_emergency_push_notification(donor, request, match_id)
    
    # We inspect the sent log since `send_emergency_push_notification` appends to `service.sent_log`
    assert len(service.sent_log) == 1
    payload = service.sent_log[0]
    
    data = payload["data"]
    
    # Assert existence
    assert "location_name" in data
    assert "location_address" in data
    assert "latitude" in data
    assert "longitude" in data
    assert "units" in data
    assert "urgency_level" in data
    
    # Assert old fields intact
    assert "location" in data
    assert "urgency" in data
    assert "request_id" in data
    assert "match_id" in data
    assert "type" in data
    
    # Assert everything is a string
    for key, value in data.items():
        assert isinstance(value, str), f"Field {key} must be a string, got {type(value)}"
    
    assert data["latitude"] == "37.7749"
    assert data["longitude"] == "-122.4194"
    assert data["units"] == "3"
    assert data["location_name"] == "General Hospital"

@pytest.mark.asyncio
async def test_emergency_push_notification_payload_missing_coordinates():
    """
    Test that if coordinates are missing, they are safely stringified as 'None' 
    without crashing the service.
    """
    service = NotificationService()
    donor = {"id": "d1"}
    request = {
        "id": "req-1",
        "blood_type": "B+",
        # Notice missing latitude/longitude
    }
    
    result = await service.send_emergency_push_notification(donor, request, "m1")
    
    payload = service.sent_log[0]
    data = payload["data"]
    
    assert data["latitude"] == "None"
    assert data["longitude"] == "None"
    assert isinstance(data["latitude"], str)
