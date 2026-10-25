param([string]$AddonRoot = 'D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $AddonRoot -PathType Container)) { throw "Addon root not found: $AddonRoot" }
$destination = Join-Path $AddonRoot 'XISpeaks'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'addon\XISpeaks\XISpeaks.lua') -Destination $destination
Write-Host "Installed to $destination. Load with /addon load XISpeaks"
