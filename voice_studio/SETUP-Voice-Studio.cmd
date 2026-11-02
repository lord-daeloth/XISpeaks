@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Run the repository setup.ps1 first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --target build\voice-studio-deps --upgrade --no-deps inno-kokoro==0.2.0 praat-parselmouth==0.4.7
if errorlevel 1 (
    pause
    exit /b 1
)
echo Voice Studio is ready. Run START-Voice-Studio.cmd.
pause
