@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase67_build_button_callback_root.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 67 BUILD CALLBACK ROOT
echo ============================================================
echo.
echo Esta fase NAO altera o gameplay.
echo Ela segue somente o callback dedicado do build_button:
echo   0x00973C90
echo e compara com os callbacks irmaos dos outros botoes.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/483242d1fa951cc42ee3cb2a77aec85354d4e507/tools/profile_phase67_build_button_callback_root.py" -o "%MAP%"
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
echo PHASE 67 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE67_BUILD_BUTTON_CALLBACK_ROOT\LATEST-PHASE67-BUILD-BUTTON-CALLBACK-ROOT.txt
echo   _PACKAGE_PHASE5\_PHASE67_BUILD_BUTTON_CALLBACK_ROOT\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 67 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
