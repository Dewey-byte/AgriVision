# Start Label Studio + AgriVision YOLO ML backend (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Error "Run from AgriVision repo with venv installed."
}

. .\venv\Scripts\Activate.ps1

$env:LABEL_STUDIO_URL = "http://localhost:8080"
$env:AGRIVISION_LS_MIN_CONF = "0.35"

Write-Host "Starting YOLO ML backend on http://localhost:9090 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root'; . .\venv\Scripts\Activate.ps1; `$env:LABEL_STUDIO_URL='http://localhost:8080'; python tools/label_studio/ml_server.py"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting Label Studio on http://localhost:8080 ..."
Write-Host ""
Write-Host "After creating a project:"
Write-Host "  1. Settings -> Labeling Interface -> paste tools/label_studio/label_config.xml"
Write-Host "  2. Settings -> Model -> Backend URL http://localhost:9090 -> Validate and Save"
Write-Host "  3. Import images from datasets/inbox (Upload Files, not JSON storage)"
Write-Host ""

label-studio start --port 8080 --no-browser
