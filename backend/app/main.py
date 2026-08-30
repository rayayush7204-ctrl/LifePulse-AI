"""
FastAPI Main Application Gateway.
Initializes production persistent database, API routes, authentication, WebSockets, and CORS middleware.
"""

import sys
import os

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.utils.exceptions import AppException
from app.utils.logger import logger as app_logger
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import Dict, Any

from app.config import settings
from app.database import DatabaseRepository, get_repository, SessionLocal
from app.api import requests, donors, hospitals, auth, notifications
from app.websockets.connection_manager import manager
from app.services.ai_parser import parse_emergency_request_text, parse_voice_sos_transcript
from app.services.voice_script import generate_voice_agent_script
from scripts.seed_data import generate_synthetic_hospitals

logging.basicConfig(level=logging.INFO)
logger = app_logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables & default hospital reserves exist
    from app.database import init_db
    init_db()
    logger.info("Initializing LifePulse AI Blood Donation Platform...")
    db_session = SessionLocal()
    db = DatabaseRepository(db_session)
    existing_hospitals = db.list_hospitals()
    if not existing_hospitals:
        seed_banks = generate_synthetic_hospitals()
        for b in seed_banks:
            db.add_hospital(b)
        logger.info(f"Initialized {len(seed_banks)} default reference hospital blood reserves.")
    else:
        logger.info(f"Loaded {len(existing_hospitals)} hospital blood reserves from database.")
    db_session.close()
    yield
    logger.info("Shutting down application...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade AI-powered Emergency Blood Donor Matching Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for PWA frontend
origins = [origin.strip() for origin in settings.FRONTEND_CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(requests.router, prefix=settings.API_V1_STR)
app.include_router(donors.router, prefix=settings.API_V1_STR)
app.include_router(hospitals.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=f"{settings.API_V1_STR}/notifications")

@app.get("/health")
async def health_check(repo: DatabaseRepository = Depends(get_repository)):
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "donors_count": len(repo.list_donors()),
        "hospitals_count": len(repo.list_hospitals()),
        "requests_count": len(repo.list_requests())
    }

# AI NLP Endpoint
@app.post(f"{settings.API_V1_STR}/ai/parse-request")
async def parse_free_text_request(payload: Dict[str, str] = Body(...)):
    raw_text = payload.get("text", "")
    if not raw_text:
        raise HTTPException(status_code=400, detail="Missing 'text' field.")
    return await parse_emergency_request_text(raw_text)

@app.post(f"{settings.API_V1_STR}/ai/voice-sos")
async def process_voice_sos_audio_transcript(payload: Dict[str, str] = Body(...)):
    transcript = payload.get("transcript", "") or payload.get("text", "")
    if not transcript:
        raise HTTPException(status_code=400, detail="Missing 'transcript' field.")
    return await parse_voice_sos_transcript(transcript)

@app.post(f"{settings.API_V1_STR}/ai/voice-script")
async def get_voice_script(request_id: str, donor_name: str = "Donor", repo: DatabaseRepository = Depends(get_repository)):
    req = repo.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    script = generate_voice_agent_script(req, donor_name)
    return {"request_id": request_id, "donor_name": donor_name, "script": script}

# WebSocket Gateway Endpoints

@app.websocket("/api/v1/ws/user")
async def websocket_user_connection(websocket: WebSocket, token: str):
    user_id = None
    try:
        from jose import jwt, JWTError
        from app.api.auth import ALGORITHM
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception as e:
        logger.error(f"User WebSocket auth failed: {e}")

    if not user_id:
        await websocket.close(code=1008)
        return

    await manager.connect_user(websocket, user_id)
    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_user(websocket, user_id)

@app.websocket("/ws/requests/{request_id}")
async def websocket_request_tracker(websocket: WebSocket, request_id: str, token: str = None):
    if token:
        try:
            from jose import jwt, JWTError
            from app.api.auth import ALGORITHM
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except Exception as e:
            logger.warning(f"WebSocket auth failed, falling back to anonymous: {e}")

    await manager.connect(websocket, request_id)
    
    # Push initial state snapshot so reconnecting clients can rebuild the full UI.
    # IMPORTANT: signal_connected() is called AFTER the snapshot send to guarantee
    # the snapshot always arrives before any ring escalation broadcast fires.
    try:
        with SessionLocal() as session:
            repo = DatabaseRepository(session)
            req = repo.get_request(request_id)
            if req:
                # Timeline history
                timeline = repo.get_timeline_events_for_request(request_id)
                # Accepted donor + GPS state
                matches = repo.get_matches_for_request(request_id)
                accepted_match = next(
                    (m for m in matches if m["status"] in ("ACCEPTED", "EN_ROUTE", "ARRIVED")), None
                )
                gps_position = None
                eta = None
                countdown_remaining = None
                if accepted_match:
                    gps_position = {
                        "lat": accepted_match.get("donor_latitude"),
                        "lng": accepted_match.get("donor_longitude"),
                    }
                    eta = accepted_match.get("eta_minutes")

                from app.websockets.connection_manager import WSEventType
                snapshot = {
                    "current_state": req.get("status"),
                    "timeline": timeline,
                    "accepted_match": accepted_match,
                    "gps_position": gps_position,
                    "eta": eta,
                    "countdown_remaining": countdown_remaining,
                }
                await websocket.send_json({
                    "type": WSEventType.CONNECTION_STATE,
                    "request_id": request_id,
                    "data": snapshot
                })
    except Exception as e:
        logger.error(f"Failed to send WS snapshot: {e}")

    # Now signal that client is ready — this unblocks the matching engine
    # and allows ring escalation broadcasts to fire on this connection.
    manager.signal_connected(request_id)

    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
            logger.debug(f"WS ping from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, request_id)
