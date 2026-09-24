@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme Public Beta - Startup Bisect
echo ============================================================
echo  ASPHALT REXTREME - STARTUP BISECT
echo ============================================================
echo.
echo Este teste abre variantes temporarias do runtime por ate 12 segundos.
echo Ele para no primeiro estagio que reproduzir o crash.
echo O AMS/IGPLib atuais e o save Campaign sao restaurados no final.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\beta_startup_bisect.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Bisect terminou com codigo %RC%.
pause
exit /b %RC%
