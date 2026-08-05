import re

with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
content = content.replace('from app.database import db', 'from app.database import DatabaseRepository, get_repository, SessionLocal')
content = content.replace('from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body', 
                          'from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Depends, Request\\nfrom fastapi.responses import JSONResponse\\nfrom sqlalchemy.exc import SQLAlchemyError\\nfrom app.utils.exceptions import AppException\\nfrom app.utils.logger import logger as app_logger')

content = content.replace('logger = logging.getLogger("main")', 'logger = app_logger')

# 2. Refactor lifespan
new_lifespan = '''@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables & default hospital reserves exist
    logger.info("Initializing LifePulse AI Blood Donation Platform...")
    session = SessionLocal()
    repo = DatabaseRepository(session)
    try:
        existing_hospitals = repo.list_hospitals()
        if not existing_hospitals:
            seed_banks = generate_synthetic_hospitals()
            for b in seed_banks:
                repo.add_hospital(b)
            session.commit()
            logger.info(f"Initialized {len(seed_banks)} default reference hospital blood reserves.")
        else:
            logger.info(f"Loaded {len(existing_hospitals)} hospital blood reserves from database.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to initialize database: {e}")
    finally:
        session.close()
        
    yield
    logger.info("Shutting down application...")'''

content = re.sub(r'@asynccontextmanager\\nasync def lifespan\(app: FastAPI\):.*?(?=app = FastAPI\()', new_lifespan + '\\n\\n', content, flags=re.DOTALL)

# 3. Add exception handlers after app = FastAPI(...)
handlers = '''
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(f"AppException: {exc.message}")
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message, "detail": exc.payload})

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(status_code=500, content={"message": "Internal Database Error."})
'''
content = content.replace(')\\n\\n# Enable CORS', ')\\n' + handlers + '\\n# Enable CORS')

# 4. Refactor endpoints
content = content.replace('async def health_check():', 'async def health_check(repo: DatabaseRepository = Depends(get_repository)):')
content = content.replace('len(db.list_donors())', 'len(repo.list_donors())')
content = content.replace('len(db.list_hospitals())', 'len(repo.list_hospitals())')
content = content.replace('len(db.list_requests())', 'len(repo.list_requests())')

content = content.replace('async def get_voice_script(request_id: str, donor_name: str = "Donor"):', 'async def get_voice_script(request_id: str, donor_name: str = "Donor", repo: DatabaseRepository = Depends(get_repository)):')
content = content.replace('req = db.get_request(request_id)', 'req = repo.get_request(request_id)')

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py refactored")
