$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$config=Join-Path $PSScriptRoot 'pocket-development.json'
$assetsRoot=if(Test-Path -LiteralPath $config){(Get-Content -LiteralPath $config -Raw | ConvertFrom-Json).assets_root}else{$PSScriptRoot}
& (Join-Path $assetsRoot 'build/pocket-env/Scripts/python.exe') 'pocket_studio/app.py'
exit $LASTEXITCODE
