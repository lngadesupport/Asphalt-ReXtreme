@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 13 Age Handler Focus

echo ============================================================
echo  Asphalt ReXtreme - PHASE 13 AGE/GENDER HANDLER FOCUS
echo  Read-only trace of the ACEITAR path
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase13_age_handler_map.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Output:
  echo   _PACKAGE_PHASE5\PROFILE-PHASE13-AGE-HANDLER-FOCUS.zip
) else (
  echo [ERRO] Focus trace failed with code %RC%.
)
echo.
pause
exit /b %RC%
