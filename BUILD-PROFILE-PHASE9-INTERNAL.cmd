@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 9 Internal Campaign Profile

echo ============================================================
echo  Asphalt ReXtreme - PHASE 9 INTERNAL CAMPAIGN PROFILE
echo  Native default profile + remote sync bypass
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase9_internal.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 9 applied successfully.
  echo Launch the game using _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 9 failed with code %RC%.
)
echo.
pause
exit /b %RC%
