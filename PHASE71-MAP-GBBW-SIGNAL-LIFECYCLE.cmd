@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase71_gbbw_signal_lifecycle.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 71 GBBW SIGNAL LIFECYCLE
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela rastreia +0x44 somente dentro dos metodos reais
echo da GarageBottomBarWidget, incluindo LEA/passagem por helper.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f47af23b2f7a65000fa9060deb66132a71c2954b/tools/profile_phase71_gbbw_signal_lifecycle.py" -o "%MAP%"
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
echo PHASE 71 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE71_GBBW_SIGNAL_LIFECYCLE\LATEST-PHASE71-GBBW-SIGNAL-LIFECYCLE.txt
echo   _PACKAGE_PHASE5\_PHASE71_GBBW_SIGNAL_LIFECYCLE\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 71 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
