@echo off
if exist "D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks\START-XISpeaks.cmd" (
  call "D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks\START-XISpeaks.cmd"
) else (
  call "%~dp0run.cmd" %*
)
