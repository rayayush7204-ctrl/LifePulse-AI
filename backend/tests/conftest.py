import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    yield
