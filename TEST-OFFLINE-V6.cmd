@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme - Offline Lobby V6 Test
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test_offline_lobby_v6.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Offline Lobby v6 test falhou com codigo %RC%.
pause
exit /b %RC%
