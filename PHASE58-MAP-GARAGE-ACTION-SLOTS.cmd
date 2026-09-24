@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase58_garage_action_slots.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 58 GARAGE ACTION SLOTS
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela mapeia os slots virtuais +18/+1C/+20/+24
echo da GarageBottomBarWidget e procura o caminho real do MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/b328f12bdd303490c3d0b3df5e5c8d1638403549/tools/profile_phase58_garage_action_slots.py" -o "%MAP%"
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
echo PHASE 58 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE58_GARAGE_ACTION_SLOTS\LATEST-PHASE58-GARAGE-ACTION-SLOTS.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 58 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
