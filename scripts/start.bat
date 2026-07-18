@echo off
chcp 65001 >nul 2>&1
title Cycle Master

set "ROOT=%~dp0.."

REM === Check Python ===
if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found
    echo Please run: cd backend ^&^& python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

REM === Clean old ports ===
echo Cleaning old ports...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM === Start Backend ===
echo Starting backend...
start "Cycle-Backend" /min cmd /k "cd /d %ROOT%\backend & %ROOT%\backend\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

REM === Start Frontend ===
echo Starting frontend...
start "Cycle-Frontend" /min cmd /k "cd /d %ROOT%\frontend & npx vite --port 5173"

echo.
echo ==========================================
echo   Backend : http://localhost:8000
echo   Game    : http://localhost:5173/play
echo ==========================================
echo.
echo Servers are starting in background windows.
echo Close the "Cycle-Backend" and "Cycle-Frontend"
echo windows to stop the servers.
echo.
pause
