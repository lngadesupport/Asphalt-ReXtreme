@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Campaign Edition

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase8_runtime.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo Campaign runtime exited with code %RC%.
  pause
)
exit /b %RC%
