@echo off
setlocal
cd /d "%~dp0"
"companion\XISpeaks-Companion.exe" %*
if errorlevel 1 pause
