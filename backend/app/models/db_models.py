"""
SQLAlchemy ORM Models for Persistent Storage.
Defines normalized tables for Users, Donor Profiles, Medical Screenings, Emergency Requests, Matches, Hospitals, and Audit Logs.
"""

from sqlalchemy import Column, String, Float, Boolean, Integer, Date, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import uuid

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    mobile_number = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    is_active = Column(Boolean, default=True)

    donor_profile = relationship("DonorProfileDB", back_populates="user", uselist=False, cascade="all, delete-orphan")

class DonorProfileDB(Base):
    __tablename__ = "donor_profiles"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    blood_type = Column(String(10), index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String(100), default="San Francisco")
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    last_donation_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    is_available = Column(Boolean, default=True)
    max_travel_radius_km = Column(Float, default=25.0)
    reliability_score = Column(Float, default=0.95)
    screening_status = Column(String(50), default="POTENTIALLY_ELIGIBLE")
    screening_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("UserDB", back_populates="donor_profile")
    screening = relationship("DonorMedicalScreeningDB", back_populates="donor", uselist=False, cascade="all, delete-orphan")
    matches = relationship("DonorMatchDB", back_populates="donor", cascade="all, delete-orphan")

class DonorMedicalScreeningDB(Base):
    __tablename__ = "donor_medical_screenings"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    donor_id = Column(String(64), ForeignKey("donor_profiles.id"), unique=True, index=True, nullable=False)
    age = Column(Integer, nullable=False, default=25)
    weight_kg = Column(Float, nullable=False, default=65.0)
    has_fever_or_illness = Column(Boolean, default=False)
    recent_medication = Column(Boolean, default=False)
    recent_surgery = Column(Boolean, default=False)
    recent_vaccination = Column(Boolean, default=False)
    pregnancy_status = Column(Boolean, default=False)
    recent_tattoo_or_piercing = Column(Boolean, default=False)
    travel_exposure_history = Column(Boolean, default=False)
    screening_answers_json = Column(JSON, default=dict)
    eligibility_status = Column(String(50), default="POTENTIALLY_ELIGIBLE")
    eligibility_reasons_json = Column(JSON, default=list)
    eligibility_flags_json = Column(JSON, default=list)
    rules_version = Column(String(20), default="v1.0")
    completed_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=True)

    donor = relationship("DonorProfileDB", back_populates="screening")

class EmergencyRequestDB(Base):
    __tablename__ = "emergency_requests"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    requester_user_id = Column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    patient_name = Column(String(255), default="Emergency Patient")
    requester_phone = Column(String(50), default="+14155550999")
    location_name = Column(String(255), nullable=True)
    location_address = Column(String(255), nullable=True)
    location_source = Column(String(50), default="gps", nullable=True)
    blood_type = Column(String(10), index=True, nullable=False)
    donation_type = Column(String(50), default="WHOLE_BLOOD")
    units_needed = Column(Integer, default=2)
    urgency_level = Column(String(50), default="CRITICAL")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    notes = Column(Text, default="Urgent emergency request.")
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    matches = relationship("DonorMatchDB", back_populates="request", cascade="all, delete-orphan")

class DonorMatchDB(Base):
    __tablename__ = "donor_matches"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    match_id = Column(String(128), unique=True, index=True, nullable=False)
    request_id = Column(String(64), ForeignKey("emergency_requests.id"), index=True, nullable=False)
    donor_id = Column(String(64), ForeignKey("donor_profiles.id"), index=True, nullable=False)
    ring_number = Column(Integer, default=1)
    score = Column(Float, default=0.90)
    distance_km = Column(Float, default=0.0)
    status = Column(String(50), default="NOTIFIED")
    score_breakdown_json = Column(JSON, default=dict)
    donor_latitude = Column(Float, nullable=True)
    donor_longitude = Column(Float, nullable=True)
    eta_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    request = relationship("EmergencyRequestDB", back_populates="matches")
    donor = relationship("DonorProfileDB", back_populates="matches")

class DonationHistoryDB(Base):
    __tablename__ = "donation_histories"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    donor_id = Column(String(64), ForeignKey("donor_profiles.id"), index=True, nullable=False)
    request_id = Column(String(64), nullable=True)
    donation_date = Column(Date, nullable=False)
    units_donated = Column(Integer, default=1)
    hospital_name = Column(String(255), default="Hospital Center")
    status = Column(String(50), default="COMPLETED")
    created_at = Column(DateTime, default=utc_now)

class HospitalDB(Base):
    __tablename__ = "hospitals"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    inventory_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)

class TimelineEventDB(Base):
    __tablename__ = "timeline_events"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    request_id = Column(String(64), index=True, nullable=False)
    message = Column(String(500), nullable=False)
    state = Column(String(50), nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)

class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    request_id = Column(String(64), index=True, nullable=False)
    donor_id = Column(String(64), nullable=True)
    action = Column(String(100), default="MATCH_EVALUATED")
    passed_all = Column(Boolean, default=True)
    score = Column(Float, nullable=True)
    reasons_json = Column(JSON, default=list)
    timestamp = Column(DateTime, default=utc_now)

class FCMDeviceTokenDB(Base):
    __tablename__ = "fcm_device_tokens"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id"), index=True, nullable=False)
    token = Column(String(512), nullable=False, unique=True, index=True)
    platform = Column(String(50), default="web")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class NotificationRecordDB(Base):
    __tablename__ = "notifications"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id"), index=True, nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    request_id = Column(String(64), ForeignKey("emergency_requests.id"), nullable=True)
    match_id = Column(String(128), ForeignKey("donor_matches.match_id"), nullable=True)
    status = Column(String(50), default="SENT")
    created_at = Column(DateTime, default=utc_now)
