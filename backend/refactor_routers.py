import re

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    content = content.replace('from app.database import db', 'from app.database import DatabaseRepository, get_repository')

    # Global replace db. to repo.
    content = re.sub(r'\bdb\.', 'repo.', content)

    # In donors.py
    if 'donors.py' in filepath:
        content = content.replace('from app.models.schemas import DonorCreate, DonorResponse, DonorActionPayload, DonorLocationUpdate, DonorMedicalScreeningPayload',
                                  'from app.models.schemas import DonorCreate, DonorResponse, DonorActionPayload, DonorLocationUpdate, DonorMedicalScreeningPayload, SubmitScreeningResponse, DonorRespondResponse, DonorLocationUpdateResponse')
        content = content.replace('@router.post("/", response_model=Dict[str, Any])\nasync def register_donor(payload: DonorCreate, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):',
                                  '@router.post("/", response_model=DonorResponse)\nasync def register_donor(payload: DonorCreate, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional), repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('@router.get("/", response_model=List[Dict[str, Any]])\nasync def list_all_donors():',
                                  '@router.get("/", response_model=List[DonorResponse])\nasync def list_all_donors(repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('@router.post("/screening", response_model=Dict[str, Any])\nasync def submit_medical_screening(payload: DonorMedicalScreeningPayload):',
                                  '@router.post("/screening", response_model=SubmitScreeningResponse)\nasync def submit_medical_screening(payload: DonorMedicalScreeningPayload, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('@router.get("/{donor_id}/screening", response_model=Dict[str, Any])\nasync def get_donor_screening_record(donor_id: str):',
                                  '@router.get("/{donor_id}/screening", response_model=Dict[str, Any])\nasync def get_donor_screening_record(donor_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('@router.post("/respond", response_model=Dict[str, Any])\nasync def respond_to_emergency_alert(payload: DonorActionPayload):',
                                  '@router.post("/respond", response_model=DonorRespondResponse)\nasync def respond_to_emergency_alert(payload: DonorActionPayload, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('@router.post("/location")\nasync def update_donor_location(donor_id: str, payload: DonorLocationUpdate):',
                                  '@router.post("/location", response_model=DonorLocationUpdateResponse)\nasync def update_donor_location(donor_id: str, payload: DonorLocationUpdate, repo: DatabaseRepository = Depends(get_repository)):')

    if 'requests.py' in filepath:
        content = content.replace('from app.models.schemas import BloodRequestCreate, BloodRequestResponse, DonorMatchResponse',
                                  'from app.models.schemas import BloodRequestCreate, BloodRequestResponse, DonorMatchResponse, SubmitRequestResponse')
        content = content.replace('async def submit_emergency_request(\n    payload: BloodRequestCreate,', 'async def submit_emergency_request(\n    payload: BloodRequestCreate,\n    repo: DatabaseRepository = Depends(get_repository),')
        content = content.replace('@router.post("/", response_model=Dict[str, Any])', '@router.post("/", response_model=SubmitRequestResponse)')
        
        content = content.replace('async def get_request_status(request_id: str):', 'async def get_request_status(request_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('async def list_request_matches(request_id: str):', 'async def list_request_matches(request_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('async def get_request_audit_trail(request_id: str):', 'async def get_request_audit_trail(request_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        
        content = content.replace('async def get_nearby_requests(\n    lat: float', 'async def get_nearby_requests(\n    repo: DatabaseRepository = Depends(get_repository),\n    lat: float')
        content = content.replace('async def get_shareable_request_data(request_id: str):', 'async def get_shareable_request_data(request_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('async def trigger_escalation(request_id: str):', 'async def trigger_escalation(request_id: str, repo: DatabaseRepository = Depends(get_repository)):')
        
    if 'hospitals.py' in filepath:
        content = content.replace('async def list_blood_banks():', 'async def list_blood_banks(repo: DatabaseRepository = Depends(get_repository)):')
        content = content.replace('from fastapi import APIRouter', 'from fastapi import APIRouter, Depends')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

refactor_file('app/api/donors.py')
refactor_file('app/api/requests.py')
refactor_file('app/api/hospitals.py')
print("Done refactoring routers")
