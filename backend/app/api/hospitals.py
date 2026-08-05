"""
Hospitals & Blood Banks Router.
Endpoints for viewing regional blood bank inventory reserves and fallback options.
"""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.database import DatabaseRepository, get_repository

router = APIRouter(prefix="/hospitals", tags=["Hospitals & Blood Banks"])

@router.get("/", response_model=List[Dict[str, Any]])
async def list_blood_banks(repo: DatabaseRepository = Depends(get_repository)):
    """
    Lists registered blood banks and current stock inventory.
    """
    return repo.list_hospitals()
