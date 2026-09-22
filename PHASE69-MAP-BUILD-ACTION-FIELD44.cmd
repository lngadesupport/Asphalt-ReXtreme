@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase69_build_action_field44.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 69 FIELD +0x44 WRITER MAP
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Corrige o scanner da Phase 68 para capturar disp8/disp32,
echo incluindo o acesso real 8B 49 44 do callback MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/9f7630bc943d83d48f01376db88f7f33d70c66d7/tools/profile_phase69_build_action_field44.py" -o "%MAP%"
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
echo PHASE 69 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE69_BUILD_ACTION_FIELD44\LATEST-PHASE69-BUILD-ACTION-FIELD44.txt
echo   _PACKAGE_PHASE5\_PHASE69_BUILD_ACTION_FIELD44\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 69 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
