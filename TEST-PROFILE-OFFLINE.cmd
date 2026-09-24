@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Profile + Offline UI Test
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_profile_offline.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Profile/offline test falhou com codigo %RC%.
pause
exit /b %RC%
