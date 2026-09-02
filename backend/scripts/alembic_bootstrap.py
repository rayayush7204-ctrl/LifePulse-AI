"""
Alembic Bootstrap Script.

Detects whether the production database was created by SQLAlchemy create_all()
before Alembic was introduced, and stamps the correct Alembic revision if needed.

Safe to run repeatedly:
- If alembic_version is already stamped -> does nothing.
- If database has application tables but no stamp -> stamps 4cba4d66e283 (current head).
- If database is empty -> does nothing (lets alembic upgrade head create everything).

Does NOT execute any migration SQL. Does NOT drop or recreate tables.
"""

import sys
import os

# Ensure the backend directory is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import inspect, text
from app.config import settings

# The revision that matches the schema created by create_all() on the current db_models.py
PRE_ALEMBIC_HEAD = "4cba4d66e283"


def get_engine():
    """Create a fresh engine using the same connection logic as database.py."""
    from sqlalchemy import create_engine

    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    engine_kwargs = {}
    if db_url.startswith("postgresql"):
        engine_kwargs["pool_size"] = 2
        engine_kwargs["max_overflow"] = 0
    elif db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(db_url, pool_pre_ping=True, **engine_kwargs)


def bootstrap():
    """
    Detect database state and stamp Alembic version if needed.

    Returns:
        str: One of "stamped", "already_stamped", "empty_db", or "error".
    """
    engine = get_engine()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    print(f"[alembic_bootstrap] Detected {len(existing_tables)} existing tables.")

    # Case 1: alembic_version table exists — check if it has a stamp
    if "alembic_version" in existing_tables:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            if row:
                print(f"[alembic_bootstrap] Already stamped at revision: {row[0]}. No action needed.")
                return "already_stamped"
            else:
                print("[alembic_bootstrap] alembic_version table exists but is empty.")
                # Fall through to stamping logic below

    # Case 2: Application tables exist but no Alembic stamp — pre-Alembic database
    # We require strict validation before stamping.
    if "users" in existing_tables:
        print(f"[alembic_bootstrap] Pre-Alembic database detected. Verifying schema...")

        required_tables = [
            "users", "donor_profiles", "donor_medical_screenings",
            "emergency_requests", "donor_matches", "donation_histories",
            "hospitals", "audit_logs"
        ]
        
        missing_tables = [t for t in required_tables if t not in existing_tables]
        if missing_tables:
            raise RuntimeError(f"Database schema mismatch: missing expected tables: {missing_tables}")
            
        columns = [c["name"] for c in inspector.get_columns("emergency_requests")]
        
        # Verify the location overhaul state
        expected_columns = ["location_name", "location_address", "location_source"]
        missing_cols = [c for c in expected_columns if c not in columns]
        if missing_cols:
             raise RuntimeError(f"Database schema mismatch: emergency_requests missing columns: {missing_cols}")
             
        if "hospital_name" in columns:
             raise RuntimeError("Database schema mismatch: emergency_requests still has hospital_name column (not at head).")

        print(f"[alembic_bootstrap] Schema verified as equivalent to {PRE_ALEMBIC_HEAD}.")
        print(f"[alembic_bootstrap] Stamping revision {PRE_ALEMBIC_HEAD} without running migrations...")

        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))

        # Set the database URL in the Alembic config
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

        command.stamp(alembic_cfg, PRE_ALEMBIC_HEAD)
        print(f"[alembic_bootstrap] Successfully stamped {PRE_ALEMBIC_HEAD}.")
        return "stamped"

    # Case 3: Empty database — let alembic upgrade head handle it
    print("[alembic_bootstrap] Empty database detected. Alembic upgrade will create schema.")
    return "empty_db"


if __name__ == "__main__":
    try:
        result = bootstrap()
        print(f"[alembic_bootstrap] Result: {result}")
    except Exception as e:
        print(f"[alembic_bootstrap] ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
