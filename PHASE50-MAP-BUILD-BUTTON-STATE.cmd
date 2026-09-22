@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase50_build_button_state.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 50 BUILD BUTTON STATE
echo ============================================================
echo.
echo Analisa somente a funcao 0x00973510:
echo   - xref direto de build_button
echo   - chamada pelo completion real da montagem
echo   - branches e writes de estado da UI
echo.
echo Nao aplica patch.
echo Nao altera save/LocalState.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/a8a108013deeca7c4dd27ebff5221dadb22ed188/tools/profile_phase50_build_button_state.py" -o "%SCRIPT%"
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
echo PHASE 50 OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE50_BUILD_BUTTON_STATE\LATEST-PHASE50-BUILD-BUTTON-STATE.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 50 falhou.
echo Nenhum patch foi aplicado e o save nao foi resetado.
pause
exit /b 1
