@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Local Business Lead Scout - Shut Down
color 0E

echo ======================================================================
echo           LOCAL BUSINESS LEAD GENERATOR - SHUTDOWN
echo ======================================================================
echo.

echo [1/3] Stopping application-owned processes...
call :STOP_PID_FILE "data\node.pid" "Node dashboard" "node"
call :STOP_PID_FILE "data\lead_engine.pid" "Python lead engine" "python"
call :STOP_PID_FILE "data\outreach_worker.pid" "Outreach worker" "python"

echo.
echo [2/3] Stopping gosom Docker service when available...
where docker >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    docker compose down
) else (
    echo  [INFO] Docker is not installed; nothing to stop.
)

echo.
echo [3/3] Shutdown complete.
color 0A
echo  [OK] Only PIDs recorded by this application were targeted.
pause
exit /b 0

:STOP_PID_FILE
set "PID_FILE=%~1"
set "SERVICE_NAME=%~2"
set "EXPECTED_PROCESS=%~3"
if not exist "%PID_FILE%" (
    echo  [INFO] %SERVICE_NAME% PID file not found.
    exit /b 0
)
set /p TARGET_PID=<"%PID_FILE%"
echo !TARGET_PID!| findstr /r "^[0-9][0-9]*$" >nul
if !ERRORLEVEL! NEQ 0 (
    echo  [WARNING] Invalid PID file for %SERVICE_NAME%; no process was stopped.
    exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-Process -Id !TARGET_PID! -ErrorAction SilentlyContinue; if ($null -eq $p) { exit 2 }; if ($p.ProcessName -ine '%EXPECTED_PROCESS%') { exit 3 }; Stop-Process -Id $p.Id -ErrorAction Stop" >nul 2>&1
if !ERRORLEVEL! EQU 3 (
    echo  [WARNING] PID !TARGET_PID! is not %EXPECTED_PROCESS%.exe; no process was stopped.
    exit /b 0
)
if !ERRORLEVEL! EQU 2 (
    echo  [INFO] %SERVICE_NAME% was not running.
    del /q "%PID_FILE%" >nul 2>&1
    exit /b 0
)
if !ERRORLEVEL! EQU 0 (
    echo  [OK] %SERVICE_NAME% stopped ^(PID !TARGET_PID!^).
) else (
    echo  [WARNING] %SERVICE_NAME% could not be stopped.
    exit /b 0
)
del /q "%PID_FILE%" >nul 2>&1
exit /b 0
