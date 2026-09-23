@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%CD%"
set "BACKUP=%ROOT%\_BACKUPS\R171\IGPLib_x86.dll"
set "TARGET=%ROOT%\_PACKAGE_PHASE5\IGPLib_x86.dll"
set "RUNTIME=%ROOT%\_PACKAGE_PHASE5\ReXtremeLocalRuntime.dll"

echo ============================================================
echo  Asphalt ReXtreme - REVERT R17.1
echo ============================================================
echo.

if not exist "%BACKUP%" (
  echo [ERRO] Backup R17.1 nao encontrado:
  echo   %BACKUP%
  echo.
  pause
  exit /b 1
)

copy /y "%BACKUP%" "%TARGET%" >nul
if errorlevel 1 (
  echo [ERRO] Falha ao restaurar IGPLib.
  pause
  exit /b 1
)

if exist "%RUNTIME%" del /q "%RUNTIME%" >nul 2>&1

echo R17.1 revertida. Bootstrap anterior restaurado.
echo.
pause
exit /b 0
