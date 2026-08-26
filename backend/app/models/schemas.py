"""
Pydantic API Schemas & Data Models.
Defines strict validation for Donors, Medical Screenings, Blood Requests, Matches, Blood Banks, and Audit Logs.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from enum import Enum

class BloodTypeEnum(str, Enum):
    O_NEG = "O-"
    O_POS = "O+"
    A_NEG = "A-"
    A_POS = "A+"
    B_NEG = "B-"
    B_POS = "B+"
    AB_NEG = "AB-"
    AB_POS = "AB+"

    def __str__(self): return self.value

class DonationTypeEnum(str, Enum):
    WHOLE_BLOOD = "WHOLE_BLOOD"
    RBC = "RBC"
    PLASMA = "PLASMA"
    PLATELETS = "PLATELETS"

    def __str__(self): return self.value

class UrgencyLevelEnum(str, Enum):
    CRITICAL = "CRITICAL"    # Life threatening, immediate < 1 hr
    HIGH = "HIGH"            # Surgery / transfusion within 3 hrs
    MEDIUM = "MEDIUM"        # Scheduled transfusion today

    def __str__(self): return self.value

class MatchStatusEnum(str, Enum):
    NOTIFIED = "NOTIFIED"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    CANCELLED = "CANCELLED"
    WITHDRAWN = "WITHDRAWN"

    def __str__(self): return self.value

class RequestStatusEnum(str, Enum):
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
    CANCELLED = "CANCELLED"

    def __str__(self): return self.value

# --- DONOR SCHEMAS ---

class DonorCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Jane Doe"})
    phone: str = Field(..., json_schema_extra={"example": "+14155550123"})
    email: Optional[str] = Field(None, json_schema_extra={"example": "jane@example.com"})
    blood_type: BloodTypeEnum = Field(..., json_schema_extra={"example": "O-"})
    latitude: float = Field(..., json_schema_extra={"example": 37.7749})
    longitude: float = Field(..., json_schema_extra={"example": -122.4194})
    city: str = Field("San Francisco", json_schema_extra={"example": "San Francisco"})
    last_donation_date: Optional[date] = Field(None, json_schema_extra={"example": "2026-03-15"})
    is_active: bool = True
    is_available: bool = True
    user_id: Optional[str] = None
    medical_disqualifications: List[str] = Field(default_factory=list)

class DonorResponse(DonorCreate):
    id: str
    reliability_score: float = 0.95
    created_at: datetime

class DonorLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    is_available: Optional[bool] = None
    request_id: Optional[str] = None
    speed_kmh: Optional[float] = 35.0

# --- MEDICAL PRE-SCREENING SCHEMAS ---

class DonorMedicalScreeningPayload(BaseModel):
    donor_id: str
    age: int = Field(25, ge=16, le=80)
    weight_kg: float = Field(65.0, ge=30.0, le=200.0)
    has_fever_or_illness: bool = False
    recent_medication: bool = False
    recent_surgery: bool = False
    recent_vaccination: bool = False
    pregnancy_status: bool = False
    recent_tattoo_or_piercing: bool = False
    travel_exposure_history: bool = False
    additional_notes: Optional[str] = None

# --- REQUEST SCHEMAS ---

class BloodRequestCreate(BaseModel):
    patient_name: str = Field("Emergency Patient", json_schema_extra={"example": "John Smith"})
    requester_phone: str = Field("+14155550999", json_schema_extra={"example": "+14155550999"})
    hospital_name: str = Field("UCSF Medical Center", json_schema_extra={"example": "UCSF Medical Center"})
    blood_type: BloodTypeEnum = Field(BloodTypeEnum.O_NEG, json_schema_extra={"example": "O-"})
    donation_type: DonationTypeEnum = DonationTypeEnum.WHOLE_BLOOD
    units_needed: int = Field(2, ge=1, le=10)
    urgency_level: UrgencyLevelEnum = UrgencyLevelEnum.CRITICAL
    latitude: float = Field(..., json_schema_extra={"example": 37.7631})
    longitude: float = Field(..., json_schema_extra={"example": -122.4578})
    notes: Optional[str] = Field("Urgent emergency request.", json_schema_extra={"example": "Urgent trauma surgery, ICU bed 4"})
    requester_user_id: Optional[str] = None

    @field_validator("blood_type", mode="before")
    @classmethod
    def normalize_blood_type(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().upper().replace(" ", "").replace("NEGATIVE", "-").replace("MINUS", "-").replace("POSITIVE", "+").replace("PLUS", "+")
            mapping = {
                "O-": "O-", "O+": "O+", "A-": "A-", "A+": "A+", "B-": "B-", "B+": "B+", "AB-": "AB-", "AB+": "AB+",
                "ONEG": "O-", "OPOS": "O+", "ANEG": "A-", "APOS": "A+", "BNEG": "B-", "BPOS": "B+", "ABNEG": "AB-", "ABPOS": "AB+"
            }
            if clean in mapping:
                return mapping[clean]
        return v or "O-"

    @field_validator("donation_type", mode="before")
    @classmethod
    def normalize_donation_type(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if "WHOLE" in v_upper: return "WHOLE_BLOOD"
            if "RBC" in v_upper or "RED" in v_upper: return "RBC"
            if "PLASMA" in v_upper: return "PLASMA"
            if "PLATELET" in v_upper: return "PLATELETS"
        return v or "WHOLE_BLOOD"

    @field_validator("urgency_level", mode="before")
    @classmethod
    def normalize_urgency_level(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if "CRITICAL" in v_upper or "EMERGENCY" in v_upper or "URGENT" in v_upper: return "CRITICAL"
            if "HIGH" in v_upper: return "HIGH"
            if "MEDIUM" in v_upper: return "MEDIUM"
        return v or "CRITICAL"

    @field_validator("units_needed", mode="before")
    @classmethod
    def normalize_units_needed(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(1, min(val, 10))
        except (ValueError, TypeError):
            return 2

    @field_validator("patient_name", "requester_phone", "hospital_name", mode="before")
    @classmethod
    def normalize_string_defaults(cls, v: Any, info) -> str:
        if not v or not str(v).strip():
            defaults = {
                "patient_name": "Emergency Patient",
                "requester_phone": "+14155550999",
                "hospital_name": "Emergency Medical Center"
            }
            return defaults.get(info.field_name, "Emergency Medical Center")
        return str(v).strip()

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_coordinates(cls, v: Any, info) -> float:
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"{info.field_name} must be a valid number, got: {v!r}")
        if info.field_name == "latitude" and not (-90 <= val <= 90):
            raise ValueError(f"latitude must be between -90 and 90, got: {val}")
        if info.field_name == "longitude" and not (-180 <= val <= 180):
            raise ValueError(f"longitude must be between -180 and 180, got: {val}")
        return val

class ParsedRequestAIInput(BaseModel):
    raw_text: str = Field(..., json_schema_extra={"example": "Need 2 units O negative blood at UCSF hospital immediately for surgery!"})

class BloodRequestResponse(BloodRequestCreate):
    id: str
    status: RequestStatusEnum = RequestStatusEnum.CREATED
    created_at: datetime
    matched_donors_count: int = 0
    accepted_donors_count: int = 0

# --- MATCH SCHEMAS ---

class DonorMatchResponse(BaseModel):
    match_id: str
    request_id: str
    donor_id: str
    donor_name: str
    donor_phone: str
    donor_blood_type: str
    ring_number: int
    score: float
    distance_km: float
    status: MatchStatusEnum
    score_breakdown: Dict[str, Any]
    donor_latitude: float
    donor_longitude: float
    updated_at: datetime

class DonorActionPayload(BaseModel):
    match_id: str
    action: MatchStatusEnum  # ACCEPTED, DECLINED, EN_ROUTE, ARRIVED
    eta_minutes: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    request_id: Optional[str] = None

# --- TIMELINE SCHEMAS ---

class TimelineEventCreate(BaseModel):
    request_id: str
    message: str
    state: str
    metadata: Optional[Dict[str, Any]] = None

class TimelineEventResponse(TimelineEventCreate):
    id: str
    created_at: datetime

# --- HOSPITAL & BLOOD BANK ---

class BloodBankItem(BaseModel):
    id: str
    name: str
    phone: str
    address: str
    latitude: float
    longitude: float
    distance_km: float
    inventory: Dict[str, int] # e.g. {"O-": 4, "A+": 12}

# --- CUSTOM RESPONSE MODELS FOR FRONTEND CONSISTENCY ---

class SignupResponse(BaseModel):
    message: str
    token: str
    user: Dict[str, Any]
    has_donor_profile: bool

class LoginResponse(BaseModel):
    message: str
    token: str
    user: Dict[str, Any]
    has_donor_profile: bool
    donor_profile: Optional[Dict[str, Any]] = None

class UserMeResponse(BaseModel):
    user: Dict[str, Any]
    has_donor_profile: bool
    donor_profile: Optional[Dict[str, Any]] = None

class SubmitRequestResponse(BaseModel):
    message: str
    request: Dict[str, Any]
    matching_summary: Dict[str, Any]

class SubmitScreeningResponse(BaseModel):
    message: str
    screening: Dict[str, Any]
    pre_screening_result: Dict[str, Any]

class DonorRespondResponse(BaseModel):
    message: str
    match: Dict[str, Any]

class DonorLocationUpdateResponse(BaseModel):
    message: str
    donor: Optional[Dict[str, Any]]
    location_updates: List[Dict[str, Any]]

# --- NOTIFICATION SCHEMAS ---

class DeviceTokenCreate(BaseModel):
    token: str
    platform: Optional[str] = "web"

class NotificationStatusEnum(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    INVALID_TOKEN = "INVALID_TOKEN"

class NotificationRecord(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: str
    request_id: Optional[str] = None
    match_id: Optional[str] = None
    status: NotificationStatusEnum
    created_at: datetime
