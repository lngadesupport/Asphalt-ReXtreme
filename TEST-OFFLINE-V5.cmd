@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Offline Surface V5 Test
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_offline_surface_v5.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Offline Surface v5 test falhou com codigo %RC%.
pause
exit /b %RC%
