@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Run the repository setup.ps1 first.
    pause
    exit /b 1
)
if not exist "build\voice-studio-deps\inno_kokoro\enroll.py" (
    echo Run voice_studio\SETUP-Voice-Studio.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" voice_studio\studio.py
if errorlevel 1 pause
