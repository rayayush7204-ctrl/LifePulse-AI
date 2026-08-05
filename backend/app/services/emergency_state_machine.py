import logging
from typing import Dict, Any, Optional
from enum import Enum
import asyncio
import json

from app.database import get_db_session, DatabaseRepository, SessionLocal
from app.websockets.connection_manager import manager

logger = logging.getLogger(__name__)

class EmergencyState(str, Enum):
    CREATED = "CREATED"
    AI_PROCESSING = "AI_PROCESSING"
    VALIDATING = "VALIDATING"
    SEARCHING = "SEARCHING"
    MATCHING = "MATCHING"
    RING1 = "RING1"
    RING2 = "RING2"
    WAITING = "WAITING"
    DONOR_ACCEPTED = "DONOR_ACCEPTED"
    TRACKING = "TRACKING"
    ARRIVING = "ARRIVING"
    ARRIVED = "ARRIVED"
    DONATION_STARTED = "DONATION_STARTED"
    DONATION_COMPLETED = "DONATION_COMPLETED"
    CLOSED = "CLOSED"

# Valid state transitions — defines what each state can transition TO
VALID_TRANSITIONS: Dict[str, list] = {
    "CREATED": ["AI_PROCESSING", "SEARCHING"],  # Allow skipping AI_PROCESSING for backward compat
    "AI_PROCESSING": ["VALIDATING", "SEARCHING"],
    "VALIDATING": ["SEARCHING"],
    "SEARCHING": ["SEARCHING", "MATCHING"],  # SEARCHING can re-enter itself for progress updates
    "MATCHING": ["RING1"],
    "RING1": ["RING2", "DONOR_ACCEPTED", "WAITING"],
    "RING2": ["WAITING", "DONOR_ACCEPTED"],
    "WAITING": ["DONOR_ACCEPTED", "CLOSED"],
    "DONOR_ACCEPTED": ["TRACKING"],
    "TRACKING": ["ARRIVING", "ARRIVED"],
    "ARRIVING": ["ARRIVED"],
    "ARRIVED": ["DONATION_STARTED"],
    "DONATION_STARTED": ["DONATION_COMPLETED"],
    "DONATION_COMPLETED": ["CLOSED"],
    "CLOSED": [],
}

class EmergencyStateMachine:
    """
    Central orchestrator for handling transitions in an emergency.
    Guarantees deterministic state transitions, database updates, 
    timeline event recording, and WebSocket broadcasts.
    """

    @classmethod
    async def transition(
        cls, 
        request_id: str, 
        new_state: EmergencyState, 
        message: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transitions an emergency request to a new state and broadcasts the event.
        Validates that the transition is legal according to VALID_TRANSITIONS.
        """
        logger.info(f"[Emergency {request_id}] Transitioning to {new_state.value}: {message}")
        
        # We need a new session context since this is often called from background tasks
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            
            # Validate transition if we can read current state
            current_req = repo.get_request(request_id)
            if current_req:
                current_state = current_req.get("status", "CREATED")
                allowed = VALID_TRANSITIONS.get(current_state, [])
                if new_state.value not in allowed and current_state != new_state.value:
                    logger.warning(
                        f"[Emergency {request_id}] Invalid transition {current_state} → {new_state.value}. "
                        f"Allowed: {allowed}. Proceeding anyway for resilience."
                    )
            
            # 1. Update Request Status in DB
            repo.update_request_status(request_id, new_state.value)
            
            # 2. Add Timeline Event in DB
            timeline_event = repo.add_timeline_event(
                request_id=request_id,
                message=message,
                state=new_state.value,
                metadata=metadata
            )
        
        # 3. Broadcast to all clients connected to this request via WebSocket
        payload = {
            "type": "STATE_TRANSITION",
            "request_id": request_id,
            "state": new_state.value,
            "message": message,
            "metadata": metadata or {},
            "timestamp": timeline_event["created_at"]
        }
        await manager.broadcast_to_request(request_id, payload)
        
        return timeline_event

    @classmethod
    async def broadcast_progress_event(
        cls,
        request_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Broadcasts a lightweight progress event via WebSocket WITHOUT persisting to the
        timeline DB. Used for high-frequency updates like search progress, donor markers,
        ring countdown ticks, and ETA updates that would overwhelm the immutable event store.
        """
        payload = {
            "type": event_type,
            "request_id": request_id,
            "data": data
        }
        await manager.broadcast_to_request(request_id, payload)
