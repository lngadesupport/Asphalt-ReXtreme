@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase54_craftcar_state2.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 54 CRAFTCAR STATE 2
echo ============================================================
echo.
echo Mantem:
echo   - Phase53 MONTAR ativo
echo   - Phase36 popup bypass
echo   - IsOnline global FALSE
echo.
echo Altera somente:
echo   - estado local consumido pelo guard do CraftCar: 2
echo.
echo Nao chama CraftCar a forca e nao reseta o save.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/1b759b2ba8f1cfa067169ea1b96b23d5d79a6002/tools/profile_phase54_craftcar_state2.ps1" -o "%PATCH%"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PATCH%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 54 OK
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Clique em MONTAR uma vez e observe o que acontece.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 54 falhou.
echo O save nao foi resetado.
pause
exit /b 1
