@echo off
cd /d "%~dp0companion"
XISpeaks-Companion.exe
if errorlevel 1 pause
