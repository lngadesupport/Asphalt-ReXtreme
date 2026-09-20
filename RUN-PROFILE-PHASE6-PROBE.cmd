@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Profile Phase 6 Probe

echo ============================================================
echo  Asphalt ReXtreme - PROFILE PHASE 6 PROBE
echo  Static local-profile map + package local storage inventory
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase6_probe.ps1"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Profile Phase 6 probe completed successfully.
) else (
  echo Profile Phase 6 probe failed with code %RC%.
)
echo.
pause
exit /b %RC%
