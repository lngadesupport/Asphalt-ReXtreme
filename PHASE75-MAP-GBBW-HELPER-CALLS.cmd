@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase75_gbbw_helper_calls.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 75 GBBW HELPER CALLS
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue a instancia real guardada em GS_Garage+0x35C
echo e lista os helpers chamados com GarageBottomBarWidget em ECX.
echo Cada helper e verificado especificamente para acesso a +0x44.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/881057f79fbfc029ed55e15fc18f1b6ac0c82a6a/tools/profile_phase75_gbbw_helper_calls.py" -o "%MAP%"
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
echo PHASE 75 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE75_GBBW_HELPER_CALLS\LATEST-PHASE75-GBBW-HELPER-CALLS.txt
echo   _PACKAGE_PHASE5\_PHASE75_GBBW_HELPER_CALLS\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 75 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
