param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $candidate) { $Python = $candidate }
    else { $Python = 'python' }
}
& $Python -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,13) and sys.maxsize > 2**32, "Use 64-bit Python 3.10-3.12"'
if ($LASTEXITCODE) { throw 'A compatible Python is required. Pass -Python with its full path.' }
& $Python -m venv .venv
if ($LASTEXITCODE) { throw 'Virtual environment creation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
& (Join-Path $PSScriptRoot 'setup-rubberband.ps1')
& '.\.venv\Scripts\python.exe' companion/voice_install.py
if ($LASTEXITCODE) { throw 'Voice installation failed. Re-run setup to resume.' }
Write-Host 'Setup complete. Run run.cmd.'
