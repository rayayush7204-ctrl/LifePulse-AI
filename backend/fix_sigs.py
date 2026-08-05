with open('app/api/requests.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix submit_emergency_request
old_sig_1 = '''async def submit_emergency_request(
    payload: BloodRequestCreate,
    repo: DatabaseRepository = Depends(get_repository),
    background_tasks: BackgroundTasks,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):'''
new_sig_1 = '''async def submit_emergency_request(
    payload: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    repo: DatabaseRepository = Depends(get_repository),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):'''
content = content.replace(old_sig_1, new_sig_1)

# Fix get_nearby_requests
old_sig_2 = '''async def get_nearby_requests(
    repo: DatabaseRepository = Depends(get_repository),
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(25.0, description="Search radius in km")
):'''
new_sig_2 = '''async def get_nearby_requests(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(25.0, description="Search radius in km"),
    repo: DatabaseRepository = Depends(get_repository)
):'''
content = content.replace(old_sig_2, new_sig_2)

# Wait, what if old_sig_2 isn't exact? I'll use regex.
import re
content = re.sub(
    r'async def get_nearby_requests\(\n\s+repo: DatabaseRepository = Depends\(get_repository\),\n\s+lat: float = Query\(..., description="Latitude"\),\n\s+lon: float = Query\(..., description="Longitude"\),\n\s+radius_km: float = Query\(25\.0, description="Search radius in km"\)\n\):',
    'async def get_nearby_requests(\n    lat: float = Query(..., description="Latitude"),\n    lon: float = Query(..., description="Longitude"),\n    radius_km: float = Query(25.0, description="Search radius in km"),\n    repo: DatabaseRepository = Depends(get_repository)\n):',
    content
)

with open('app/api/requests.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed requests.py")
