@echo off
echo ========================================================
echo   Starting LifePulse AI - Smart Blood Donor Matcher
echo ========================================================
echo.

echo Starting FastAPI Backend Server on port 8000...
start "LifePulse AI - Backend Server (Port 8000)" cmd /k "cd /d "%~dp0backend" && (if exist ..\.venv\Scripts\python.exe (..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000) else (..\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000))"

timeout /t 3 /nobreak >nul

echo Starting Vite React Frontend Dev Server on port 3000...
start "LifePulse AI - Frontend Dev (Port 3000)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================================
echo   Both services have been launched in separate terminals!
echo   Frontend UI: http://localhost:3000
echo   Backend API Docs: http://localhost:8000/docs
echo ========================================================
pause
