import logging
import asyncio
from typing import Dict, Any
from haversine import haversine, Unit
import time

from app.database import SessionLocal, DatabaseRepository
from app.services.emergency_state_machine import EmergencyStateMachine, EmergencyState

logger = logging.getLogger(__name__)

class GPSService:
    """
    Handles live location updates.
    In this platform, we simulate a donor driving to the hospital by
    interpolating coordinates between their current location and the hospital.
    """

    # Simulation speed: ~120 km/h for faster demo cycles.
    # Each tick = 1 second real-time, covering speed_km_per_sec km.
    SIMULATION_SPEED_KMH = 120
    TICK_INTERVAL_SECONDS = 1

    @classmethod
    async def simulate_donor_drive(cls, request_id: str, match_id: str):
        """
        Background task that updates GPS location every tick and broadcasts ETA.
        Completes the full lifecycle: TRACKING -> ARRIVING -> ARRIVED -> DONATION_STARTED -> DONATION_COMPLETED.
        """
        logger.info(f"Starting GPS simulation for Request {request_id}, Match {match_id}")
        
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            req = repo.get_request(request_id)
            match = repo.get_match(match_id)
            if not req or not match:
                logger.error(f"GPS simulation aborted: request or match not found (req={bool(req)}, match={bool(match)})")
                return

            req_lat, req_lon = req["latitude"], req["longitude"]
            donor_lat = match.get("donor_latitude")
            donor_lon = match.get("donor_longitude")
            
            if donor_lat is None or donor_lon is None:
                logger.error(f"GPS simulation aborted: donor coordinates are None for match {match_id}")
                # Still transition to ARRIVED so the flow completes
                await EmergencyStateMachine.transition(
                    request_id, EmergencyState.ARRIVED, 
                    "Donor has arrived at the hospital.", {"match_id": match_id}
                )
                await cls._complete_donation(request_id, match_id)
                return
            
            speed_km_per_sec = cls.SIMULATION_SPEED_KMH / 3600
            
            total_dist_km = haversine((donor_lat, donor_lon), (req_lat, req_lon), unit=Unit.KILOMETERS)
            logger.info(f"GPS simulation: distance={total_dist_km:.2f}km, speed={cls.SIMULATION_SPEED_KMH}km/h, est_steps={int(total_dist_km / speed_km_per_sec)}")
            
            if total_dist_km <= 0.1:
                await EmergencyStateMachine.transition(
                    request_id, EmergencyState.ARRIVED, 
                    "Donor is already at the hospital.", {"match_id": match_id}
                )
                await cls._complete_donation(request_id, match_id)
                return

            steps = max(1, int(total_dist_km / speed_km_per_sec))
                
            lat_step = (req_lat - donor_lat) / steps
            lon_step = (req_lon - donor_lon) / steps

        current_lat, current_lon = donor_lat, donor_lon
        has_transitioned_to_arriving = False
        
        try:
            time_disconnected = 0
            for step in range(steps):
                from app.websockets.connection_manager import manager
                
                # Disconnect Grace Period
                if manager.get_connection_count(request_id) == 0:
                    time_disconnected += cls.TICK_INTERVAL_SECONDS
                    if time_disconnected > 60:
                        logger.warning(f"GPS simulation terminated: No active subscribers for 60s (Request {request_id})")
                        return
                else:
                    time_disconnected = 0

                # Check state - if not TRACKING or ARRIVING, stop
                with SessionLocal() as session:
                    repo = DatabaseRepository(session)
                    req = repo.get_request(request_id)
                    if not req:
                        logger.info("Request not found, stopping GPS simulation.")
                        return
                    current_status = req["status"]
                    if current_status not in [EmergencyState.TRACKING.value, EmergencyState.ARRIVING.value]:
                        logger.info(f"Emergency state changed to {current_status}, stopping GPS simulation.")
                        return
                
                current_lat += lat_step
                current_lon += lon_step
                
                remaining_dist = haversine((current_lat, current_lon), (req_lat, req_lon), unit=Unit.KILOMETERS)
                remaining_time_min = max(1, int((remaining_dist / cls.SIMULATION_SPEED_KMH) * 60))
                
                # If less than 1 km, state is ARRIVING
                if remaining_dist < 1.0 and not has_transitioned_to_arriving:
                    has_transitioned_to_arriving = True
                    await EmergencyStateMachine.transition(
                        request_id, 
                        EmergencyState.ARRIVING, 
                        "Donor is arriving at the hospital (< 1km).",
                        {"eta_minutes": 1, "distance_km": round(remaining_dist, 2)}
                    )
                
                # Broadcast GPS update
                await manager.broadcast_to_request(request_id, {
                    "type": "GPS_UPDATE",
                    "request_id": request_id,
                    "lat": current_lat,
                    "lng": current_lon,
                    "eta_minutes": remaining_time_min,
                    "distance_km": round(remaining_dist, 2),
                    "step": step + 1,
                    "total_steps": steps
                })
                
                # Update DB match status periodically
                if step % 5 == 0:
                     with SessionLocal() as session:
                        repo = DatabaseRepository(session)
                        repo.update_match_status(match_id, "EN_ROUTE", remaining_time_min)

                await asyncio.sleep(cls.TICK_INTERVAL_SECONDS)

            # Arrived!
            await EmergencyStateMachine.transition(
                request_id, 
                EmergencyState.ARRIVED, 
                "Donor has arrived at the hospital.",
                {"match_id": match_id}
            )
            
            # Complete the donation lifecycle
            await cls._complete_donation(request_id, match_id)
        except asyncio.CancelledError:
            logger.info(f"GPS simulation task cancelled for Request {request_id}")
            raise

    @classmethod
    async def _complete_donation(cls, request_id: str, match_id: str):
        """
        Handles the post-arrival lifecycle: DONATION_STARTED -> DONATION_COMPLETED.
        """
        # Brief pause to simulate donation preparation
        await asyncio.sleep(2)
        
        await EmergencyStateMachine.transition(
            request_id,
            EmergencyState.DONATION_STARTED,
            "Donation procedure has started.",
            {"match_id": match_id}
        )
        
        # Simulate donation duration (short for demo)
        await asyncio.sleep(3)
        
        await EmergencyStateMachine.transition(
            request_id,
            EmergencyState.DONATION_COMPLETED,
            "Donation completed successfully. Thank you for saving a life!",
            {"match_id": match_id}
        )
        
        await asyncio.sleep(1)
        
        await EmergencyStateMachine.transition(
            request_id,
            EmergencyState.CLOSED,
            "Emergency request closed.",
            {"match_id": match_id}
        )
        
        # Update match status
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            repo.update_match_status(match_id, "ARRIVED")
        
        logger.info(f"Full lifecycle completed for Request {request_id}, Match {match_id}")

