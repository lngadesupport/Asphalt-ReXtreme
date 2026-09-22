@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase74_gs_garage_gbbw_storage.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 74 GS_GARAGE -> GBBW STORAGE
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue:
echo   GS_Garage::+0xDC 0x00ABE7E0
echo   -> factory 0x00A6C7F0
echo   -> GarageBottomBarWidget 0x0096EB10
echo e identifica onde a instancia/shared_ptr e armazenada
echo e reutilizada por outros metodos da GS_Garage.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/532d682d737a12defd21519f139d7a3aa5195e4a/tools/profile_phase74_gs_garage_gbbw_storage.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 74 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE74_GS_GARAGE_GBBW_STORAGE\LATEST-PHASE74-GS-GARAGE-GBBW-STORAGE.txt
echo   _PACKAGE_PHASE5\_PHASE74_GS_GARAGE_GBBW_STORAGE\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 74 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
