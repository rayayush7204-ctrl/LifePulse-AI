"""
WebSocket / GPS Tracking Benchmark (In-Process).

Measures the actual real-time interval between GPS_UPDATE events
broadcast by GPSService.simulate_donor_drive() and received by
a WebSocket listener, using an in-process ASGI transport (no real
TCP overhead). Results reflect server-side event generation latency only.

Run with:
    cd backend
    python scripts/benchmark_websocket.py
"""
import asyncio
import time
import json
import statistics
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, DatabaseRepository
from app.services.gps_service import GPSService
from app.websockets.connection_manager import manager


# ─── In-process GPS event capture ────────────────────────────────────────────
# We bypass the real WebSocket protocol and directly subscribe to the
# connection_manager's broadcast queue by monkey-patching broadcast_to_request.

captured_gps_times = []

_original_broadcast = manager.broadcast_to_request.__func__

async def _capturing_broadcast(self, request_id, message):
    """Intercept GPS_UPDATE events and record precise monotonic timestamps."""
    if isinstance(message, dict) and message.get("type") == "GPS_UPDATE":
        captured_gps_times.append(time.perf_counter())
    # Still call original so the manager behaves correctly
    await _original_broadcast(self, request_id, message)

# Patch the method on the singleton instance
import types
manager.broadcast_to_request = types.MethodType(_capturing_broadcast, manager)
# ─────────────────────────────────────────────────────────────────────────────


def _setup_test_data(req_id: str, match_id: str, donor_id: str):
    """Insert minimal rows needed for GPSService to run."""
    with SessionLocal() as session:
        repo = DatabaseRepository(session)
        repo.add_donor({
            "id": donor_id,
            "name": "GPS Benchmark Donor",
            "blood_type": "O+",
            "latitude": 37.750,
            "longitude": -122.450,
            "max_travel_radius_km": 50.0,
            "reliability_score": 0.95,
        })
        repo.create_request({
            "id": req_id,
            "patient_name": "GPS Benchmark Patient",
            "hospital_name": "Benchmark Hospital",
            "blood_type": "O+",
            "units_needed": 1,
            "urgency_level": "HIGH",
            "latitude": 37.770,   # ~2.2 km from donor
            "longitude": -122.450,
            "status": "TRACKING",
        })
        repo.add_match({
            "match_id": match_id,
            "request_id": req_id,
            "donor_id": donor_id,
            "ring_number": 1,
            "score": 0.90,
            "distance_km": 2.2,
            "status": "ACCEPTED",
            "score_breakdown": {},
            "donor_latitude": 37.750,
            "donor_longitude": -122.450,
        })


async def run_benchmark():
    print("=" * 60)
    print("WebSocket / GPS Tracking Benchmark (In-Process)")
    print("=" * 60)
    print(f"Configured TICK_INTERVAL: {GPSService.TICK_INTERVAL_SECONDS} second(s)")
    print(f"Configured SIMULATION_SPEED: {GPSService.SIMULATION_SPEED_KMH} km/h")
    print("Distance to hospital (simulated): ~2.2 km")
    print()

    req_id = f"req-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    donor_id = f"donor-{uuid.uuid4().hex[:8]}"

    _setup_test_data(req_id, match_id, donor_id)

    max_samples = 20   # Collect up to 20 GPS ticks (simulation ends naturally)

    gps_task = asyncio.create_task(
        GPSService.simulate_donor_drive(req_id, match_id)
    )

    print(f"Running GPS simulation (collecting up to {max_samples} ticks)...")
    try:
        deadline = time.perf_counter() + 45  # 45-second hard cap
        while len(captured_gps_times) < max_samples and time.perf_counter() < deadline:
            if gps_task.done():
                break
            await asyncio.sleep(0.1)
    finally:
        gps_task.cancel()
        try:
            await gps_task
        except asyncio.CancelledError:
            pass

    total_captured = len(captured_gps_times)
    print(f"GPS_UPDATE events captured: {total_captured}\n")

    if total_captured < 2:
        print("Not enough events to calculate intervals. Simulation may have ended too quickly.")
        return

    intervals = [
        captured_gps_times[i] - captured_gps_times[i - 1]
        for i in range(1, total_captured)
    ]

    min_int    = min(intervals)
    max_int    = max(intervals)
    mean_int   = statistics.mean(intervals)
    median_int = statistics.median(intervals)
    stdev_int  = statistics.stdev(intervals) if len(intervals) > 1 else 0

    print("-" * 40)
    print(f"Number of intervals measured : {len(intervals)}")
    print(f"Configured tick interval     : {GPSService.TICK_INTERVAL_SECONDS:.3f} s")
    print(f"Measured minimum interval    : {min_int:.3f} s")
    print(f"Measured median interval     : {median_int:.3f} s")
    print(f"Measured mean interval       : {mean_int:.3f} s")
    print(f"Measured maximum interval    : {max_int:.3f} s")
    print(f"Measured std deviation       : {stdev_int:.3f} s")
    print("-" * 40)
    print()
    print("NOTE: These intervals represent in-process event generation latency.")
    print("Production WebSocket delivery will add network RTT on top of these numbers.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
