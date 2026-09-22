@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase56_build_click_callback.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 56 BUILD CLICK CALLBACK MAP
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela identifica o callback real ligado ao botao MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/0aa7987a121a9c183e19b77a48fca6a791f42471/tools/profile_phase56_build_click_callback.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :done
)

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado.
  echo Instale Python 3 ou use o py.exe do Windows.
  pause
  exit /b 11
)

python.exe "%MAP%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

:done
echo.
echo PHASE 56 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE56_BUILD_CLICK_CALLBACK\LATEST-PHASE56-BUILD-CLICK-CALLBACK.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 56 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
