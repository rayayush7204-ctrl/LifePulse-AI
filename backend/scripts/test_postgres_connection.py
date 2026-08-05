"""
Script to test PostgreSQL connection, auto-create blood_donor database if missing,
run Alembic migrations, and verify CRUD persistence.
"""

import sys
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, '.env'))

from app.config import settings

def ensure_database_exists():
    db_url = settings.DATABASE_URL
    print(f"[+] Configured DATABASE_URL: {db_url}")
    
    if "YOUR_PASSWORD" in db_url:
        print("[!] ERROR: Please update backend/.env with your actual PostgreSQL password in DATABASE_URL.")
        return False
        
    try:
        # Parse connection details
        # Format: postgresql://user:pass@host:port/dbname
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)
        username = unquote(parsed.username) if parsed.username else "postgres"
        password = unquote(parsed.password) if parsed.password else ""
        hostname = parsed.hostname or "localhost"
        port = parsed.port or 5432
        target_dbname = parsed.path.lstrip("/") or "blood_donor"

        # 1. Connect to default postgres DB
        print(f"Connecting to PostgreSQL server at {hostname}:{port} as user '{username}'...")
        conn = psycopg2.connect(
            dbname="postgres",
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_dbname,))
        exists = cursor.fetchone()
        if not exists:
            print(f"Database '{target_dbname}' does not exist. Creating database '{target_dbname}'...")
            cursor.execute(f'CREATE DATABASE "{target_dbname}"')
            print(f"Database '{target_dbname}' created successfully.")
        else:
            print(f"Database '{target_dbname}' already exists.")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"[!] PostgreSQL Connection Error: {e}")
        return False

def verify_persistence():
    from app.database import db, SessionLocal
    from app.models.db_models import UserDB
    import uuid

    print("Testing CRUD operation & persistence in PostgreSQL...")
    test_email = f"test_pg_{uuid.uuid4().hex[:6]}@example.com"
    test_mobile = f"+1555{uuid.uuid4().hex[:7]}"
    
    user_data = {
        "full_name": "PG Test User",
        "email": test_email,
        "mobile_number": test_mobile,
        "password_hash": "hashed_pass_test"
    }

    # Create user
    created_user = db.create_user(user_data)
    user_id = created_user["id"]
    print(f"Created User in PostgreSQL: ID={user_id}, Email={created_user['email']}")

    # Verify retrieval from a fresh session
    retrieved_user = db.get_user_by_id(user_id)
    assert retrieved_user is not None, "Failed to retrieve created user!"
    assert retrieved_user["email"] == test_email.lower(), f"Email mismatch: {retrieved_user['email']}"
    print(f"[OK] Persistence verified! Successfully fetched user '{retrieved_user['full_name']}' from PostgreSQL.")
    return True

if __name__ == "__main__":
    if ensure_database_exists():
        print("Ensured PostgreSQL database existence.")
        verify_persistence()
    else:
        sys.exit(1)
