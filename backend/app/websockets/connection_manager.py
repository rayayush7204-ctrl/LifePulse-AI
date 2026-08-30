"""
WebSocket Connection Manager.
Broadcasts real-time emergency events (donor response, location updates, ring escalations) to active dashboards.
Supports typed progress events for granular dispatch experience (search stats, donor markers, countdowns).
"""

from typing import Dict, List, Any
from fastapi import WebSocket
import json
import asyncio
import logging

logger = logging.getLogger("websocket_manager")

# ── Event Type Constants ────────────────────────────────────────────
class WSEventType:
    """Typed event constants for WebSocket messages."""
    STATE_TRANSITION = "STATE_TRANSITION"
    SEARCH_PROGRESS = "SEARCH_PROGRESS"
    DONOR_MARKERS = "DONOR_MARKERS"
    RING_COUNTDOWN = "RING_COUNTDOWN"
    DONOR_ACCEPTED_HIGHLIGHT = "DONOR_ACCEPTED_HIGHLIGHT"
    ETA_UPDATE = "ETA_UPDATE"
    GPS_UPDATE = "GPS_UPDATE"
    DONOR_LOCATION_UPDATED = "DONOR_LOCATION_UPDATED"
    DONOR_STATUS_CHANGED = "DONOR_STATUS_CHANGED"
    RING_ESCALATED = "RING_ESCALATED"
    CONNECTION_STATE = "CONNECTION_STATE"
    REQUEST_CANCELLED = "REQUEST_CANCELLED"
    DONOR_WITHDRAWN = "DONOR_WITHDRAWN"


class ConnectionManager:
    def __init__(self):
        # Maps request_id -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Maps request_id -> asyncio.Event for initial connection sync
        self.connection_events: Dict[str, asyncio.Event] = {}
        # Maps user_id -> list of active WebSocket connections for personal/fallback notifications
        self.user_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, request_id: str):
        await websocket.accept()
        self.active_connections.setdefault(request_id, []).append(websocket)
        # NOTE: Event is NOT set here. Call signal_connected() after sending
        # the initial snapshot so the snapshot always arrives before broadcasts.
        logger.info(f"[WS CONNECTED] Client connected to request {request_id}")

    def signal_connected(self, request_id: str):
        """Signal that connection is fully ready (snapshot sent). Unblocks matching
        engine wait and allows ring escalation broadcasts to start firing."""
        if request_id not in self.connection_events:
            self.connection_events[request_id] = asyncio.Event()
        self.connection_events[request_id].set()

    def disconnect(self, websocket: WebSocket, request_id: str):
        if request_id in self.active_connections:
            if websocket in self.active_connections[request_id]:
                self.active_connections[request_id].remove(websocket)
            if not self.active_connections[request_id]:
                del self.active_connections[request_id]
                if request_id in self.connection_events:
                    del self.connection_events[request_id]
        logger.info(f"[WS DISCONNECTED] Client disconnected from request {request_id}")

    async def wait_for_connection(self, request_id: str, timeout: float = 5.0) -> bool:
        """
        Wait until at least one WebSocket client connects to this request_id, 
        or until the timeout expires.
        """
        if request_id not in self.connection_events:
            self.connection_events[request_id] = asyncio.Event()
        
        if self.get_connection_count(request_id) > 0:
            return True
            
        try:
            await asyncio.wait_for(self.connection_events[request_id].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"[WS TIMEOUT] No client connected for request {request_id} within {timeout}s.")
            return False

    async def broadcast_to_request(self, request_id: str, payload: Dict[str, Any]):
        """
        Broadcasts an event payload to all clients connected to a specific request ID.
        """
        if request_id in self.active_connections:
            disconnected = []
            for ws in self.active_connections[request_id]:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.error(f"[WS ERROR] Broadcast failed: {e}")
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws, request_id)

    async def broadcast_progress(self, request_id: str, event_type: str, data: Dict[str, Any]):
        """
        Sends lightweight progress events (donor count, filter counts, countdown)
        without persisting to the database. Used for high-frequency real-time updates.
        """
        payload = {
            "type": event_type,
            "request_id": request_id,
            "data": data
        }
        await self.broadcast_to_request(request_id, payload)

    def get_connection_count(self, request_id: str) -> int:
        """Returns the number of active connections for a given request."""
        return len(self.active_connections.get(request_id, []))

    # ── User Connections (for Personal Fallback Notifications) ──

    async def connect_user(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.user_connections.setdefault(user_id, []).append(websocket)
        logger.info(f"[WS CONNECTED] User {user_id} connected for personal notifications.")

    def disconnect_user(self, websocket: WebSocket, user_id: str):
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        logger.info(f"[WS DISCONNECTED] User {user_id} disconnected.")

    async def send_personal_message(self, user_id: str, payload: Dict[str, Any]):
        """
        Sends an event payload specifically to a user's authenticated connections.
        Used for fallback push notifications (e.g., INCOMING_EMERGENCY).
        """
        if user_id in self.user_connections:
            disconnected = []
            for ws in self.user_connections[user_id]:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.error(f"[WS ERROR] Personal message failed for user {user_id}: {e}")
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect_user(ws, user_id)


manager = ConnectionManager()
