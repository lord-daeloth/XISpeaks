$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$assetsRoot=(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pocket-development.json') -Raw | ConvertFrom-Json).assets_root
$catalog='D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaksPocket\companion\pocket_voices\catalog.json'
if (!(Test-Path -LiteralPath $catalog)) {$catalog=Join-Path $PSScriptRoot 'pocket_voices/catalog.json'}
& (Join-Path $assetsRoot 'build/pocket-env/Scripts/python.exe') 'voice_editor/app.py' --catalog $catalog
exit $LASTEXITCODE
