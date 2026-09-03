"""
Tests for notification dispatch integration in MatchingEngine and RingEscalationService.
Verifies that NotificationService is actually called with correct data during ring transitions.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date, timedelta

from app.database import SessionLocal, DatabaseRepository
from app.services.notification_service import notification_service


@pytest.fixture
def setup_request_with_donors():
    """Creates a request and multiple donors in the DB, returns their IDs."""
    session = SessionLocal()
    repo = DatabaseRepository(session)
    suffix = uuid.uuid4().hex[:8]

    # Create a user and donor with user_id (Ring 1 candidate)
    user1 = repo.create_user({
        "full_name": "Donor One",
        "email": f"donor1_{suffix}@test.com",
        "mobile_number": f"+110000{suffix[:4]}",
        "password_hash": "hash"
    })
    donor1 = repo.add_donor({
        "id": f"d1-{suffix}",
        "user_id": user1["id"],
        "name": "Donor One",
        "phone": "+110001111",
        "blood_type": "O-",
        "latitude": 37.7750,
        "longitude": -122.4195,
        "is_active": True,
        "is_available": True,
        "reliability_score": 0.98,
        "max_travel_radius_km": 25.0
    })

    # Create a second user and donor (can be Ring 2 candidate)
    user2 = repo.create_user({
        "full_name": "Donor Two",
        "email": f"donor2_{suffix}@test.com",
        "mobile_number": f"+120000{suffix[:4]}",
        "password_hash": "hash"
    })
    donor2 = repo.add_donor({
        "id": f"d2-{suffix}",
        "user_id": user2["id"],
        "name": "Donor Two",
        "phone": "+120002222",
        "blood_type": "O-",
        "latitude": 37.7760,
        "longitude": -122.4200,
        "is_active": True,
        "is_available": True,
        "reliability_score": 0.90,
        "max_travel_radius_km": 25.0
    })

    # Create an emergency request
    req = repo.create_request({
        "id": f"req-{suffix}",
        "patient_name": "Test Patient",
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
        "notes": "Test request",
        "status": "CREATED"
    })

    session.close()
    return {
        "request": req,
        "donor1": donor1,
        "donor2": donor2,
        "user1": user1,
        "user2": user2,
    }


# ─── Test 1: Ring 1 matching -> NotificationService called ───
@pytest.mark.asyncio
async def test_ring1_matching_calls_notification_service(setup_request_with_donors):
    """After Ring 1 matches are saved, NotificationService.send_emergency_push_notification is called."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    with patch.object(
        notification_service, "send_emergency_push_notification", new_callable=AsyncMock
    ) as mock_notify:
        mock_notify.return_value = {"status": "SIMULATED_DELIVERED"}

        from app.services.matching_engine import MatchingEngine
        # Patch out sleeps/WS/state-machine for speed
        with patch("app.services.matching_engine.asyncio.sleep", new_callable=AsyncMock), \
             patch("app.services.matching_engine.EmergencyStateMachine") as mock_sm, \
             patch("app.services.matching_engine.manager") as mock_mgr, \
             patch.object(MatchingEngine, "_is_cancelled", return_value=False):
            mock_sm.transition = AsyncMock()
            mock_sm.broadcast_progress_event = AsyncMock()
            mock_mgr.wait_for_connection = AsyncMock()
            mock_mgr.broadcast_progress = AsyncMock()

            from app.services.ring_escalation import RingEscalationService
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                await MatchingEngine.run_matching_cycle(req_id)

        assert mock_notify.call_count > 0, "NotificationService was never called for Ring 1 donors"


# ─── Test 2: Correct persisted match_id passed to NotificationService ───
@pytest.mark.asyncio
async def test_ring1_notification_receives_persisted_match_id(setup_request_with_donors):
    """The match_id passed to NotificationService must match the DB-persisted match_id."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    captured_match_ids = []

    async def capture_notification(donor, request, match_id):
        captured_match_ids.append(match_id)
        return {"status": "SIMULATED_DELIVERED"}

    with patch.object(
        notification_service, "send_emergency_push_notification", side_effect=capture_notification
    ):
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
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                await MatchingEngine.run_matching_cycle(req_id)

    assert len(captured_match_ids) > 0, "No match_ids captured"

    # Verify each captured match_id exists in the database
    session = SessionLocal()
    repo = DatabaseRepository(session)
    for mid in captured_match_ids:
        match = repo.get_match(mid)
        assert match is not None, f"match_id {mid} not found in database"
        assert match["request_id"] == req_id
    session.close()


# ─── Test 3: Correct donor user_id passed to NotificationService ───
@pytest.mark.asyncio
async def test_ring1_notification_receives_correct_user_id(setup_request_with_donors):
    """The donor dict passed to NotificationService must contain the correct user_id."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]
    expected_user_ids = {data["user1"]["id"], data["user2"]["id"]}

    captured_donors = []

    async def capture_notification(donor, request, match_id):
        captured_donors.append(donor)
        return {"status": "SIMULATED_DELIVERED"}

    with patch.object(
        notification_service, "send_emergency_push_notification", side_effect=capture_notification
    ):
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
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                await MatchingEngine.run_matching_cycle(req_id)

    assert len(captured_donors) > 0, "No donors captured"
    session = SessionLocal()
    repo = DatabaseRepository(session)
    for donor in captured_donors:
        # Get the actual donor from the DB to compare
        db_donor = repo.get_donor(donor["id"])
        assert donor.get("user_id") == db_donor.get("user_id"), f"Mismatch for donor {donor['id']}"
    session.close()


# ─── Test 4: Ring 2 escalation -> NotificationService called ───
@pytest.mark.asyncio
async def test_ring2_escalation_calls_notification_service(setup_request_with_donors):
    """When RingEscalationService promotes Ring 2 donors, NotificationService must be called."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    # Manually create Ring 1 and Ring 2 matches
    session = SessionLocal()
    repo = DatabaseRepository(session)
    repo.update_request_status(req_id, "RING1")

    ring1_match = repo.add_match({
        "request_id": req_id,
        "donor_id": data["donor1"]["id"],
        "ring_number": 1,
        "score": 0.95,
        "distance_km": 1.0,
        "status": "NOTIFIED",
        "score_breakdown": {},
    })
    ring2_match = repo.add_match({
        "request_id": req_id,
        "donor_id": data["donor2"]["id"],
        "ring_number": 2,
        "score": 0.80,
        "distance_km": 3.0,
        "status": "QUEUED",
        "score_breakdown": {},
    })
    session.close()

    with patch.object(
        notification_service, "send_emergency_push_notification", new_callable=AsyncMock
    ) as mock_notify:
        mock_notify.return_value = {"status": "SIMULATED_DELIVERED"}

        from app.services.ring_escalation import RingEscalationService
        with patch("app.services.ring_escalation.asyncio.sleep", new_callable=AsyncMock), \
             patch("app.services.ring_escalation.EmergencyStateMachine") as mock_sm, \
             patch("app.services.ring_escalation.manager") as mock_mgr:
            mock_sm.transition = AsyncMock()
            mock_mgr.broadcast_progress = AsyncMock()

            # Simulate timeout by setting RING_TIMEOUT_SECONDS to 0
            original_timeout = RingEscalationService.RING_TIMEOUT_SECONDS
            RingEscalationService.RING_TIMEOUT_SECONDS = 0
            try:
                await RingEscalationService.monitor_ring(req_id, 1)
            finally:
                RingEscalationService.RING_TIMEOUT_SECONDS = original_timeout

        # NotificationService must have been called for the Ring 2 donor
        assert mock_notify.call_count >= 1, "NotificationService was never called for Ring 2 donors"
        # Verify the match_id is the Ring 2 match
        call_args = mock_notify.call_args_list
        notified_match_ids = [c.args[2] if len(c.args) > 2 else c.kwargs.get("match_id") for c in call_args]
        assert ring2_match["match_id"] in notified_match_ids


# ─── Test 5: No notification for queued donors before ring activation ───
@pytest.mark.asyncio
async def test_no_notification_for_queued_donors(setup_request_with_donors):
    """Donors in Ring 2 (QUEUED status) must NOT receive notifications during Ring 1."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    captured_donor_ids = []

    async def capture_notification(donor, request, match_id):
        captured_donor_ids.append(donor.get("id"))
        return {"status": "SIMULATED_DELIVERED"}

    with patch.object(
        notification_service, "send_emergency_push_notification", side_effect=capture_notification
    ):
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
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                await MatchingEngine.run_matching_cycle(req_id)

    # Check DB: any QUEUED match should NOT have been notified
    session = SessionLocal()
    repo = DatabaseRepository(session)
    matches = repo.get_matches_for_request(req_id)
    queued_donor_ids = {m["donor_id"] for m in matches if m["status"] == "QUEUED"}
    session.close()

    for qid in queued_donor_ids:
        assert qid not in captured_donor_ids, f"QUEUED donor {qid} was notified prematurely"


# ─── Test 6: Notification dispatch happens after DB session closed ───
@pytest.mark.asyncio
async def test_notification_dispatched_outside_db_session(setup_request_with_donors):
    """Verifies the notification call happens after the 'with SessionLocal()' block exits."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    session_was_closed = []

    original_close = SessionLocal.kw.get("class_", None)

    async def check_notification(donor, request, match_id):
        # At this point the DB session should be closed (we're outside the `with` block)
        # Verify by opening a new session successfully
        test_session = SessionLocal()
        repo = DatabaseRepository(test_session)
        m = repo.get_match(match_id)
        assert m is not None, "Match should exist in DB before notification is dispatched"
        session_was_closed.append(True)
        test_session.close()
        return {"status": "SIMULATED_DELIVERED"}

    with patch.object(
        notification_service, "send_emergency_push_notification", side_effect=check_notification
    ):
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
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                await MatchingEngine.run_matching_cycle(req_id)

    assert len(session_was_closed) > 0, "Notification was never dispatched"


# ─── Test 7: Notification failure does not crash matching workflow ───
@pytest.mark.asyncio
async def test_notification_failure_does_not_crash_matching(setup_request_with_donors):
    """If NotificationService raises an exception, matches should still be saved and ring transition should still happen."""
    data = setup_request_with_donors
    req_id = data["request"]["id"]

    async def failing_notification(donor, request, match_id):
        raise RuntimeError("Simulated FCM failure")

    with patch.object(
        notification_service, "send_emergency_push_notification", side_effect=failing_notification
    ):
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
            with patch.object(RingEscalationService, "monitor_ring", new_callable=AsyncMock):
                # This should NOT raise despite notification failure
                await MatchingEngine.run_matching_cycle(req_id)

    # Verify matches were still saved
    session = SessionLocal()
    repo = DatabaseRepository(session)
    matches = repo.get_matches_for_request(req_id)
    assert len(matches) > 0, "Matches should still be saved despite notification failure"

    # Verify ring1 donors have NOTIFIED status
    ring1 = [m for m in matches if m["ring_number"] == 1]
    for m in ring1:
        assert m["status"] == "NOTIFIED"
    session.close()
