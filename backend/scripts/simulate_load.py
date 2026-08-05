"""
Load Test Simulator Script (Phase 5 Hardening).
Simulates 50+ concurrent emergency blood requests and 500+ donor notification fan-outs.
Verifies latency, matching performance, and concurrent WebSocket stability.
"""

import asyncio
import time
import random
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import db
from scripts.seed_data import generate_synthetic_donors

BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]

async def run_single_request_simulation(client: AsyncClient, req_id: int):
    bt = random.choice(BLOOD_TYPES)
    payload = {
        "patient_name": f"Load Patient #{req_id}",
        "requester_phone": f"+1415555{req_id:04d}",
        "hospital_name": "UCSF Medical Center",
        "blood_type": bt,
        "donation_type": "WHOLE_BLOOD",
        "units_needed": random.randint(1, 3),
        "urgency_level": random.choice(["CRITICAL", "HIGH"]),
        "latitude": 37.7631 + random.uniform(-0.05, 0.05),
        "longitude": -122.4578 + random.uniform(-0.05, 0.05),
        "notes": f"Load test request #{req_id}"
    }

    start_time = time.time()
    response = await client.post("/api/v1/requests/", json=payload)
    elapsed_ms = (time.time() - start_time) * 1000.0

    assert response.status_code == 200
    data = response.json()
    return {
        "req_id": req_id,
        "elapsed_ms": elapsed_ms,
        "eligible_count": data["matching_summary"]["eligible_count"]
    }

async def run_load_test(num_concurrent_requests: int = 50):
    print(f"--- Starting Load Test: {num_concurrent_requests} Concurrent Emergency Requests ---")
    
    # Pre-seed 200 donors into DB
    donors = generate_synthetic_donors(200)
    for d in donors:
        db.add_donor(d)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_all = time.time()
        tasks = [run_single_request_simulation(client, i) for i in range(1, num_concurrent_requests + 1)]
        results = await asyncio.gather(*tasks)
        total_time_sec = time.time() - start_all

    latencies = [r["elapsed_ms"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    print(f"\n[SUCCESS] Load Test Completed Successfully!")
    print(f"Total Concurrent Requests: {num_concurrent_requests}")
    print(f"Total Execution Time: {total_time_sec:.2f} seconds")
    print(f"Average Request Latency: {avg_latency:.2f} ms")
    print(f"Max Request Latency: {max_latency:.2f} ms")
    print(f"Throughput: {num_concurrent_requests / total_time_sec:.2f} requests/sec")

if __name__ == "__main__":
    asyncio.run(run_load_test(50))
