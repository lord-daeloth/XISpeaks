@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run powershell -ExecutionPolicy Bypass -File setup.ps1 first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" companion\piper_service.py %*
if errorlevel 1 pause
