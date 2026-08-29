$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compiler = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    throw 'The Windows .NET Framework C# compiler was not found.'
}

& $compiler /nologo /target:exe /optimize+ /win32icon:"$projectRoot\assets\app.ico" /out:"$projectRoot\Launch.exe" "$PSScriptRoot\Launcher.cs"
if ($LASTEXITCODE -ne 0) { throw 'Launch.exe compilation failed.' }
& $compiler /nologo /target:exe /optimize+ /win32icon:"$projectRoot\assets\stop.ico" /out:"$projectRoot\Stop.exe" "$PSScriptRoot\Stopper.cs"
if ($LASTEXITCODE -ne 0) { throw 'Stop.exe compilation failed.' }
Write-Host 'Launch.exe and Stop.exe rebuilt successfully.' -ForegroundColor Green
