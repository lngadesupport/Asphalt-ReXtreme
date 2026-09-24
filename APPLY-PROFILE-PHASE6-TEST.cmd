@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Apply Profile Phase 6 Test

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase6_test.ps1"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 6 test applied successfully.
  echo Now run: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 6 test failed with code %RC%.
)
echo.
pause
exit /b %RC%
