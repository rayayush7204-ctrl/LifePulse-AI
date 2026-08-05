"""
Authentication Router.
Handles user registration (signup), authentication (login), JWT token issuance, and user session validation.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import bcrypt

from app.config import settings
from app.database import DatabaseRepository, get_repository
from app.models.schemas import SignupResponse, LoginResponse, UserMeResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

# --- Pydantic Schemas for Auth ---

class UserSignupPayload(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    mobile_number: str = Field(..., min_length=7, max_length=20, pattern=r"^\+?[1-9]\d{1,14}$")
    password: str = Field(..., min_length=6, max_length=100)

class UserLoginPayload(BaseModel):
    email_or_mobile: str
    password: str

async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    repo: DatabaseRepository = Depends(get_repository)
) -> Optional[Dict[str, Any]]:
    """Helper to extract user from JWT Bearer token if provided."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return repo.get_user_by_id(user_id)
    except JWTError:
        return None

async def get_current_user_required(
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Dependency enforcing valid authentication."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

@router.post("/signup", response_model=SignupResponse)
async def signup(payload: UserSignupPayload, repo: DatabaseRepository = Depends(get_repository)):
    """
    Creates a new persistent User account.
    """
    email_clean = payload.email.lower().strip()
    mobile_clean = payload.mobile_number.strip()

    # Validate duplicates
    if repo.get_user_by_email(email_clean):
        raise HTTPException(status_code=400, detail="An account with this email address already exists.")
    if repo.get_user_by_mobile(mobile_clean):
        raise HTTPException(status_code=400, detail="An account with this mobile number already exists.")

    hashed_pw = hash_password(payload.password)
    user_data = {
        "full_name": payload.full_name.strip(),
        "email": email_clean,
        "mobile_number": mobile_clean,
        "password_hash": hashed_pw
    }

    user = repo.create_user(user_data)
    token = create_access_token({"sub": user["id"], "email": user["email"]})

    # Remove sensitive hash before returning
    user.pop("password_hash", None)

    return {
        "message": "Account created successfully.",
        "token": token,
        "user": user,
        "has_donor_profile": False
    }

@router.post("/login", response_model=LoginResponse)
async def login(payload: UserLoginPayload, repo: DatabaseRepository = Depends(get_repository)):
    """
    Authenticates existing user credentials.
    """
    identifier = payload.email_or_mobile.strip()
    user = repo.get_user_by_email(identifier) or repo.get_user_by_mobile(identifier)

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email/mobile or password.")

    token = create_access_token({"sub": user["id"], "email": user["email"]})
    donor_profile = repo.get_donor_by_user_id(user["id"])

    user_clean = {**user}
    user_clean.pop("password_hash", None)

    return {
        "message": "Login successful.",
        "token": token,
        "user": user_clean,
        "has_donor_profile": bool(donor_profile),
        "donor_profile": donor_profile
    }

@router.get("/me", response_model=UserMeResponse)
async def get_me(user: Dict[str, Any] = Depends(get_current_user_required), repo: DatabaseRepository = Depends(get_repository)):
    """
    Returns current authenticated user profile and donor status.
    """
    donor_profile = repo.get_donor_by_user_id(user["id"])
    user_clean = {**user}
    user_clean.pop("password_hash", None)
    return {
        "user": user_clean,
        "has_donor_profile": bool(donor_profile),
        "donor_profile": donor_profile
    }
