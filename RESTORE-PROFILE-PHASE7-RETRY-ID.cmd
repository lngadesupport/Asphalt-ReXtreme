@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Restore Phase 7 Retry Identifier

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase7_retry_identify.ps1" ^
  -ProjectRoot "%CD%" ^
  -Restore

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
