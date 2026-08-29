$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& '.venv\Scripts\python.exe' -m uvicorn lead_engine.app:app --host 127.0.0.1 --port 8000
