import logging
import asyncio
from typing import Dict, Any

from app.database import SessionLocal, DatabaseRepository
from app.services.emergency_state_machine import EmergencyStateMachine, EmergencyState
from app.websockets.connection_manager import manager, WSEventType

logger = logging.getLogger(__name__)

class RingEscalationService:
    """
    Handles escalating through donor rings if nobody accepts within the timeout.
    Broadcasts countdown ticks every 5 seconds so the frontend can show a live timer.
    """
    
    RING_TIMEOUT_SECONDS = 45
    COUNTDOWN_TICK_INTERVAL = 5  # Broadcast countdown every 5 seconds

    @classmethod
    async def monitor_ring(cls, request_id: str, current_ring: int):
        """
        Waits for RING_TIMEOUT_SECONDS. If the state is still RINGX, 
        it escalates to the next ring.
        Broadcasts countdown ticks every COUNTDOWN_TICK_INTERVAL seconds.
        """
        logger.info(f"Monitoring Ring {current_ring} for Request {request_id}")
        
        donors_viewing = 0  # Simulated: track how many donors have "viewed" the request
        
        for seconds_elapsed in range(cls.RING_TIMEOUT_SECONDS):
            # Check if state changed (donor accepted, etc.)
            with SessionLocal() as session:
                repo = DatabaseRepository(session)
                req = repo.get_request(request_id)
                if not req or req["status"] != f"RING{current_ring}":
                    logger.info(f"Request {request_id} is no longer in Ring {current_ring}. Stopping monitor.")
                    return
            
            seconds_remaining = cls.RING_TIMEOUT_SECONDS - seconds_elapsed
            
            # Broadcast countdown tick every COUNTDOWN_TICK_INTERVAL seconds
            if seconds_elapsed % cls.COUNTDOWN_TICK_INTERVAL == 0:
                # Simulate donors viewing the request (for demo realism)
                if seconds_elapsed > 5 and donors_viewing < 3:
                    donors_viewing += 1
                
                await manager.broadcast_progress(
                    request_id,
                    WSEventType.RING_COUNTDOWN,
                    {
                        "ring": current_ring,
                        "seconds_remaining": seconds_remaining,
                        "seconds_elapsed": seconds_elapsed,
                        "total_seconds": cls.RING_TIMEOUT_SECONDS,
                        "progress_pct": round((seconds_elapsed / cls.RING_TIMEOUT_SECONDS) * 100),
                        "donors_viewing": donors_viewing
                    }
                )
            
            await asyncio.sleep(1)

        # Timeout reached! Escalate.
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            req = repo.get_request(request_id)
            if not req or req["status"] != f"RING{current_ring}":
                return
            
            # Check if there are donors in the next ring
            next_ring = current_ring + 1
            matches = repo.get_matches_for_request(request_id)
            next_ring_matches = [m for m in matches if m["ring_number"] == next_ring]

            if next_ring_matches:
                # Update status of these matches to NOTIFIED
                for m in next_ring_matches:
                    repo.update_match_status(m["match_id"], "NOTIFIED")
                
                new_state_str = f"RING{next_ring}"
                new_state = EmergencyState(new_state_str) if new_state_str in [e.value for e in EmergencyState] else EmergencyState.WAITING
                
                await EmergencyStateMachine.transition(
                    request_id, 
                    new_state, 
                    f"Ring {current_ring} timeout. Escalating to Ring {next_ring}.",
                    {"step": "ring_escalation", "ring": next_ring}
                )
                
                # Start monitoring next ring
                if new_state.value.startswith("RING"):
                    asyncio.create_task(cls.monitor_ring(request_id, next_ring))
            else:
                # No more rings
                await EmergencyStateMachine.transition(
                    request_id, 
                    EmergencyState.WAITING, 
                    "All donor rings exhausted. Waiting for any available donor.",
                    {"step": "exhausted"}
                )
