# Train and score every architecture benchmark contender, in sequence.
#
# The contenders share a 6 GB GPU, so runs are strictly serial. Each stage is
# skipped when its output already exists, which makes the script safe to re-run
# after an interruption.
#
# Usage (from the repository root, with the desktop app closed):
#   powershell -ExecutionPolicy Bypass -File .\tools\run_benchmark_suite.ps1
#
# Options:
#   -WaitForPid <id>   Block until that process exits before starting (lets you
#                      queue this behind a training run that is already going)
#   -SkipYolov8        Reuse an existing bench_yolov8n run

param(
    [int]$WaitForPid = 0,
    [int]$Epochs = 100,
    [switch]$SkipYolov8
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$runsDir = Join-Path $repoRoot "runs\detect"

function Write-Stage($message) {
    Write-Host "`n=== $message ===" -ForegroundColor Cyan
}

if ($WaitForPid -gt 0) {
    Write-Stage "Waiting for PID $WaitForPid to finish"
    while (Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 30 }
    Write-Host "PID $WaitForPid has exited."
    Start-Sleep -Seconds 10
}

# Ultralytics resolves a relative --project against its global runs_dir
# setting, which on this machine still pointed at an older checkout. Any
# bench_* run that landed outside the repo gets pulled back in, so the
# results.csv paths in models.json stay valid.
Write-Stage "Collecting stray Ultralytics runs"
$settingsRunsDir = (& py -3.10 -c "from ultralytics.utils import SETTINGS; print(SETTINGS.get('runs_dir'))").Trim()
$searchRoots = @(
    $settingsRunsDir,
    (Join-Path $env:USERPROFILE "Documents\GitHub\AgriVision\runs")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

New-Item -ItemType Directory -Force -Path $runsDir | Out-Null
foreach ($root in $searchRoots) {
    Get-ChildItem $root -Directory -Recurse -Filter "bench_*" -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not (Test-Path (Join-Path $_.FullName "results.csv"))) { return }
        $target = Join-Path $runsDir $_.Name
        if ($_.FullName -ieq $target) { return }
        if (Test-Path $target) {
            Write-Host "  $($_.Name) already in repo, leaving alone"
            return
        }
        Write-Host "  copying $($_.FullName) -> $target"
        Copy-Item $_.FullName $target -Recurse
    }
}

if (-not $SkipYolov8) {
    $target = Join-Path $runsDir "bench_yolov8n\weights\best.pt"
    if (Test-Path $target) {
        Write-Stage "YOLOv8n already trained, skipping"
    } else {
        Write-Stage "Training YOLOv8n ($Epochs epochs)"
        & py -3.10 train.py --model yolov8n.pt --name bench_yolov8n --epochs $Epochs --batch 16 --no-deploy
        if ($LASTEXITCODE -ne 0) { throw "YOLOv8n training failed" }
    }
}

Write-Stage "Scoring all contenders on the held-out test split"
& py -3.10 tools\benchmark_models.py

Write-Stage "Done"
Write-Host "Open the dashboard's Model Comparison page to see the leaderboard."
