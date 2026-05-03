@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  DPP 2.2.0 Services Startup
echo ============================================
echo.

REM Navigate to project root
cd /d "%~dp0"

echo Starting Backend Server (port 8002)...
start "Backend - DPP 2.2.0" cmd /k "cd backend && uvicorn app.main:app --reload --port 8002"

timeout /t 2

echo Starting Celery Worker...
start "Celery Worker - DPP 2.2.0" cmd /k "cd backend && celery -A celery_app worker --loglevel=info --pool=prefork"

timeout /t 2

echo Starting Frontend Dev Server (port 5175)...
start "Frontend - DPP 2.2.0" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================
echo All services started successfully!
echo ============================================
echo.
echo Access points:
echo   Frontend:  http://localhost:5175
echo   Backend:   http://localhost:8002
echo   Docs:      http://localhost:8002/docs
echo.
echo To stop services: Close each terminal window individually
echo.
pause
