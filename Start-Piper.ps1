param([ValidateSet('trainer','companion','setup','catalog')][string]$Mode='trainer')
$ErrorActionPreference='Stop'
$assetsRoot=$PSScriptRoot
$localConfig=Join-Path $PSScriptRoot 'piper-development.json'
if(Test-Path -LiteralPath $localConfig){$assetsRoot=(Get-Content -LiteralPath $localConfig -Raw | ConvertFrom-Json).assets_root}
$pythonPath=Join-Path $assetsRoot 'build/piper-train-env/Scripts/python.exe'
if(!(Test-Path -LiteralPath $pythonPath) -and $Mode -ne 'trainer'){$pythonPath=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'}
if(!(Test-Path -LiteralPath $pythonPath)){throw 'Piper training environment is missing. See PIPER-EXPERIMENT.md.'}
Set-Location -LiteralPath $PSScriptRoot
switch($Mode){
 'trainer' {& $pythonPath 'piper_trainer/app.py'}
 'companion' {& $pythonPath 'companion/piper_service.py'}
 'catalog' {& $pythonPath 'voice_editor/app.py'}
 'setup' {& $pythonPath 'piper_trainer/setup_voices.py'}
}
exit $LASTEXITCODE
