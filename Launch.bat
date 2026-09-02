@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Local Business Lead Scout - Launcher
color 0B

echo ======================================================================
echo           LOCAL BUSINESS LEAD GENERATOR - LAUNCHER
echo ======================================================================
echo.

echo [1/5] Checking Node.js and Python...
where node >nul 2>&1 || goto NODE_MISSING
where py >nul 2>&1 || goto PYTHON_MISSING
echo  [OK] Node.js and Python launchers are available.
goto RUNTIME_READY

:NODE_MISSING
color 0C
echo  [ERROR] Node.js 18 or newer is required.
pause
exit /b 1

:PYTHON_MISSING
color 0C
echo  [ERROR] Python 3.11 or newer is required.
pause
exit /b 1

:RUNTIME_READY
echo.
echo [2/5] Preparing the Python lead engine...
if not exist ".venv\Scripts\python.exe" (
    echo  [INFO] Creating isolated Python environment...
    py -m venv .venv || goto PYTHON_SETUP_FAILED
)
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,bs4,dns,httpx,cryptography,argon2" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo  [INFO] Installing pinned Python dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto PYTHON_SETUP_FAILED
)
echo  [OK] Python lead engine is ready.
goto PYTHON_READY

:PYTHON_SETUP_FAILED
color 0E
echo  [WARNING] Python lead-engine setup failed. The dashboard can still run,
echo            but persistence, enrichment, and campaign workflows will be offline.

:PYTHON_READY
echo.
echo [3/5] Checking optional gosom Docker scraper...
set "DOCKER_CLI="
where docker >nul 2>&1
if !ERRORLEVEL! EQU 0 set "DOCKER_CLI=docker"
if not defined DOCKER_CLI if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "DOCKER_CLI=%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"
if not defined DOCKER_CLI if exist "%LOCALAPPDATA%\Docker\resources\bin\docker.exe" set "DOCKER_CLI=%LOCALAPPDATA%\Docker\resources\bin\docker.exe"

if not defined DOCKER_CLI (
    echo  [WARNING] Docker is not installed. Continuing with Apify fallback.
) else (
    call :ENSURE_DOCKER
)

echo.
echo [4/5] Starting Python lead engine and Node dashboard...
if exist ".venv\Scripts\python.exe" (
    start /b "LeadEngine" ".venv\Scripts\python.exe" -m uvicorn lead_engine.app:app --host 127.0.0.1 --port 8000 > "%TEMP%\lead_engine.log" 2>&1
    start /b "OutreachWorker" ".venv\Scripts\python.exe" -m lead_engine.worker > "%TEMP%\outreach_worker.log" 2>&1
)
start /b "LeadDashboard" node server.js > "%TEMP%\leadgen_server.log" 2>&1

echo.
echo [5/5] Waiting for the dashboard...
set /a attempts=0
:POLL_LOOP
timeout /t 2 /nobreak >nul
set /a attempts+=1
powershell -NoProfile -Command "try { $r=Invoke-WebRequest 'http://127.0.0.1:3000/api/status' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0} }; exit 1" >nul 2>&1
if !ERRORLEVEL! EQU 0 goto SERVER_READY
if !attempts! GEQ 20 goto SERVER_TIMEOUT
echo  ... waiting ^(attempt !attempts!/20^)...
goto POLL_LOOP

:SERVER_READY
color 0A
echo  [OK] Dashboard is ready at http://127.0.0.1:3000
echo  [INFO] Opening the dashboard in your default browser...
start "" "http://127.0.0.1:3000"
goto SHOW_LOGS

:SERVER_TIMEOUT
color 0E
echo  [WARNING] Dashboard did not become ready within 40 seconds.
echo  Review %TEMP%\leadgen_server.log and %TEMP%\lead_engine.log.

:SHOW_LOGS
echo.
echo ======================================================================
echo  Services are running. Use Stop.bat or Stop.exe for a clean shutdown.
echo  Sending runs only through the background worker after validation.
echo ======================================================================
echo.
powershell -NoProfile -Command "Get-Content @('%TEMP%\leadgen_server.log','%TEMP%\lead_engine.log','%TEMP%\outreach_worker.log') -Tail 25 -Wait"
exit /b 0

:ENSURE_DOCKER
"%DOCKER_CLI%" info >nul 2>&1
if !ERRORLEVEL! EQU 0 goto START_GOSOM

echo  [INFO] Docker is installed but its engine is offline. Starting Docker Desktop...
set "DOCKER_DESKTOP="
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not defined DOCKER_DESKTOP if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" set "DOCKER_DESKTOP=%LOCALAPPDATA%\Docker\Docker Desktop.exe"

if not defined DOCKER_DESKTOP (
    echo  [WARNING] Docker Desktop could not be located. Continuing with Apify fallback.
    exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:DOCKER_DESKTOP -WindowStyle Hidden" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo  [WARNING] Docker Desktop could not be started. Continuing with Apify fallback.
    exit /b 0
)

set /a docker_attempts=0
:DOCKER_WAIT_LOOP
timeout /t 2 /nobreak >nul
set /a docker_attempts+=1
"%DOCKER_CLI%" info >nul 2>&1
if !ERRORLEVEL! EQU 0 goto START_GOSOM
if !docker_attempts! GEQ 45 (
    echo  [WARNING] Docker did not become ready within 90 seconds. Continuing with Apify fallback.
    exit /b 0
)
echo  ... waiting for Docker Desktop ^(attempt !docker_attempts!/45^) ...
goto DOCKER_WAIT_LOOP

:START_GOSOM
echo  [INFO] Docker engine is ready. Starting the gosom discovery service...
"%DOCKER_CLI%" compose up -d
if !ERRORLEVEL! EQU 0 (
    echo  [OK] gosom Docker service started.
) else (
    echo  [WARNING] gosom could not be started. Continuing with Apify fallback.
)
exit /b 0
