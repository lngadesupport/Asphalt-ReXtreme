@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Phase 4 Crash Probe

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\phase4_crash_probe.ps1" ^
  -GameRoot "%~dp0_RUNTIME_PHASE4"

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
