@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase52_preclick_build_button.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 52 PRE-CLICK BUILD BUTTON MAP
echo ============================================================
echo.
echo Alvo: o spinner que aparece NO LUGAR do botao MONTAR.
echo.
echo Esta fase:
echo   - reverte automaticamente a Phase51
echo   - volta ao estado Phase36-only
echo   - mapeia o build_button antes de qualquer clique
echo   - nao aplica novo bypass
echo   - nao reseta save/LocalState
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c9943b8bb0a25542743aa751ec2e2422c8314017/tools/profile_phase52_preclick_build_button.py" -o "%SCRIPT%"
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
echo PHASE 52 OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE52_PRECLICK_BUILD_BUTTON\LATEST-PHASE52-PRECLICK-BUILD-BUTTON.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 52 falhou.
echo O save nao foi resetado.
pause
exit /b 1
