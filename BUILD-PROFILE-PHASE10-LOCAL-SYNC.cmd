@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 10 Global Local Sync

echo ============================================================
echo  Asphalt ReXtreme - PHASE 10 GLOBAL LOCAL SYNC
echo  Neutralizes all known online-profile loading sites
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase10_local_sync.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 10 applied successfully.
  echo Launch: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 10 failed with code %RC%.
)
echo.
pause
exit /b %RC%
