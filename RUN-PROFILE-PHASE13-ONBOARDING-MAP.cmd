@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 13 Onboarding Map

echo ============================================================
echo  Asphalt ReXtreme - PHASE 13 ONBOARDING MAP
echo  Read-only mapper for age/gender/consent/profile state
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase13_onboarding_map.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 13 onboarding map complete.
  echo Output: _PACKAGE_PHASE5\PROFILE-PHASE13-ONBOARDING-MAP.zip
) else (
  echo Phase 13 mapper failed with code %RC%.
)
echo.
pause
exit /b %RC%
