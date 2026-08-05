"""
Synthetic Seed Data Generator for Blood Donor Network.
Populates 100+ realistic donors & hospitals across SF, Bangalore, Mumbai, or dynamic GPS location.
"""

from datetime import date, timedelta
import random
from typing import List, Dict, Any

# Blood distribution probabilities based on WHO regional estimates
BLOOD_TYPES = ["O+", "A+", "B+", "O-", "A-", "AB+", "B-", "AB-"]
BLOOD_WEIGHTS = [0.38, 0.30, 0.18, 0.07, 0.04, 0.02, 0.01, 0.005]

# Center coordinates for test cities
CITIES = {
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "delta": 0.15},
    "Bangalore":     {"lat": 12.9716, "lon": 77.5946,   "delta": 0.12},
    "Mumbai":        {"lat": 19.0760, "lon": 72.8777,   "delta": 0.15}
}

FIRST_NAMES = [
    "Alex", "Priya", "Rahul", "Sarah", "Carlos", "Aarav", "Elena", "Marcus",
    "Ananya", "David", "Fatima", "Vikram", "Chloe", "Dev", "Sofia", "Kavya",
    "Michael", "Neha", "Liam", "Zainab", "Arjun", "Emily", "Rohan", "Maya"
]

LAST_NAMES = [
    "Sharma", "Smith", "Patel", "Johnson", "Gupta", "Garcia", "Rao", "Chen",
    "Khan", "Williams", "Nair", "Taylor", "Verma", "Brown", "Reddy", "Davis"
]

def generate_synthetic_donors(count: int = 100) -> List[Dict[str, Any]]:
    donors = []
    today = date.today()

    for i in range(1, count + 1):
        city_name, city_meta = random.choice(list(CITIES.items()))
        
        # Jitter latitude/longitude within city delta radius (~15 km)
        lat = round(city_meta["lat"] + random.uniform(-city_meta["delta"], city_meta["delta"]), 6)
        lon = round(city_meta["lon"] + random.uniform(-city_meta["delta"], city_meta["delta"]), 6)
        
        bt = random.choices(BLOOD_TYPES, weights=BLOOD_WEIGHTS)[0]
        
        # Randomize donation interval: 30% first time/long ago, 50% eligible (>56 days), 20% recent (<56 days)
        rand_cat = random.random()
        if rand_cat < 0.3:
            last_date = None
        elif rand_cat < 0.8:
            days_ago = random.randint(60, 300)
            last_date = (today - timedelta(days=days_ago)).isoformat()
        else:
            days_ago = random.randint(10, 50)
            last_date = (today - timedelta(days=days_ago)).isoformat()

        # 5% chance of disqualifying flag
        disqualifications = []
        if random.random() < 0.05:
            disqualifications = [random.choice(["Low Hemoglobin (<12.5g/dL)", "Recent Travel (Malaria Risk)", "Tattoo < 6 months"])]

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        phone = f"+1{random.randint(400, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"

        donor = {
            "id": f"donor-{i:03d}",
            "name": name,
            "phone": phone,
            "email": f"donor{i}@example.com",
            "blood_type": bt,
            "latitude": lat,
            "longitude": lon,
            "city": city_name,
            "last_donation_date": last_date,
            "is_active": True,
            "is_available": random.random() > 0.1,  # 90% available
            "reliability_score": round(random.uniform(0.75, 0.99), 2),
            "medical_disqualifications": disqualifications
        }
        donors.append(donor)

    return donors

def generate_donors_for_coordinates(lat: float, lon: float, count: int = 25) -> List[Dict[str, Any]]:
    """
    Dynamically generates synthetic donors jittered around the user's exact current GPS coordinates.
    """
    donors = []
    today = date.today()

    for i in range(1, count + 1):
        d_lat = round(lat + random.uniform(-0.12, 0.12), 6)
        d_lon = round(lon + random.uniform(-0.12, 0.12), 6)
        bt = random.choices(BLOOD_TYPES, weights=BLOOD_WEIGHTS)[0]
        
        rand_cat = random.random()
        if rand_cat < 0.3:
            last_date = None
        elif rand_cat < 0.8:
            days_ago = random.randint(60, 300)
            last_date = (today - timedelta(days=days_ago)).isoformat()
        else:
            days_ago = random.randint(10, 50)
            last_date = (today - timedelta(days=days_ago)).isoformat()

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        phone = f"+1{random.randint(400, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"

        donor = {
            "id": f"donor-local-{i:03d}-{random.randint(100, 999)}",
            "name": name,
            "phone": phone,
            "email": f"local_donor{i}@example.com",
            "blood_type": bt,
            "latitude": d_lat,
            "longitude": d_lon,
            "city": "Current GPS Location",
            "last_donation_date": last_date,
            "is_active": True,
            "is_available": True,
            "reliability_score": round(random.uniform(0.80, 0.99), 2),
            "medical_disqualifications": []
        }
        donors.append(donor)

    # Ensure universal donor O- and major blood groups are represented locally
    donors[0]["blood_type"] = "O-"
    donors[1]["blood_type"] = "O+"
    donors[2]["blood_type"] = "A+"
    donors[3]["blood_type"] = "B+"
    donors[4]["blood_type"] = "AB-"
    return donors

def generate_synthetic_hospitals() -> List[Dict[str, Any]]:
    return [
        {
            "id": "bank-sf-01",
            "name": "UCSF Medical Center Blood Bank",
            "phone": "+1-415-353-1307",
            "address": "505 Parnassus Ave, San Francisco, CA",
            "latitude": 37.7631,
            "longitude": -122.4578,
            "inventory": {"O-": 4, "O+": 18, "A+": 12, "A-": 2, "B+": 8, "B-": 1, "AB+": 6, "AB-": 1}
        },
        {
            "id": "bank-sf-02",
            "name": "Zuckerberg San Francisco General Blood Bank",
            "phone": "+1-415-206-8000",
            "address": "1001 Potrero Ave, San Francisco, CA",
            "latitude": 37.7554,
            "longitude": -122.4057,
            "inventory": {"O-": 2, "O+": 14, "A+": 9, "A-": 3, "B+": 6, "B-": 0, "AB+": 4, "AB-": 0}
        },
        {
            "id": "bank-blr-01",
            "name": "Manipal Hospital Blood Reserve",
            "phone": "+91-80-2502-4444",
            "address": "HAL Airport Road, Bangalore",
            "latitude": 12.9585,
            "longitude": 77.6483,
            "inventory": {"O-": 3, "O+": 22, "A+": 15, "B+": 25, "B-": 2, "AB+": 8, "AB-": 1}
        },
        {
            "id": "bank-mum-01",
            "name": "Lilavati Hospital & Research Centre Blood Bank",
            "phone": "+91-22-2675-1000",
            "address": "Bandra West, Mumbai",
            "latitude": 19.0515,
            "longitude": 72.8286,
            "inventory": {"O-": 5, "O+": 30, "A+": 20, "B+": 28, "B-": 3, "AB+": 10, "AB-": 2}
        }
    ]

def generate_hospitals_for_coordinates(lat: float, lon: float) -> List[Dict[str, Any]]:
    """
    Dynamically generates synthetic blood banks around the user's GPS coordinates.
    """
    return [
        {
            "id": f"bank-local-{random.randint(100, 999)}",
            "name": "Local District Hospital Blood Bank",
            "phone": "+1-800-555-0199",
            "address": "Emergency Regional Center, Local District",
            "latitude": round(lat + 0.015, 6),
            "longitude": round(lon + 0.015, 6),
            "inventory": {"O-": 5, "O+": 20, "A+": 15, "A-": 4, "B+": 12, "B-": 2, "AB+": 8, "AB-": 2}
        },
        {
            "id": f"bank-local-{random.randint(100, 999)}",
            "name": "City Emergency Blood Reserve",
            "phone": "+1-800-555-0188",
            "address": "Central Trauma Reserve, City Hub",
            "latitude": round(lat - 0.025, 6),
            "longitude": round(lon - 0.025, 6),
            "inventory": {"O-": 3, "O+": 15, "A+": 10, "A-": 2, "B+": 8, "B-": 1, "AB+": 5, "AB-": 1}
        }
    ]

if __name__ == "__main__":
    import os, sys
    # Ensure backend directory is in sys.path
    BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, BACKEND_DIR)

    from app.database import init_db, SessionLocal, DatabaseRepository

    print("Initializing database...")
    init_db()
    session = SessionLocal()
    repo = DatabaseRepository(session)

    print("Generating synthetic donors...")
    donors = generate_synthetic_donors(100)
    for d in donors:
        repo.add_donor(d)

    print("Generating synthetic hospitals...")
    banks = generate_synthetic_hospitals()
    for b in banks:
        repo.add_hospital(b)

    session.close()
    print(f"Successfully seeded {len(donors)} donors and {len(banks)} hospitals into the database.")
