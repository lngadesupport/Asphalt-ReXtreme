@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase62_garage_bottombar_owner.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 62 GARAGE BOTTOMBAR OWNER
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela mapeia quem cria a GarageBottomBarWidget,
echo quais argumentos/owners chegam ao construtor
echo e a cadeia ate GS_Garage.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ba5fd2411503556c5325430eaa9278831d39e353/tools/profile_phase62_garage_bottombar_owner.py" -o "%MAP%"
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
echo PHASE 62 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE62_GARAGE_BOTTOMBAR_OWNER\LATEST-PHASE62-GARAGE-BOTTOMBAR-OWNER.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 62 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
