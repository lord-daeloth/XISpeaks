@echo off
cd /d "%~dp0companion"
XISpeaks-Pocket-Companion.exe
if errorlevel 1 pause
