@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme Public Beta - Update
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\public_beta.ps1" -Action Update
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Atualizacao concluida.
) else (
  echo Atualizacao falhou com codigo %RC%.
)
echo.
pause
exit /b %RC%
