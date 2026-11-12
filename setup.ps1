param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $candidate) { $Python = $candidate }
    else { $Python = 'python' }
}
& $Python -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32, "Use 64-bit Python 3.12"'
if ($LASTEXITCODE) { throw 'A compatible Python is required. Pass -Python with its full path.' }
& $Python -m venv .venv
if ($LASTEXITCODE) { throw 'Virtual environment creation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
& (Join-Path $PSScriptRoot 'setup-rubberband.ps1')
Write-Host 'Dependencies ready. Copy models and pocket_voices from the beta release into the project root, then run run.cmd.'
