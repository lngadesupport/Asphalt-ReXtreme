@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Profile Only Test
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_profile_only.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Profile-only test falhou com codigo %RC%.
pause
exit /b %RC%
