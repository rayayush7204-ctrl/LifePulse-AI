"""
Persistent Database Repository powered by SQLAlchemy ORM.
Supports SQLite (zero-config persistent storage) and PostgreSQL.
Provides thread-safe persistence for Users, Donors, Medical Screenings, Requests, Matches, Hospitals, and Audit Logs.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends
import os
import uuid
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Any

from app.config import settings
from app.models.db_models import (
    Base, UserDB, DonorProfileDB, DonorMedicalScreeningDB,
    EmergencyRequestDB, DonorMatchDB, HospitalDB, AuditLogDB, DonationHistoryDB, TimelineEventDB
)

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

# Pass pool arguments only for postgresql, sqlite does not support them.
engine_kwargs = {}
if db_url.startswith("postgresql"):
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
elif db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes all database tables."""
    Base.metadata.create_all(bind=engine)

def get_db_session():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_repository(session: Session = Depends(get_db_session)):
    return DatabaseRepository(session)
def row_to_dict(row: Any) -> Dict[str, Any]:
    """Helper to convert an ORM model instance into a clean dictionary."""
    if not row:
        return {}
    d = {}
    for column in row.__table__.columns:
        val = getattr(row, column.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        d[column.name] = val
    return d

class DatabaseRepository:
    """Thread-safe persistent repository managing database operations."""

    def __init__(self, session: Session):
        self.session = session

    # --- USER OPERATIONS ---
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:

        user_id = user_data.get("id") or f"usr-{uuid.uuid4().hex[:8]}"
        user = UserDB(
            id=user_id,
            full_name=user_data["full_name"],
            email=user_data["email"].lower().strip(),
            mobile_number=user_data["mobile_number"].strip(),
            password_hash=user_data["password_hash"],
            is_active=user_data.get("is_active", True)
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return row_to_dict(user)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:

        user = self.session.query(UserDB).filter(UserDB.id == user_id).first()
        return row_to_dict(user) if user else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:

        user = self.session.query(UserDB).filter(UserDB.email == email.lower().strip()).first()
        return row_to_dict(user) if user else None

    def get_user_by_mobile(self, mobile_number: str) -> Optional[Dict[str, Any]]:

        user = self.session.query(UserDB).filter(UserDB.mobile_number == mobile_number.strip()).first()
        return row_to_dict(user) if user else None

    # --- DONOR OPERATIONS ---
    def add_donor(self, donor_data: Dict[str, Any]) -> Dict[str, Any]:

        donor_id = donor_data.get("id") or f"donor-{uuid.uuid4().hex[:8]}"

        # Check if updating existing donor
        existing = self.session.query(DonorProfileDB).filter(DonorProfileDB.id == donor_id).first()
        if not existing and donor_data.get("user_id"):
            existing = self.session.query(DonorProfileDB).filter(DonorProfileDB.user_id == donor_data["user_id"]).first()

        last_don_date = donor_data.get("last_donation_date")
        if isinstance(last_don_date, str) and last_don_date.strip():
            try:
                last_don_date = datetime.strptime(last_don_date, "%Y-%m-%d").date()
            except Exception:
                last_don_date = None

        if existing:
            existing.name = donor_data.get("name", existing.name)
            existing.phone = donor_data.get("phone", existing.phone)
            existing.email = donor_data.get("email", existing.email)
            existing.blood_type = donor_data.get("blood_type", existing.blood_type)
            existing.latitude = float(donor_data.get("latitude", existing.latitude))
            existing.longitude = float(donor_data.get("longitude", existing.longitude))
            existing.city = donor_data.get("city", existing.city)
            if last_don_date:
                existing.last_donation_date = last_don_date
            existing.is_active = donor_data.get("is_active", existing.is_active)
            existing.is_available = donor_data.get("is_available", existing.is_available)
            if "screening_status" in donor_data:
                existing.screening_status = donor_data["screening_status"]
            self.session.commit()
            self.session.refresh(existing)
            return row_to_dict(existing)
        else:
            donor = DonorProfileDB(
                id=donor_id,
                user_id=donor_data.get("user_id"),
                name=donor_data.get("name", "Jane Doe"),
                phone=donor_data.get("phone", "+14155550123"),
                email=donor_data.get("email"),
                blood_type=donor_data.get("blood_type", "O-"),
                latitude=float(donor_data.get("latitude", 37.7749)),
                longitude=float(donor_data.get("longitude", -122.4194)),
                city=donor_data.get("city", "San Francisco"),
                state=donor_data.get("state"),
                pincode=donor_data.get("pincode"),
                last_donation_date=last_don_date if isinstance(last_don_date, date) else None,
                is_active=donor_data.get("is_active", True),
                is_available=donor_data.get("is_available", True),
                max_travel_radius_km=float(donor_data.get("max_travel_radius_km", 25.0)),
                reliability_score=float(donor_data.get("reliability_score", 0.95)),
                screening_status=donor_data.get("screening_status", "POTENTIALLY_ELIGIBLE")
            )
            self.session.add(donor)
            self.session.commit()
            self.session.refresh(donor)
            return row_to_dict(donor)

    def get_donor(self, donor_id: str) -> Optional[Dict[str, Any]]:

        d = self.session.query(DonorProfileDB).filter(DonorProfileDB.id == donor_id).first()
        return row_to_dict(d) if d else None

    def get_donor_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:

        d = self.session.query(DonorProfileDB).filter(DonorProfileDB.user_id == user_id).first()
        return row_to_dict(d) if d else None

    def list_donors(self, filters: Optional[Dict[str, Any]] = None, bbox: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        query = self.session.query(DonorProfileDB)
        if filters:
            for k, v in filters.items():
                if hasattr(DonorProfileDB, k):
                    query = query.filter(getattr(DonorProfileDB, k) == v)
        if bbox:
            query = query.filter(
                DonorProfileDB.latitude >= bbox['min_lat'],
                DonorProfileDB.latitude <= bbox['max_lat'],
                DonorProfileDB.longitude >= bbox['min_lon'],
                DonorProfileDB.longitude <= bbox['max_lon']
            )
        donors = query.all()
        return [row_to_dict(d) for d in donors]

    # --- MEDICAL SCREENING OPERATIONS ---
    def save_donor_screening(self, screening_data: Dict[str, Any]) -> Dict[str, Any]:

        donor_id = screening_data["donor_id"]
        existing = self.session.query(DonorMedicalScreeningDB).filter(DonorMedicalScreeningDB.donor_id == donor_id).first()
        if existing:
            existing.age = screening_data.get("age", existing.age)
            existing.weight_kg = screening_data.get("weight_kg", existing.weight_kg)
            existing.has_fever_or_illness = screening_data.get("has_fever_or_illness", existing.has_fever_or_illness)
            existing.recent_medication = screening_data.get("recent_medication", existing.recent_medication)
            existing.recent_surgery = screening_data.get("recent_surgery", existing.recent_surgery)
            existing.recent_vaccination = screening_data.get("recent_vaccination", existing.recent_vaccination)
            existing.pregnancy_status = screening_data.get("pregnancy_status", existing.pregnancy_status)
            existing.recent_tattoo_or_piercing = screening_data.get("recent_tattoo_or_piercing", existing.recent_tattoo_or_piercing)
            existing.travel_exposure_history = screening_data.get("travel_exposure_history", existing.travel_exposure_history)
            existing.screening_answers_json = screening_data.get("screening_answers_json", {})
            existing.eligibility_status = screening_data.get("eligibility_status", existing.eligibility_status)
            existing.eligibility_reasons_json = screening_data.get("eligibility_reasons_json", [])
            existing.eligibility_flags_json = screening_data.get("eligibility_flags_json", [])
            existing.completed_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(existing)
            res = row_to_dict(existing)
        else:
            sc = DonorMedicalScreeningDB(
                id=f"scr-{uuid.uuid4().hex[:8]}",
                donor_id=donor_id,
                age=screening_data.get("age", 25),
                weight_kg=screening_data.get("weight_kg", 65.0),
                has_fever_or_illness=screening_data.get("has_fever_or_illness", False),
                recent_medication=screening_data.get("recent_medication", False),
                recent_surgery=screening_data.get("recent_surgery", False),
                recent_vaccination=screening_data.get("recent_vaccination", False),
                pregnancy_status=screening_data.get("pregnancy_status", False),
                recent_tattoo_or_piercing=screening_data.get("recent_tattoo_or_piercing", False),
                travel_exposure_history=screening_data.get("travel_exposure_history", False),
                screening_answers_json=screening_data.get("screening_answers_json", {}),
                eligibility_status=screening_data.get("eligibility_status", "POTENTIALLY_ELIGIBLE"),
                eligibility_reasons_json=screening_data.get("eligibility_reasons_json", []),
                eligibility_flags_json=screening_data.get("eligibility_flags_json", [])
            )
            self.session.add(sc)
            self.session.commit()
            self.session.refresh(sc)
            res = row_to_dict(sc)

        # Update donor screening status
        donor = self.session.query(DonorProfileDB).filter(DonorProfileDB.id == donor_id).first()
        if donor:
            donor.screening_status = res.get("eligibility_status", "POTENTIALLY_ELIGIBLE")
            donor.screening_completed_at = datetime.now(timezone.utc)
            self.session.commit()

        return res

    def get_donor_screening(self, donor_id: str) -> Optional[Dict[str, Any]]:

        sc = self.session.query(DonorMedicalScreeningDB).filter(DonorMedicalScreeningDB.donor_id == donor_id).first()
        return row_to_dict(sc) if sc else None

    # --- REQUEST OPERATIONS ---
    def create_request(self, req_data: Dict[str, Any]) -> Dict[str, Any]:

        req_id = req_data.get("id") or f"req-{uuid.uuid4().hex[:8]}"
        req = EmergencyRequestDB(
            id=req_id,
            requester_user_id=req_data.get("requester_user_id"),
            patient_name=req_data.get("patient_name", "Emergency Patient"),
            requester_phone=req_data.get("requester_phone", "+14155550999"),
            hospital_name=req_data.get("hospital_name", "UCSF Medical Center"),
            blood_type=req_data.get("blood_type", "O-"),
            donation_type=req_data.get("donation_type", "WHOLE_BLOOD"),
            units_needed=int(req_data.get("units_needed", 2)),
            urgency_level=req_data.get("urgency_level", "CRITICAL"),
            latitude=float(req_data.get("latitude", 37.7631)),
            longitude=float(req_data.get("longitude", -122.4578)),
            notes=req_data.get("notes", "Urgent emergency request."),
            status=req_data.get("status", "PENDING")
        )
        self.session.add(req)
        self.session.commit()
        self.session.refresh(req)
        return row_to_dict(req)

    def get_request(self, req_id: str) -> Optional[Dict[str, Any]]:

        r = self.session.query(EmergencyRequestDB).filter(EmergencyRequestDB.id == req_id).first()
        return row_to_dict(r) if r else None

    def list_requests(self, bbox: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        query = self.session.query(EmergencyRequestDB)
        if bbox:
            query = query.filter(
                EmergencyRequestDB.latitude >= bbox['min_lat'],
                EmergencyRequestDB.latitude <= bbox['max_lat'],
                EmergencyRequestDB.longitude >= bbox['min_lon'],
                EmergencyRequestDB.longitude <= bbox['max_lon']
            )
        reqs = query.all()
        return [row_to_dict(r) for r in reqs]

    def update_request_status(self, req_id: str, status: str) -> Optional[Dict[str, Any]]:

        r = self.session.query(EmergencyRequestDB).filter(EmergencyRequestDB.id == req_id).first()
        if r:
            r.status = status
            self.session.commit()
            self.session.refresh(r)
            return row_to_dict(r)
        return None

    def try_accept_emergency(self, req_id: str) -> bool:
        """
        Atomically attempts to accept an emergency request.
        Only succeeds if the request is currently in a state that can be accepted.
        Returns True if successful, False if already accepted or invalid state.
        """
        updated_count = self.session.query(EmergencyRequestDB).filter(
            EmergencyRequestDB.id == req_id,
            EmergencyRequestDB.status.in_(["RING1", "RING2", "WAITING"])
        ).update({"status": "DONOR_ACCEPTED"}, synchronize_session=False)
        self.session.commit()
        return updated_count > 0

    # --- MATCH OPERATIONS ---
    def add_match(self, match_data: Dict[str, Any]) -> Dict[str, Any]:

        match_id = match_data.get("match_id") or f"match-{uuid.uuid4().hex[:8]}"
        existing = self.session.query(DonorMatchDB).filter(DonorMatchDB.match_id == match_id).first()
        if existing:
            existing.status = match_data.get("status", existing.status)
            existing.score = float(match_data.get("score", existing.score))
            existing.distance_km = float(match_data.get("distance_km", existing.distance_km))
            existing.donor_latitude = match_data.get("donor_latitude", existing.donor_latitude)
            existing.donor_longitude = match_data.get("donor_longitude", existing.donor_longitude)
            if "eta_minutes" in match_data:
                existing.eta_minutes = match_data["eta_minutes"]
            self.session.commit()
            self.session.refresh(existing)
            return row_to_dict(existing)
        else:
            m = DonorMatchDB(
                id=f"dm-{uuid.uuid4().hex[:8]}",
                match_id=match_id,
                request_id=match_data["request_id"],
                donor_id=match_data["donor_id"],
                ring_number=int(match_data.get("ring_number", 1)),
                score=float(match_data.get("score", 0.90)),
                distance_km=float(match_data.get("distance_km", 0.0)),
                status=match_data.get("status", "NOTIFIED"),
                score_breakdown_json=match_data.get("score_breakdown", {}),
                donor_latitude=match_data.get("donor_latitude"),
                donor_longitude=match_data.get("donor_longitude"),
                eta_minutes=match_data.get("eta_minutes")
            )
            self.session.add(m)
            self.session.commit()
            self.session.refresh(m)
            return row_to_dict(m)

    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:

        m = self.session.query(DonorMatchDB).filter(DonorMatchDB.match_id == match_id).first()
        return row_to_dict(m) if m else None

    def get_matches_for_request(self, req_id: str) -> List[Dict[str, Any]]:

        matches = self.session.query(DonorMatchDB).filter(DonorMatchDB.request_id == req_id).all()
        result = []
        for m in matches:
            m_dict = row_to_dict(m)
            # Attach donor profile details
            donor = self.session.query(DonorProfileDB).filter(DonorProfileDB.id == m.donor_id).first()
            if donor:
                m_dict["donor_name"] = donor.name
                m_dict["donor_phone"] = donor.phone
                m_dict["donor_blood_type"] = donor.blood_type
                m_dict["donor"] = row_to_dict(donor)
            result.append(m_dict)
        return result

    def update_match_status(self, match_id: str, status: str, eta_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:

        m = self.session.query(DonorMatchDB).filter(DonorMatchDB.match_id == match_id).first()
        if m:
            m.status = status
            if eta_minutes is not None:
                m.eta_minutes = eta_minutes
            self.session.commit()
            self.session.refresh(m)
            return row_to_dict(m)
        return None

    # --- HOSPITAL OPERATIONS ---
    def add_hospital(self, hospital_data: Dict[str, Any]) -> Dict[str, Any]:

        h_id = hospital_data.get("id") or f"bank-{uuid.uuid4().hex[:8]}"
        existing = self.session.query(HospitalDB).filter(HospitalDB.id == h_id).first()
        if existing:
            existing.name = hospital_data.get("name", existing.name)
            existing.phone = hospital_data.get("phone", existing.phone)
            existing.address = hospital_data.get("address", existing.address)
            existing.latitude = float(hospital_data.get("latitude", existing.latitude))
            existing.longitude = float(hospital_data.get("longitude", existing.longitude))
            existing.inventory_json = hospital_data.get("inventory", existing.inventory_json)
            self.session.commit()
            self.session.refresh(existing)
            return row_to_dict(existing)
        else:
            h = HospitalDB(
                id=h_id,
                name=hospital_data["name"],
                phone=hospital_data.get("phone", "+18005550199"),
                address=hospital_data.get("address", "Hospital Center"),
                latitude=float(hospital_data.get("latitude", 37.7631)),
                longitude=float(hospital_data.get("longitude", -122.4578)),
                inventory_json=hospital_data.get("inventory", {})
            )
            self.session.add(h)
            self.session.commit()
            self.session.refresh(h)
            return row_to_dict(h)

    def list_hospitals(self, bbox: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        query = self.session.query(HospitalDB)
        if bbox:
            query = query.filter(
                HospitalDB.latitude >= bbox['min_lat'],
                HospitalDB.latitude <= bbox['max_lat'],
                HospitalDB.longitude >= bbox['min_lon'],
                HospitalDB.longitude <= bbox['max_lon']
            )
        hosps = query.all()
        res = []
        for h in hosps:
            d = row_to_dict(h)
            d["inventory"] = h.inventory_json or {}
            res.append(d)
        return res

    # --- AUDIT LOG OPERATIONS ---
    def add_audit_log(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:

        log = AuditLogDB(
            id=f"audit-{uuid.uuid4().hex[:8]}",
            request_id=audit_data["request_id"],
            donor_id=audit_data.get("donor_id"),
            action=audit_data.get("action", "MATCH_EVALUATED"),
            passed_all=bool(audit_data.get("passed_all", True)),
            score=float(audit_data["score"]) if audit_data.get("score") is not None else None,
            reasons_json=audit_data.get("reasons", [])
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        res = row_to_dict(log)
        res["reasons"] = log.reasons_json
        return res

    def get_audit_logs_for_request(self, req_id: str) -> List[Dict[str, Any]]:

        logs = self.session.query(AuditLogDB).filter(AuditLogDB.request_id == req_id).all()
        res = []
        for l in logs:
            d = row_to_dict(l)
            d["reasons"] = l.reasons_json or []
            res.append(d)
        return res

    # --- TIMELINE OPERATIONS ---
    def add_timeline_event(self, request_id: str, message: str, state: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        event = TimelineEventDB(
            id=f"evt-{uuid.uuid4().hex[:8]}",
            request_id=request_id,
            message=message,
            state=state,
            metadata_json=metadata or {}
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return row_to_dict(event)

    def get_timeline_events_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        events = self.session.query(TimelineEventDB).filter(TimelineEventDB.request_id == request_id).order_by(TimelineEventDB.created_at.asc()).all()
        return [row_to_dict(e) for e in events]

