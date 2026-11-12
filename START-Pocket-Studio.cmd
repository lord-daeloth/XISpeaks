@echo off
if exist "%~dp0dist\XISpeaks-Pocket-Studio\XISpeaks-Pocket-Studio.exe" (
  start "" "%~dp0dist\XISpeaks-Pocket-Studio\XISpeaks-Pocket-Studio.exe"
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Pocket-Studio.ps1"
if errorlevel 1 pause
