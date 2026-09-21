@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Remove Runtime Logger

set "GAME=%CD%\_PACKAGE_PHASE5"
set "LIVE=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "BACKUP=%GAME%\RUN-PACKAGE-PHASE5-ORIGINAL.cmd"

if not exist "%BACKUP%" (
  echo [ERRO] Backup original nao encontrado:
  echo   %BACKUP%
  pause
  exit /b 10
)

copy /y "%BACKUP%" "%LIVE%" >nul
if errorlevel 1 (
  echo [ERRO] Nao foi possivel restaurar o launcher.
  pause
  exit /b 11
)

echo Runtime logger removido do launcher.
echo Os logs existentes foram preservados em _RUNTIME_LOGS.
pause
exit /b 0
