"""
Donors Router.
Endpoints for donor registration, medical pre-screening, location/availability updates,
and responding to emergency alerts (ACCEPT/DECLINE/EN_ROUTE).
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Dict, Any, Optional
from app.models.schemas import DonorCreate, DonorResponse, DonorActionPayload, DonorLocationUpdate, DonorMedicalScreeningPayload, SubmitScreeningResponse, DonorRespondResponse, DonorLocationUpdateResponse
from app.database import DatabaseRepository, get_repository
from app.websockets.connection_manager import manager
from app.matching.medical_prescreening import evaluate_medical_prescreening
from app.api.auth import get_current_user_optional
from app.services.emergency_state_machine import EmergencyStateMachine, EmergencyState
from app.services.gps_service import GPSService
import asyncio

router = APIRouter(prefix="/donors", tags=["Donors"])

@router.post("/", response_model=DonorResponse)
async def register_donor(payload: DonorCreate, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional), repo: DatabaseRepository = Depends(get_repository)):
    """
    Registers or updates a donor profile in the database.
    If authenticated, links donor profile to user account.
    """
    donor_dict = payload.model_dump()
    donor_dict["blood_type"] = payload.blood_type.value
    if payload.last_donation_date:
        donor_dict["last_donation_date"] = payload.last_donation_date.isoformat()
    
    if current_user:
        donor_dict["user_id"] = current_user["id"]
        donor_dict["email"] = current_user.get("email")

    saved_donor = repo.add_donor(donor_dict)
    return saved_donor

@router.get("/", response_model=List[DonorResponse])
async def list_all_donors(repo: DatabaseRepository = Depends(get_repository)):
    """
    Lists registered donors in the system.
    """
    return repo.list_donors()

@router.post("/screening", response_model=SubmitScreeningResponse)
async def submit_medical_screening(payload: DonorMedicalScreeningPayload, repo: DatabaseRepository = Depends(get_repository)):
    """
    Submits a donor medical pre-screening questionnaire.
    Evaluates clinical rules and returns AI-assisted pre-screening status.
    """
    donor = repo.get_donor(payload.donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")

    screening_dict = payload.model_dump()
    result = evaluate_medical_prescreening(screening_dict)

    screening_record = {
        "donor_id": payload.donor_id,
        "age": payload.age,
        "weight_kg": payload.weight_kg,
        "has_fever_or_illness": payload.has_fever_or_illness,
        "recent_medication": payload.recent_medication,
        "recent_surgery": payload.recent_surgery,
        "recent_vaccination": payload.recent_vaccination,
        "pregnancy_status": payload.pregnancy_status,
        "recent_tattoo_or_piercing": payload.recent_tattoo_or_piercing,
        "travel_exposure_history": payload.travel_exposure_history,
        "screening_answers_json": screening_dict,
        "eligibility_status": result["eligibility_status"],
        "eligibility_reasons_json": result["eligibility_reasons"],
        "eligibility_flags_json": result["eligibility_flags"]
    }

    saved = repo.save_donor_screening(screening_record)

    return {
        "message": "Medical pre-screening evaluated successfully.",
        "screening": saved,
        "pre_screening_result": result
    }

@router.get("/{donor_id}/screening", response_model=Dict[str, Any])
async def get_donor_screening_record(donor_id: str, repo: DatabaseRepository = Depends(get_repository)):
    """
    Fetches donor medical screening record.
    """
    sc = repo.get_donor_screening(donor_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Screening record not found for this donor.")
    return sc

@router.post("/respond", response_model=DonorRespondResponse)
async def respond_to_emergency_alert(payload: DonorActionPayload, repo: DatabaseRepository = Depends(get_repository)):
    """
    Donor response endpoint (ACCEPT, DECLINE).
    Updates match status, transitions state machine, and starts GPS simulation if ACCEPTED.
    """
    match_rec = repo.get_match(payload.match_id)
    if not match_rec:
        raise HTTPException(status_code=404, detail=f"Match record '{payload.match_id}' not found.")

    new_status = payload.action.value
    donor_id = match_rec["donor_id"]
    req_id = match_rec["request_id"]
    
    if new_status == "ACCEPTED":
        # Atomically attempt to accept the emergency
        if not repo.try_accept_emergency(req_id):
            raise HTTPException(status_code=409, detail="Emergency request already accepted by another donor.")

    # Update match status in DB
    updated_match = repo.update_match_status(
        match_id=payload.match_id,
        status=new_status,
        eta_minutes=payload.eta_minutes
    )

    if new_status == "ACCEPTED":
        # State Machine Transition
        await EmergencyStateMachine.transition(
            req_id, 
            EmergencyState.DONOR_ACCEPTED, 
            "A donor has accepted the emergency request. Preparing for tracking...",
            {"match_id": payload.match_id, "donor_id": donor_id}
        )
        
        # Start GPS tracking immediately
        await EmergencyStateMachine.transition(
            req_id, 
            EmergencyState.TRACKING, 
            "GPS Link established. Tracking donor in real-time.",
            {"match_id": payload.match_id}
        )
        
        asyncio.create_task(GPSService.simulate_donor_drive(req_id, payload.match_id))

    return {
        "message": f"Match status updated to '{new_status}'",
        "match": updated_match
    }

@router.post("/location", response_model=DonorLocationUpdateResponse)
async def update_donor_location(donor_id: str, payload: DonorLocationUpdate, repo: DatabaseRepository = Depends(get_repository)):
    """
    Updates live GPS coordinates and availability for an en-route donor in the database.
    Recalculates ETA and broadcasts live GPS Radar update via WebSockets.
    """
    from app.matching.hard_filters import calculate_haversine_distance_km

    donor = repo.get_donor(donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")

    donor_update = {
        "id": donor_id,
        "latitude": payload.latitude,
        "longitude": payload.longitude
    }
    if payload.is_available is not None:
        donor_update["is_available"] = payload.is_available

    repo.add_donor(donor_update)

    active_updates = []
    matched_items = [m for m in repo.get_matches_for_request(payload.request_id) if m.get("donor_id") == donor_id] if payload.request_id else []

    for m in matched_items:
        req_id = m.get("request_id")
        req = repo.get_request(req_id) or {"latitude": 37.7631, "longitude": -122.4578}
        
        dist_km = round(calculate_haversine_distance_km(
            payload.latitude, payload.longitude,
            req.get("latitude", 37.7631), req.get("longitude", -122.4578)
        ), 2)
        speed = payload.speed_kmh or 35.0
        eta_mins = max(1, round((dist_km / speed) * 60))

        repo.add_match({
            "match_id": m["match_id"],
            "request_id": req_id,
            "donor_id": donor_id,
            "distance_km": dist_km,
            "donor_latitude": payload.latitude,
            "donor_longitude": payload.longitude,
            "eta_minutes": eta_mins
        })

        location_event_data = {
            "donor_id": donor_id,
            "donor_name": m.get("donor_name", donor.get("name", "Donor")),
            "donor_blood_type": m.get("donor_blood_type", donor.get("blood_type", "O-")),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "distance_km": dist_km,
            "eta_minutes": eta_mins,
            "speed_kmh": speed,
            "status": m.get("status", "EN_ROUTE"),
            "match_id": m.get("match_id"),
            "request_id": req_id
        }

        active_updates.append(location_event_data)
        await manager.broadcast_to_request(req_id, {"type": "DONOR_LOCATION_UPDATED", "data": location_event_data})

    return {
        "message": "Location updated and GPS Radar broadcasted.",
        "donor": repo.get_donor(donor_id),
        "location_updates": active_updates
    }
