@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_shortcut.ps1"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)
echo.
pause
