param([switch]$InstallPlaywrightBrowser)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11+ is required.'
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js 18+ is required.'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -m venv .venv
}
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
npm install
& '.venv\Scripts\python.exe' -m lead_engine.cli init
& '.venv\Scripts\python.exe' -m lead_engine.cli import

if ($InstallPlaywrightBrowser) {
    & '.venv\Scripts\python.exe' -m playwright install chromium
}

Write-Host 'Setup complete. Outreach is still dry-run locked.' -ForegroundColor Green
