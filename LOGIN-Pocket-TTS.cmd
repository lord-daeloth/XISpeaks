@echo off
setlocal
cd /d "%~dp0"
set "HF_HOME=%~dp0build\pocket-hf"
echo First accept access at https://huggingface.co/kyutai/pocket-tts
echo Then paste a Hugging Face READ token when prompted below.
echo Your token is stored locally. Do not paste it into chat.
"build\pocket-env\Scripts\hf.exe" auth login
if errorlevel 1 (
  pause
  exit /b 1
)
echo Login complete. You can close this window.
pause
