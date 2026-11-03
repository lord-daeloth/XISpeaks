@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Piper.ps1" -Mode trainer
if errorlevel 1 pause
