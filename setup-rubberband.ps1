$ErrorActionPreference = 'Stop'
$toolsDir = Join-Path $PSScriptRoot 'tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$archive = Join-Path $toolsDir 'rubberband-4.0.0.zip'
Invoke-WebRequest -Uri 'https://breakfastquay.com/files/releases/rubberband-4.0.0-gpl-executable-windows.zip' -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne 'F2D47FC64DBB42F6CC62EDF7933AC4FA89D8F0EF8B9CF97B6AFC263A7FE05644') {
    throw 'Rubber Band archive checksum mismatch; not extracting.'
}
Expand-Archive -LiteralPath $archive -DestinationPath $toolsDir -Force
Write-Host 'Rubber Band R3 installed (including its DLL and license).'
