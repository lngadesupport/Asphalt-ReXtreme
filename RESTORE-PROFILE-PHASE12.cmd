@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Restore Phase 12

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase12_local_offline.ps1" ^
  -ProjectRoot "%CD%" ^
  -Restore

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
