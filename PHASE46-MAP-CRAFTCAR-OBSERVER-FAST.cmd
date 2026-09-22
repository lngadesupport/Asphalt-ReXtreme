@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase46_craftcar_observer_map_fast.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 46 FAST OBSERVER MAP
echo ============================================================
echo.
echo Nao requer Python.
echo Usa C# compilado em memoria via PowerShell.
echo Nao aplica patch e nao altera save/LocalState.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/cfc53892495da9895cd88d2efa934474658458d3/tools/profile_phase46_craftcar_observer_map_fast.ps1" -o "%SCRIPT%"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 46 FAST OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE46_BUILD_OBSERVER_MAP\LATEST-PHASE46-BUILD-OBSERVER-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 46 Fast falhou.
echo Nenhum patch foi aplicado e o save nao foi resetado.
pause
exit /b 1
