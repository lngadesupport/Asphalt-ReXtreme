@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 11 No Connection Errors

echo ============================================================
echo  Asphalt ReXtreme - PHASE 11 NO CONNECTION ERRORS
echo  Removes all known NO_INTERNET popup paths
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase11_no_connection_errors.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 11 applied successfully.
  echo Launch: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 11 failed with code %RC%.
)
echo.
pause
exit /b %RC%
