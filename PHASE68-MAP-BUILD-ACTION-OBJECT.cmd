@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase68_build_action_object.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 68 BUILD ACTION OBJECT
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue a cadeia real do clique:
echo   build_button callback 0x00973C90
echo   register helper 0x0096E4B0
echo   invoke helper   0x00936BE0
echo e mapeia o objeto guardado em +0x44.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/df468dd1ac1a1a99001ce170cf07412ab05341c4/tools/profile_phase68_build_action_object.py" -o "%MAP%"
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
echo PHASE 68 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE68_BUILD_ACTION_OBJECT\LATEST-PHASE68-BUILD-ACTION-OBJECT.txt
echo   _PACKAGE_PHASE5\_PHASE68_BUILD_ACTION_OBJECT\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 68 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
