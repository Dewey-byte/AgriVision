# Build the isolated environment used to fine-tune YOLO-NAS.
#
# YOLO-NAS training lives in Deci's super-gradients, which pins numpy<=1.23 and
# an older protobuf/onnx stack. Installing it into the main venv would break the
# Ultralytics detector the desktop app depends on, so it gets its own venv.
#
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File .\tools\setup_venv_nas.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot "venv-nas"
$python310 = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"

if (-not (Test-Path $python310)) {
    throw "Python 3.10 not found at $python310. super-gradients does not support Python 3.11+."
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating $venvPath ..." -ForegroundColor Cyan
    & $python310 -m venv $venvPath
}

$py = Join-Path $venvPath "Scripts\python.exe"

Write-Host "Upgrading installer tooling ..." -ForegroundColor Cyan
& $py -m pip install --upgrade "pip<24.1" "setuptools<70" wheel

# Match the main venv's CUDA build so both environments target the same GPU stack.
Write-Host "Installing torch 2.5.1+cu124 ..." -ForegroundColor Cyan
& $py -m pip install torch==2.5.1+cu124 torchvision==0.20.1+cu124 --index-url https://download.pytorch.org/whl/cu124

Write-Host "Installing super-gradients 3.7.1 ..." -ForegroundColor Cyan
& $py -m pip install super-gradients==3.7.1

Write-Host "`nVerifying ..." -ForegroundColor Cyan
& $py -c @"
import torch, super_gradients
print('torch', torch.__version__, 'cuda', torch.cuda.is_available())
print('super_gradients', super_gradients.__version__)
"@

# pretrained_weights='coco' still resolves against sghub.deci.ai, which stopped
# resolving after Deci was acquired. train_yolo_nas.py fetches the checkpoint
# from Deci's CDN into weights/ instead; warm that cache here.
Write-Host "`nFetching YOLO-NAS COCO weights ..." -ForegroundColor Cyan
& $py -c @"
import sys; sys.path.insert(0, r'$repoRoot')
from tools.train_yolo_nas import coco_checkpoint
print('ready:', coco_checkpoint('yolo_nas_s'))
"@

Write-Host "`nvenv-nas ready. Train with:" -ForegroundColor Green
Write-Host "  .\venv-nas\Scripts\python.exe tools\train_yolo_nas.py --epochs 100"
