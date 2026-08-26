from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.models.schemas import DeviceTokenCreate
from app.database import get_repository, DatabaseRepository
from app.api.auth import get_current_user_required

router = APIRouter()

@router.post("/device-token")
async def register_device_token(
    payload: DeviceTokenCreate,
    current_user: Dict[str, Any] = Depends(get_current_user_required),
    repo: DatabaseRepository = Depends(get_repository)
):
    """
    Registers an FCM device token for the authenticated user.
    """
    if not payload.token:
        raise HTTPException(status_code=400, detail="Token cannot be empty")
        
    res = repo.add_device_token(current_user["id"], payload.token, payload.platform)
    return {"status": "success", "token": res["token"]}
