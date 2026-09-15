@echo off
cd /d "%~dp0"
title AgriVision
py -3.10 main.py
if errorlevel 1 (
    echo.
    echo AgriVision failed to start. Install Python 3.10 and run:
    echo   py -3.10 -m pip install -r requirements.txt
    pause
)
