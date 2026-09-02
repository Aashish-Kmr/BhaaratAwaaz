<#
.SYNOPSIS
    Start BAIF Bhasha. Run setup.ps1 once first.

.DESCRIPTION
    Starts the single-process app: FastAPI serves both the API (/api/*) and the
    prebuilt UI (/) on http://127.0.0.1:8000, and opens a browser.

    There is no second terminal and no Node.js here. The React UI was built to
    static files on the packaging machine, so `npm install` / `npm run dev` from
    the README's development flow are not part of this bundle.

.PARAMETER Port
    Override the port (default 8000). Useful if something else already has it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File run.ps1
    powershell -ExecutionPolicy Bypass -File run.ps1 -Port 8080
#>

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$AppHost = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'

$Root       = $PSScriptRoot
$BackendDir = Join-Path $Root 'app\backend'
$VenvDir    = Join-Path $BackendDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$BinDir     = Join-Path $Root 'bin'

if (-not (Test-Path $VenvPython)) {
    throw "No virtual environment at $VenvDir. Run setup.ps1 first:`n  powershell -ExecutionPolicy Bypass -File setup.ps1"
}

# The video pipeline shells out to a bare "ffmpeg" (vendor/video_baif/services/
# extractor.py, media.py, renderer.py). setup.ps1 copies it into .venv\Scripts,
# but prepend bin\ too so this works even if that copy was skipped.
$env:Path = "$BinDir;$env:Path"

$env:BAIF_HOST = $AppHost
$env:BAIF_PORT = "$Port"

Write-Host "Starting BAIF Bhasha on http://${AppHost}:${Port}" -ForegroundColor Green
Write-Host 'First start is slow: the translation and ASR models load on demand, from disk.' -ForegroundColor DarkGray
Write-Host 'Ctrl+C to stop.' -ForegroundColor DarkGray
Write-Host ''

Push-Location $BackendDir
try {
    # run.py, not `uvicorn --reload`: the job queue is in-memory, and a reload
    # triggered by transformers writing into data\hf_cache would wipe every
    # in-flight job. run.py does not use --reload at all.
    & $VenvPython run.py
} finally {
    Pop-Location
}
