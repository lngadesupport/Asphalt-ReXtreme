@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - DO EVERYTHING Campaign Edition

set "ROOT=%CD%"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"
set "FINALIZER=%ROOT%\FINALIZE-CAMPAIGN-EDITION.cmd"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] Execute este arquivo na raiz CAsphalt-ReXtreme-Baseline.
  echo Esperado:
  echo   %ROOT%\_PACKAGE_PHASE5\AMS.exe
  pause
  exit /b 10
)

where curl.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] curl.exe nao encontrado.
  pause
  exit /b 11
)

echo ============================================================
echo  ASPHALT REXTREME - RECONSTRUCAO COMPLETA AUTOMATICA
echo ============================================================
echo.
echo Baixando o finalizador estrito mais recente...
curl.exe -fL --retry 3 "%BASE%/FINALIZE-CAMPAIGN-EDITION.cmd" -o "%FINALIZER%"
if errorlevel 1 (
  echo [ERRO] Nao foi possivel baixar o finalizador.
  pause
  exit /b 20
)

echo.
echo Iniciando reconstrucao...
echo.
call "%FINALIZER%"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ============================================================
  echo  COMPLETE_REBUILD = TRUE
  echo ============================================================
  echo.
  echo A validacao estrita foi concluida sem bloqueios.
) else (
  echo ============================================================
  echo  RECONSTRUCAO PAROU EM UM BLOQUEIO REAL
  echo ============================================================
  echo.
  echo Codigo: %RC%
  echo Consulte:
  echo   _TRACE_MONTAR\CAMPAIGN-FINAL-STATUS.json
  echo   _CAMPAIGN_PRODUCTION_DATA
)
echo.
pause
exit /b %RC%
