@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Frontend Only Garage V1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_frontend_only_garage_v1.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Frontend-Only Garage v1 falhou com codigo %RC%.
pause
exit /b %RC%
