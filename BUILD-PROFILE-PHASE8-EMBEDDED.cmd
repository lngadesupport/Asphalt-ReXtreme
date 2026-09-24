@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 8 Embedded Profile

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase8_embed.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 8 embedded profile completed successfully.
  echo Use RUN-CAMPAIGN-PHASE8.cmd from now on.
) else (
  echo Phase 8 build failed with code %RC%.
)
echo.
pause
exit /b %RC%
