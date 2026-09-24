@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Frontend Only Boot V1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_frontend_only_boot_v1.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Frontend-Only Boot v1 falhou com codigo %RC%.
pause
exit /b %RC%
