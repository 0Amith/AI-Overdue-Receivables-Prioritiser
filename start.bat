@echo off
title ABC Traders Receivables Assistant
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py run.py
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    python run.py
    exit /b
)

echo Python 3 was not found on PATH.
echo Install Python from python.org, then run this file again.
pause
