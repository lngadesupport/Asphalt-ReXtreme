@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme 0.1.0-beta.1 - Install
echo ============================================================
echo  ASPHALT REXTREME - PUBLIC BETA 0.1.0-beta.1
echo ============================================================
echo.
echo Este instalador nao usa Git e nao exige Python instalado.
echo Ele precisa de uma copia compativel do Asphalt Xtreme 1.7.3.8 x86.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\public_beta.ps1" -Action Install -SourceDir "%~1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Instalacao do beta concluida.
  echo Use PLAY-BETA.cmd para jogar.
) else (
  echo Instalacao falhou com codigo %RC%.
)
echo.
pause
exit /b %RC%
