@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Profile Phase 7 Callback Map

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase7_callback_map.ps1"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 7 callback map completed successfully.
) else (
  echo Phase 7 callback map failed with code %RC%.
)
echo.
pause
exit /b %RC%
