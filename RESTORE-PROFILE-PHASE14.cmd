@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Restore Phase 14

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase14_no_connection_ui.ps1" ^
  -ProjectRoot "%CD%" ^
  -Restore

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
