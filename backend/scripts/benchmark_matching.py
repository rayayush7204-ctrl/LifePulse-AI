import sys
import os
import time
import statistics
import random
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.matching_engine import MatchingEngine
from haversine import haversine, Unit

def generate_synthetic_donors(count: int):
    blood_types = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
    donors = []
    base_lat = 37.76
    base_lon = -122.45
    for i in range(count):
        lat = base_lat + random.uniform(-0.5, 0.5)
        lon = base_lon + random.uniform(-0.5, 0.5)
        
        # 10% chance of no donation history
        if random.random() < 0.1:
            last_don = None
        else:
            # Between 10 and 200 days ago
            days_ago = random.randint(10, 200)
            last_don = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        donors.append({
            "id": f"D_{i}",
            "blood_type": random.choice(blood_types),
            "latitude": lat,
            "longitude": lon,
            "last_donation_date": last_don,
            "max_travel_radius_km": random.uniform(10.0, 50.0),
            "reliability_score": random.uniform(0.5, 1.0)
        })
    return donors

def run_benchmark():
    dataset_sizes = [100, 1000, 5000, 10000]
    iterations = 10
    req_lat, req_lon = 37.7631, -122.4578
    req_blood = "O+"

    print("=== Matching Engine Benchmark ===")
    print("Methodology: Generates in-memory donors. Measures raw time to filter by ABO compatibility,")
    print("56-day recovery rule, and Haversine distance, followed by multi-factor ranking.")
    print("No database access, network I/O, or artificial delays are included.\n")

    for size in dataset_sizes:
        print(f"--- Dataset Size: {size} donors ---")
        donors = generate_synthetic_donors(size)
        execution_times_ms = []

        # Warm-up (1 run)
        _run_matching_logic(donors, req_lat, req_lon, req_blood)

        for i in range(iterations):
            start_time = time.perf_counter()
            _run_matching_logic(donors, req_lat, req_lon, req_blood)
            end_time = time.perf_counter()
            
            elapsed_ms = (end_time - start_time) * 1000
            execution_times_ms.append(elapsed_ms)

        min_time = min(execution_times_ms)
        max_time = max(execution_times_ms)
        mean_time = statistics.mean(execution_times_ms)
        median_time = statistics.median(execution_times_ms)
        stdev = statistics.stdev(execution_times_ms) if iterations > 1 else 0

        print(f"Runs: {iterations}")
        print(f"Min: {min_time:.2f} ms")
        print(f"Max: {max_time:.2f} ms")
        print(f"Mean: {mean_time:.2f} ms")
        print(f"Median: {median_time:.2f} ms")
        print(f"StdDev: {stdev:.2f} ms\n")

def _run_matching_logic(donors, req_lat, req_lon, req_blood):
    # 1. Compatibility
    compatible_types = MatchingEngine.get_compatible_types(req_blood)
    after_blood_filter = [d for d in donors if d["blood_type"] in compatible_types]

    # 2. 56-day rule
    after_56day = []
    now_date = datetime.now().date()
    for d in after_blood_filter:
        if d["last_donation_date"]:
            last_d = datetime.strptime(d["last_donation_date"], "%Y-%m-%d").date()
            if (now_date - last_d).days < 56:
                continue
        after_56day.append(d)

    # 3. Distance filter
    eligible_donors = []
    for d in after_56day:
        dist_km = haversine((req_lat, req_lon), (d["latitude"], d["longitude"]), unit=Unit.KILOMETERS)
        if dist_km <= d["max_travel_radius_km"]:
            # create shallow copy to avoid mutating original dataset between iterations
            d_copy = dict(d)
            d_copy["calculated_distance"] = dist_km
            eligible_donors.append(d_copy)

    # 4. Rank
    ranked = MatchingEngine._rank_donors(eligible_donors)
    return ranked

if __name__ == "__main__":
    run_benchmark()
