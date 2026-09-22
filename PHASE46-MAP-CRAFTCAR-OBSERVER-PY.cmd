@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase46_craftcar_observer_map.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 46 PYTHON OBSERVER MAP
echo ============================================================
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/4421ba8794fd405074134058d785c8aa5dd95abb/tools/profile_phase46_craftcar_observer_map.py" -o "%SCRIPT%"
if errorlevel 1 goto :fail

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%SCRIPT%" --project-root "%ROOT%"
  goto :after
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado no PATH.
  goto :fail
)

python "%SCRIPT%" --project-root "%ROOT%"

:after
if errorlevel 1 goto :fail

echo.
echo PHASE 46 PYTHON OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE46_BUILD_OBSERVER_MAP\LATEST-PHASE46-BUILD-OBSERVER-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 46 Python falhou.
echo Nenhum patch foi aplicado e o save nao foi resetado.
pause
exit /b 1
