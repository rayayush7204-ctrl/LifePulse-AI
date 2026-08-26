"""
GPS / Coordinate Validation Tests.

Verifies that:
1. Valid coordinates are accepted and flow through the request workflow.
2. Invalid latitude (out of range) is rejected with 422.
3. Invalid longitude (out of range) is rejected with 422.
4. Missing coordinates are rejected with 422 (no silent SF fallback).
5. Edge cases: Null Island (0,0), polar boundaries (-90/90, -180/180) are accepted.
6. San Francisco fallback coordinates (37.7631) do NOT appear in error responses.
7. String coordinates that parse to valid floats are accepted.
8. Non-numeric coordinate strings are rejected.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


# ── Valid base payload (will be modified per test) ──────────────
def _base_payload(**overrides):
    base = {
        "patient_name": "GPS Test Patient",
        "requester_phone": "+14155559999",
        "hospital_name": "GPS Test Hospital",
        "blood_type": "O-",
        "donation_type": "WHOLE_BLOOD",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "notes": "GPS validation test"
    }
    base.update(overrides)
    return base


# ── 1. Valid real GPS coordinates ─────────────────────────────────

@pytest.mark.asyncio
async def test_valid_real_coordinates():
    """Request with valid real-world coordinates succeeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=40.7128, longitude=-74.0060)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["request"]["latitude"] == 40.7128
        assert data["request"]["longitude"] == -74.0060


@pytest.mark.asyncio
async def test_valid_coordinates_different_city():
    """Request with valid Bangalore coordinates succeeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=12.9716, longitude=77.5946)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["request"]["latitude"] == 12.9716
        assert data["request"]["longitude"] == 77.5946


# ── 2. Invalid latitude ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_latitude_too_high():
    """Latitude > 90 is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=999.0, longitude=-74.0060)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422
        body = res.json()
        # Must NOT contain SF fallback coordinates
        assert "37.7631" not in str(body)


@pytest.mark.asyncio
async def test_invalid_latitude_too_low():
    """Latitude < -90 is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=-91.0, longitude=-74.0060)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


# ── 3. Invalid longitude ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_longitude_too_high():
    """Longitude > 180 is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=40.7128, longitude=999.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422
        body = res.json()
        assert "-122.4578" not in str(body)


@pytest.mark.asyncio
async def test_invalid_longitude_too_low():
    """Longitude < -180 is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=40.7128, longitude=-181.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


# ── 4. Missing coordinates ───────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_latitude():
    """Request without latitude is rejected (no silent SF fallback)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload()
        del payload["latitude"]
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_missing_longitude():
    """Request without longitude is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload()
        del payload["longitude"]
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_missing_both_coordinates():
    """Request without both coordinates is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload()
        del payload["latitude"]
        del payload["longitude"]
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


# ── 5. Edge cases ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_null_island_coordinates():
    """Null Island (0,0) is valid — it's a real coordinate, not a fallback."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=0.0, longitude=0.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["request"]["latitude"] == 0.0
        assert data["request"]["longitude"] == 0.0


@pytest.mark.asyncio
async def test_polar_boundary_south():
    """Boundary: lat=-90, lon=-180 is valid."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=-90.0, longitude=-180.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_polar_boundary_north():
    """Boundary: lat=90, lon=180 is valid."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=90.0, longitude=180.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200


# ── 6. String coordinates ────────────────────────────────────────

@pytest.mark.asyncio
async def test_string_coordinates_valid():
    """Stringified valid floats are accepted (coerced to float)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude="40.7128", longitude="-74.0060")
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["request"]["latitude"] == 40.7128


@pytest.mark.asyncio
async def test_string_coordinates_invalid():
    """Non-numeric coordinate strings are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude="not-a-number", longitude="-74.0060")
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422


# ── 7. Verify no SF fallback in runtime paths ────────────────────

@pytest.mark.asyncio
async def test_no_sf_fallback_on_invalid_coordinates():
    """When coordinates are invalid, response must NOT contain SF fallback values."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=999.0, longitude=999.0)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 422
        body_str = str(res.json())
        assert "37.7631" not in body_str
        assert "-122.4578" not in body_str


# ── 8. Valid coordinates continue through normal workflow ────────

@pytest.mark.asyncio
async def test_valid_coordinates_normal_workflow():
    """Complete request workflow with valid coordinates produces matching data."""
    import asyncio
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = _base_payload(latitude=37.7749, longitude=-122.4194)
        res = await ac.post("/api/v1/requests/", json=payload)
        assert res.status_code == 200
        req_id = res.json()["request"]["id"]

        # Give background matching time to run
        await asyncio.sleep(2)

        # Fetch request status
        status_res = await ac.get(f"/api/v1/requests/{req_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        # The request coordinates should be the ones we submitted, not SF fallback
        assert status_data["request"]["latitude"] == 37.7749
        assert status_data["request"]["longitude"] == -122.4194
