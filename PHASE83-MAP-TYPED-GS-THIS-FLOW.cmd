@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase83_typed_gs_this_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 83 TYPED GS THIS FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela parte dos 147 metodos reais da vtable da GS_Garage
echo e segue somente o MESMO ponteiro this por ECX/aliases/LEA,
echo incluindo &this+0x354/+0x358 passados como argumentos.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/d6c9bf82e5a0743a113f98c9639bfce33819b730/tools/profile_phase83_typed_gs_this_flow.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 83 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE83_TYPED_GS_THIS_FLOW\LATEST-PHASE83-TYPED-GS-THIS-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE83_TYPED_GS_THIS_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 83 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
