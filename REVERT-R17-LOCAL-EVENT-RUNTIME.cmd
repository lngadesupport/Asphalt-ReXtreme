@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - Revert R17

set "ROOT=%CD%"
set "BACKUP=%ROOT%\_BACKUPS\R17\IGPLib_x86.dll"
set "TARGET=%ROOT%\_PACKAGE_PHASE5\IGPLib_x86.dll"

echo ============================================================
echo  Asphalt ReXtreme - REVERT R17
echo ============================================================
echo.

if not exist "%BACKUP%" (
  echo [ERRO] Backup R17 nao encontrado:
  echo   %BACKUP%
  echo.
  pause
  exit /b 1
)

if not exist "%ROOT%\_PACKAGE_PHASE5\" (
  echo [ERRO] Pasta _PACKAGE_PHASE5 nao encontrada.
  echo.
  pause
  exit /b 1
)

copy /y "%BACKUP%" "%TARGET%" >nul
if errorlevel 1 (
  echo [ERRO] Nao foi possivel restaurar o DLL.
  echo.
  pause
  exit /b 1
)

fc /b "%BACKUP%" "%TARGET%" >nul
if errorlevel 1 (
  echo [ERRO] Restauracao feita, mas a verificacao falhou.
  echo.
  pause
  exit /b 1
)

echo R17 revertida com sucesso.
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
pause
exit /b 0
