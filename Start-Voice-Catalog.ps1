$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$installed='D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks\companion'
if (Test-Path -LiteralPath (Join-Path $installed 'XISpeaks-Catalog.exe')) {
    Start-Process -FilePath (Join-Path $installed 'XISpeaks-Catalog.exe') -WorkingDirectory $installed -WindowStyle Hidden
    exit
}
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') 'voice_editor/app.py'
exit $LASTEXITCODE
