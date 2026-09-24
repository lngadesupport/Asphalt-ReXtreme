@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme 0.1.0-beta.1 - Repair
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\public_beta.ps1" -Action Repair
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Reparo concluido. O save local foi preservado/restaurado.
) else (
  echo Reparo falhou com codigo %RC%.
)
echo.
pause
exit /b %RC%
