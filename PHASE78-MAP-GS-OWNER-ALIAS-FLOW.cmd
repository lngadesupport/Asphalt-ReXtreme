@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase78_gs_owner_alias_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 78 GS OWNER ALIAS FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela parte somente das leituras confirmadas de GS_Garage+0x35C
echo e segue aliases/LEA/helpers da GarageBottomBarWidget,
echo procurando acessos efetivos aos campos de callback,
echo especialmente +0x44 usado pelo MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/753479c32c52f481a405fb08b2a9aaede0129177/tools/profile_phase78_gs_owner_alias_flow.py" -o "%MAP%"
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
echo PHASE 78 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE78_GS_OWNER_ALIAS_FLOW\LATEST-PHASE78-GS-OWNER-ALIAS-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE78_GS_OWNER_ALIAS_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 78 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
