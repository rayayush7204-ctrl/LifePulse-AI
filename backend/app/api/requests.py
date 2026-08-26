"""
Blood Requests Router.
Endpoints for submitting emergency requests, fetching live match status, audit logs, and triggering ring escalation.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends, status
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.models.schemas import BloodRequestCreate, BloodRequestResponse, DonorMatchResponse, SubmitRequestResponse
from app.database import DatabaseRepository, get_repository
from app.websockets.connection_manager import manager, WSEventType
from app.api.auth import get_current_user_optional, get_current_user_required
from app.services.matching_engine import MatchingEngine
from app.services.emergency_state_machine import EmergencyStateMachine, EmergencyState
from app.services.escalation_engine import escalation_engine

router = APIRouter(prefix="/requests", tags=["Emergency Requests"])

def sanitize_match_privacy(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies privacy-safe masking for donor information prior to donor acceptance.
    Exposes full name, phone number, and exact coordinates ONLY AFTER donor accepts.
    """
    m = {**match}
    status = m.get("status", "NOTIFIED")
    is_accepted = status in ("ACCEPTED", "EN_ROUTE", "ARRIVED")

    if not is_accepted:
        # Mask donor name
        raw_name = m.get("donor_name") or m.get("donor", {}).get("name") or "Donor Candidate"
        name_parts = raw_name.strip().split()
        if len(name_parts) > 1:
            masked_name = f"{name_parts[0]} {name_parts[-1][0]}."
        else:
            masked_name = f"{raw_name[:3]}***"

        m["donor_name"] = masked_name
        m["donor_phone"] = "Consent Required"
        if "donor" in m and isinstance(m["donor"], dict):
            m["donor"] = {
                **m["donor"],
                "name": masked_name,
                "phone": "Consent Required"
            }

    return m

@router.post("/", response_model=SubmitRequestResponse)
async def submit_emergency_request(
    payload: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    repo: DatabaseRepository = Depends(get_repository),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Submits an emergency blood request and instantly starts background matching.
    """
    try:
        req_dict = payload.model_dump(mode='json')
        for k in ["blood_type", "donation_type", "urgency_level"]:
            if hasattr(req_dict.get(k), "value"):
                req_dict[k] = req_dict[k].value

        if current_user:
            req_dict["requester_user_id"] = current_user["id"]

        # 1. Ensure initial status is CREATED
        req_dict["status"] = EmergencyState.CREATED.value

        # 2. Store request in DB
        saved_req = repo.create_request(req_dict)
        req_id = saved_req["id"]

        # 3. Add initial timeline event via State Machine (so it broadcasts if anyone is connected, though they connect right after)
        await EmergencyStateMachine.transition(
            req_id, 
            EmergencyState.CREATED, 
            "Emergency broadcast received. Initializing engines...",
            {"blood_type": req_dict["blood_type"]}
        )

        # 4. Trigger background matching
        import asyncio
        asyncio.create_task(MatchingEngine.run_matching_cycle(req_id))

        return {
            "message": "Emergency request submitted and background processing started.",
            "request": saved_req,
            "matching_summary": {"request_id": req_id, "status": "CREATED", "eligible_count": 0}
        }
    except Exception as err:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to create emergency request.")

@router.get("/nearby", response_model=List[Dict[str, Any]])
async def get_nearby_requests(
    repo: DatabaseRepository = Depends(get_repository),
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(50.0, description="Search radius in km")
):
    """
    Returns active (non-fulfilled/cancelled) emergency requests within radius_km, sorted by distance.
    """
    from app.matching.hard_filters import calculate_haversine_distance_km, calculate_bounding_box

    bbox = calculate_bounding_box(lat, lon, radius_km)
    all_requests = repo.list_requests(bbox=bbox)
    active = [r for r in all_requests if r.get("status") not in ("FULFILLED", "CANCELLED")]
    nearby = []
    for req in active:
        r_lat = req.get("latitude")
        r_lon = req.get("longitude")
        if r_lat is None or r_lon is None:
            continue
        dist = round(calculate_haversine_distance_km(lat, lon, r_lat, r_lon), 2)
        if dist <= radius_km:
            req_copy = {**req, "distance_from_user_km": dist}
            nearby.append(req_copy)
    nearby.sort(key=lambda x: x["distance_from_user_km"])
    return nearby

@router.get("/{request_id}", response_model=Dict[str, Any])
async def get_request_status(request_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Fetches live request details and match progress with privacy masking.
    """
    req = repo.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail=f"Blood request '{request_id}' not found.")
    
    matches = repo.get_matches_for_request(request_id)
    accepted = [m for m in matches if m["status"] in ("ACCEPTED", "EN_ROUTE", "ARRIVED")]
    
    sanitized_matches = [sanitize_match_privacy(m) for m in matches]

    return {
        "request": req,
        "matches_count": len(matches),
        "accepted_count": len(accepted),
        "matches": sanitized_matches,
        "nearby_blood_banks": escalation_engine.find_nearby_blood_banks(repo, req)
    }

@router.get("/{request_id}/matches", response_model=List[Dict[str, Any]])
async def list_request_matches(request_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Lists matched donors and their live response statuses with privacy masking.
    """
    matches = repo.get_matches_for_request(request_id)
    return [sanitize_match_privacy(m) for m in matches]

@router.get("/{request_id}/audit", response_model=List[Dict[str, Any]])
async def get_request_audit_trail(request_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Fetches explainable audit trail for medical compliance.
    """
    return repo.get_audit_logs_for_request(request_id)

@router.post("/{request_id}/escalate")
async def trigger_escalation(request_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Manually or timer-triggered ring escalation.
    """
    res = await escalation_engine.check_and_escalate_ring(repo, request_id)
    await manager.broadcast_to_request(request_id, {"type": "RING_ESCALATED", "data": res})
    return res

@router.get("/{request_id}/share", response_model=Dict[str, Any])
async def get_shareable_request_data(request_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Returns a public-safe subset of request data for social sharing links.
    """
    req = repo.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
    return {
        "request_id": req.get("id"),
        "blood_type": req.get("blood_type"),
        "units_needed": req.get("units_needed"),
        "hospital_name": req.get("hospital_name"),
        "urgency_level": req.get("urgency_level"),
        "status": req.get("status"),
        "created_at": req.get("created_at"),
    }

# Terminal states that cannot be cancelled
_TERMINAL_STATES = {"CLOSED", "CANCELLED", "DONATION_STARTED", "DONATION_COMPLETED"}

@router.patch("/{request_id}/cancel", response_model=Dict[str, Any])
async def cancel_emergency_request(
    request_id: str,
    repo: DatabaseRepository = Depends(get_repository),
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """
    Cancels an active emergency request.
    Only the original requester can cancel their own request.
    Requests without an owner (legacy/anonymous) cannot be cancelled via this endpoint.
    """
    # 1. Verify request exists
    req = repo.get_request(request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request '{request_id}' not found."
        )

    # 2. Authorization: owner-only
    requester_user_id = req.get("requester_user_id")
    if not requester_user_id:
        # Legacy/anonymous request — no owner recorded, cannot be cancelled by regular users
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This request has no registered owner and cannot be cancelled without admin authorization."
        )
    if requester_user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel this request."
        )

    # 3. Verify request is not already terminal
    previous_status = req.get("status", "CREATED")
    if previous_status in _TERMINAL_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request cannot be cancelled — current status is '{previous_status}'."
        )

    # 4. Cancel pending/actionable donor matches (preserves ACCEPTED, DECLINED, etc.)
    cancelled_matches_count = repo.cancel_pending_matches_for_request(request_id)

    # 5. Transition to CANCELLED via state machine (updates DB, records timeline event, broadcasts WS)
    await EmergencyStateMachine.transition(
        request_id,
        EmergencyState.CANCELLED,
        "Emergency request cancelled by requester.",
        {"cancelled_by": current_user["id"], "previous_status": previous_status}
    )

    # 6. Broadcast dedicated REQUEST_CANCELLED event via WebSocket
    cancelled_at = datetime.now(timezone.utc).isoformat()
    await manager.broadcast_to_request(request_id, {
        "type": WSEventType.REQUEST_CANCELLED,
        "request_id": request_id,
        "previous_status": previous_status,
        "new_status": "CANCELLED",
        "cancelled_at": cancelled_at,
        "message": "Emergency request has been cancelled."
    })

    return {
        "request_id": request_id,
        "previous_status": previous_status,
        "new_status": "CANCELLED",
        "cancelled_at": cancelled_at,
        "cancelled_matches_count": cancelled_matches_count,
        "message": "Emergency request cancelled successfully."
    }
