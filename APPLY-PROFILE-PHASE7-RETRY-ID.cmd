@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 7 Retry Identifier

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase7_retry_identify.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Test patch applied.
  echo Launch _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd and click TENTAR NOVAMENTE once.
) else (
  echo Retry identifier failed with code %RC%.
)
echo.
pause
exit /b %RC%
