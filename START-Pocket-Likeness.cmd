@echo off
setlocal
cd /d "%~dp0"
"build\pocket-env\Scripts\python.exe" experiments\pocket_tts\likeness.py
if errorlevel 1 (
  pause
  exit /b 1
)
start "" "experiments\pocket_tts\output\likeness\index.html"
