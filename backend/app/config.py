"""
Application Configuration Settings.
Reads environment variables or provides production-grade defaults.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Smart Blood Donation Network"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # Environment
    APP_ENV: str = os.getenv("APP_ENV", "development")
    
    # Database Settings (PostgreSQL engine configuration)
    FRONTEND_CORS_ORIGINS: str = os.getenv("FRONTEND_CORS_ORIGINS", "http://localhost:5173,http://localhost:8000")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    USE_SQLITE_FALLBACK: bool = os.getenv("USE_SQLITE_FALLBACK", "False").lower() == "true"
    
    # Redis Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Matching Engine Parameters
    DEFAULT_MAX_RADIUS_KM: float = 25.0
    DEFAULT_RING_SIZE: int = 5
    RING_ESCALATION_TIMEOUT_SECONDS: int = 45  # Ring 1 timeout before ring 2 fan-out
    
    # Exotel / Notification Credentials
    EXOTEL_SID: str = os.getenv("EXOTEL_SID", "")
    EXOTEL_TOKEN: str = os.getenv("EXOTEL_TOKEN", "")
    EXOTEL_PHONE_NUMBER: str = os.getenv("EXOTEL_PHONE_NUMBER", "")
    
    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    
    # LLM Settings (Anthropic / OpenAI format)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "claude-3-5-sonnet-20241022")

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
