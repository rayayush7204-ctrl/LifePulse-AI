"""
Application Configuration Settings.
Reads environment variables or provides production-grade defaults.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Smart Blood Donation Network"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-emergency-blood-match-key-2026")
    
    # Database Settings (PostgreSQL engine configuration)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/blood_donor")
    USE_SQLITE_FALLBACK: bool = os.getenv("USE_SQLITE_FALLBACK", "False").lower() == "true"
    
    # Redis Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Matching Engine Parameters
    DEFAULT_MAX_RADIUS_KM: float = 25.0
    DEFAULT_RING_SIZE: int = 5
    RING_ESCALATION_TIMEOUT_SECONDS: int = 45  # Ring 1 timeout before ring 2 fan-out
    
    # Exotel / Notification Credentials
    EXOTEL_SID: str = os.getenv("EXOTEL_SID", "demo_exotel_sid")
    EXOTEL_TOKEN: str = os.getenv("EXOTEL_TOKEN", "demo_exotel_token")
    EXOTEL_PHONE_NUMBER: str = os.getenv("EXOTEL_PHONE_NUMBER", "+18005550199")
    
    # LLM Settings (Anthropic / OpenAI format)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "claude-3-5-sonnet-20241022")

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
