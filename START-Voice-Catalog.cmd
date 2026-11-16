@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Voice-Catalog.ps1"
if errorlevel 1 pause
