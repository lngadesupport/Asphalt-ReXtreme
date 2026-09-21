@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 12 Local Offline

echo ============================================================
echo  Asphalt ReXtreme - PHASE 12 LOCAL OFFLINE
echo  No remote connectivity + no known network-error UI
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase12_local_offline.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 12 applied successfully.
  echo Launch: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 12 failed with code %RC%.
)
echo.
pause
exit /b %RC%
