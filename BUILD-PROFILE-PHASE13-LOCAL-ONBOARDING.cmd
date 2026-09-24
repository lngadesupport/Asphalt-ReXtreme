@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 13 Local Onboarding

echo ============================================================
echo  Asphalt ReXtreme - PHASE 13 LOCAL ONBOARDING
echo  Repairs age/gender handler without enabling global network
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase13_local_onboarding.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 13 applied successfully.
  echo Launch: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 13 failed with code %RC%.
)
echo.
pause
exit /b %RC%
