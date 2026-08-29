# Local Lead Scout - Windows launch helper.
# Launch.bat is the canonical entry point because it starts both the persistent
# Python lead engine and the existing Node dashboard, with optional gosom Docker.
$projectRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $projectRoot 'Launch.bat'

if (-not (Test-Path -LiteralPath $launcher)) {
    Write-Error "Launch.bat was not found at $launcher"
    exit 1
}

& $launcher
exit $LASTEXITCODE
