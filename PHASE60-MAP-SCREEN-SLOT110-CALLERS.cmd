@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase60_screen_slot110_callers.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 60 SCREEN SLOT +0x110 MAP
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela localiza todos os CALLs virtuais no slot +0x110
echo e identifica quem pode despachar para GS_Garage::Build.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/db1e688bb02d847b912242f20ab219ce2a262629/tools/profile_phase60_screen_slot110_callers.py" -o "%MAP%"
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
  pause
  exit /b 11
)

python.exe "%MAP%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

:done
echo.
echo PHASE 60 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE60_SCREEN_SLOT110_CALLERS\LATEST-PHASE60-SCREEN-SLOT110-CALLERS.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 60 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
