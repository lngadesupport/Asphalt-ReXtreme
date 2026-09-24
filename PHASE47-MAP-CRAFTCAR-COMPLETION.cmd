@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase47_craftcar_completion.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 47 CRAFTCAR COMPLETION
echo ============================================================
echo.
echo Analisa somente o callback 0x00AA4D00.
echo Nao aplica patch.
echo Nao altera save/LocalState.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/2b055600cd60f9a2d8fbb5357559c1bf6f1883a6/tools/profile_phase47_craftcar_completion.py" -o "%SCRIPT%"
if errorlevel 1 goto :fail

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%SCRIPT%" --project-root "%ROOT%"
  goto :after
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 ainda nao esta no PATH.
  goto :fail
)

python "%SCRIPT%" --project-root "%ROOT%"

:after
if errorlevel 1 goto :fail

echo.
echo PHASE 47 OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE47_CRAFTCAR_COMPLETION\LATEST-PHASE47-CRAFTCAR-COMPLETION.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 47 falhou.
echo Nenhum patch foi aplicado e o save nao foi resetado.
pause
exit /b 1
