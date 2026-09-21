@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 29 Connectivity Methods

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase29_connectivity_methods.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 29 CONNECTIVITY METHODS
echo ============================================================
echo.
echo Mapeia somente os metodos reais de AVAsphaltConnectivityTracker,
echo seus callers, chamadas WinRT/IsOnline e offsets internos do objeto.
echo Usa Python para ser muito mais rapido que os mappers PowerShell.
echo Nao abre o jogo e nao altera save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/693bde50158affeb8d9a3c6757ec80f51eb2f8fc/tools/profile_phase29_connectivity_methods.py" ^
  -o "%SCRIPT%"
if errorlevel 1 goto :fail

echo [2/2] Validando e executando...
python "%SCRIPT%" "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 29 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE29_CONNECTIVITY_METHODS\LATEST-PHASE29-CONNECTIVITY-METHODS.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 29 falhou.
echo O save nao foi resetado.
pause
exit /b 1
