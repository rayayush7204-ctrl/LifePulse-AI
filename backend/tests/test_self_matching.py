"""
Tests for self-matching exclusion in MatchingEngine.
Verifies that a requester is not matched to their own emergency request.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import uuid
from unittest.mock import patch, AsyncMock

from app.database import SessionLocal, DatabaseRepository

@pytest.fixture
def setup_requester_and_donor():
    """Creates a user with a donor profile and a request."""
    session = SessionLocal()
    repo = DatabaseRepository(session)
    suffix = uuid.uuid4().hex[:8]

    # Create the requester user
    user1 = repo.create_user({
        "full_name": "Self Matcher",
        "email": f"self_{suffix}@test.com",
        "mobile_number": f"+110000{suffix[:4]}",
        "password_hash": "hash"
    })
    
    # Create donor profile for the requester user
    donor1 = repo.add_donor({
        "id": f"d1-{suffix}",
        "user_id": user1["id"],
        "name": "Self Matcher",
        "phone": "+110001111",
        "blood_type": "O-",
        "latitude": 37.7750,
        "longitude": -122.4195,
        "is_active": True,
        "is_available": True,
        "reliability_score": 0.98,
        "max_travel_radius_km": 25.0
    })

    # Create an emergency request BY this user
    req_self = repo.create_request({
        "id": f"req-self-{suffix}",
        "requester_user_id": user1["id"],
        "patient_name": "Myself",
        "requester_phone": "+19999999999",
        "location_name": "Test Hospital",
        "location_address": "123 Test St",
        "location_source": "gps",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "status": "CREATED"
    })

    # Create an emergency request BY an anonymous user
    req_anon = repo.create_request({
        "id": f"req-anon-{suffix}",
        "requester_user_id": None,
        "patient_name": "Anonymous",
        "requester_phone": "+19999999998",
        "location_name": "Test Hospital",
        "location_address": "123 Test St",
        "location_source": "gps",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "status": "CREATED"
    })

    # Create another user's request
    user2 = repo.create_user({
        "full_name": "Other User",
        "email": f"other_{suffix}@test.com",
        "mobile_number": f"+120000{suffix[:4]}",
        "password_hash": "hash"
    })
    req_other = repo.create_request({
        "id": f"req-other-{suffix}",
        "requester_user_id": user2["id"],
        "patient_name": "Other Person",
        "requester_phone": "+19999999997",
        "location_name": "Test Hospital",
        "location_address": "123 Test St",
        "location_source": "gps",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "status": "CREATED"
    })

    session.close()
    return {
        "user1": user1,
        "donor1": donor1,
        "req_self": req_self,
        "req_anon": req_anon,
        "req_other": req_other
    }


@pytest.mark.asyncio
async def test_self_matching_excluded(setup_requester_and_donor):
    """A requester who also has a donor profile is never matched to their own emergency."""
    data = setup_requester_and_donor
    req_id = data["req_self"]["id"]
    donor_id = data["donor1"]["id"]

    from app.services.matching_engine import MatchingEngine
    
    with patch("app.services.matching_engine.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.matching_engine.EmergencyStateMachine") as mock_sm, \
         patch("app.services.matching_engine.manager") as mock_mgr, \
         patch.object(MatchingEngine, "_is_cancelled", return_value=False):
        
        mock_sm.transition = AsyncMock()
        mock_sm.broadcast_progress_event = AsyncMock()
        mock_mgr.wait_for_connection = AsyncMock()
        mock_mgr.broadcast_progress = AsyncMock()
        
        from app.services.ring_escalation import RingEscalationService
        with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock), \
             patch("app.services.notification_service.notification_service.send_emergency_push_notification", new_callable=AsyncMock):
            
            await MatchingEngine.run_matching_cycle(req_id)

    # Verify the donor was NOT matched
    session = SessionLocal()
    repo = DatabaseRepository(session)
    matches = repo.get_matches_for_request(req_id)
    session.close()

    matched_donor_ids = [m["donor_id"] for m in matches]
    assert donor_id not in matched_donor_ids, "Requester's donor profile should be excluded from their own request."


@pytest.mark.asyncio
async def test_other_user_matching_included(setup_requester_and_donor):
    """A requester-owned donor CAN be matched to another user's emergency."""
    data = setup_requester_and_donor
    req_id = data["req_other"]["id"]
    donor_id = data["donor1"]["id"]

    from app.services.matching_engine import MatchingEngine
    
    with patch("app.services.matching_engine.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.matching_engine.EmergencyStateMachine") as mock_sm, \
         patch("app.services.matching_engine.manager") as mock_mgr, \
         patch.object(MatchingEngine, "_is_cancelled", return_value=False):
        
        mock_sm.transition = AsyncMock()
        mock_sm.broadcast_progress_event = AsyncMock()
        mock_mgr.wait_for_connection = AsyncMock()
        mock_mgr.broadcast_progress = AsyncMock()
        
        from app.services.ring_escalation import RingEscalationService
        with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock), \
             patch("app.services.notification_service.notification_service.send_emergency_push_notification", new_callable=AsyncMock):
            
            await MatchingEngine.run_matching_cycle(req_id)

    # Verify the donor WAS matched
    session = SessionLocal()
    repo = DatabaseRepository(session)
    matches = repo.get_matches_for_request(req_id)
    session.close()

    matched_donor_ids = [m["donor_id"] for m in matches]
    assert donor_id in matched_donor_ids, "Donor profile should be included for other users' requests."


@pytest.mark.asyncio
async def test_anonymous_request_included(setup_requester_and_donor):
    """An anonymous request (requester_user_id is None) does not falsely exclude donors."""
    data = setup_requester_and_donor
    req_id = data["req_anon"]["id"]
    donor_id = data["donor1"]["id"]

    from app.services.matching_engine import MatchingEngine
    
    with patch("app.services.matching_engine.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.matching_engine.EmergencyStateMachine") as mock_sm, \
         patch("app.services.matching_engine.manager") as mock_mgr, \
         patch.object(MatchingEngine, "_is_cancelled", return_value=False):
        
        mock_sm.transition = AsyncMock()
        mock_sm.broadcast_progress_event = AsyncMock()
        mock_mgr.wait_for_connection = AsyncMock()
        mock_mgr.broadcast_progress = AsyncMock()
        
        from app.services.ring_escalation import RingEscalationService
        with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock), \
             patch("app.services.notification_service.notification_service.send_emergency_push_notification", new_callable=AsyncMock):
            
            await MatchingEngine.run_matching_cycle(req_id)

    # Verify the donor WAS matched
    session = SessionLocal()
    repo = DatabaseRepository(session)
    matches = repo.get_matches_for_request(req_id)
    session.close()

    matched_donor_ids = [m["donor_id"] for m in matches]
    assert donor_id in matched_donor_ids, "Donor profile should be included for anonymous requests."
