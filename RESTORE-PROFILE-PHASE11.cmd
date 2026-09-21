@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Restore Phase 11

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase11_no_connection_errors.ps1" ^
  -ProjectRoot "%CD%" ^
  -Restore

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
