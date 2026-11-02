@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Run the repository setup.ps1 first to create the Python environment.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" maintainer\maintainer_ui.py
if errorlevel 1 pause
