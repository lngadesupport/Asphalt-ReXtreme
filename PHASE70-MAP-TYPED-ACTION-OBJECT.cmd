@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase70_typed_action_object.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 70 TYPED ACTION OBJECT
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela tipa a vtable 0x01832394, segue o caller 0x00A6CA80
echo e mapeia cada resolucao 0x00902140 -> par de campos,
echo incluindo +0x40/+0x44.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/75d8181b92ff8f0f6c8c2db435854025e704a348/tools/profile_phase70_typed_action_object.py" -o "%MAP%"
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
echo PHASE 70 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE70_TYPED_ACTION_OBJECT\LATEST-PHASE70-TYPED-ACTION-OBJECT.txt
echo   _PACKAGE_PHASE5\_PHASE70_TYPED_ACTION_OBJECT\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 70 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
