@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase72_gbbw_this_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 72 GBBW THIS-FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue explicitamente o this da GarageBottomBarWidget
echo pelos helpers chamados com mov ecx,obj / push obj,
echo procurando quem escreve ou passa endereco de +0x44.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/373e3682ee993dc7fca7a1c4ed5aea850605584b/tools/profile_phase72_gbbw_this_flow.py" -o "%MAP%"
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
echo PHASE 72 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE72_GBBW_THIS_FLOW\LATEST-PHASE72-GBBW-THIS-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE72_GBBW_THIS_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 72 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
