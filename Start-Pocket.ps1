param()
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$assetsRoot=$PSScriptRoot
$localConfig=Join-Path $PSScriptRoot 'pocket-development.json'
if(Test-Path -LiteralPath $localConfig){$assetsRoot=(Get-Content -LiteralPath $localConfig -Raw | ConvertFrom-Json).assets_root}
$pythonPath=Join-Path $assetsRoot 'build/pocket-env/Scripts/python.exe'
if(!(Test-Path -LiteralPath $pythonPath)){throw 'Pocket environment missing. See POCKET-EXPERIMENT.md.'}
& $pythonPath 'companion/pocket_service.py'
exit $LASTEXITCODE
