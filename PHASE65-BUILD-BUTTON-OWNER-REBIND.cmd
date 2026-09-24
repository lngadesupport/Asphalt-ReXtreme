@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase65_build_button_owner_rebind.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 65 BUILD BUTTON OWNER REBIND
echo ============================================================
echo.
echo Root patch:
echo   template_build_button
echo   owner +0xBC lookup
echo   force existing +0xDC/+0xD0 rebind/register path
echo.
echo IsOnline global permanece FALSE.
echo CraftCar nao e chamado artificialmente.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ffde555c3db7917d4516f8a84eca81f469d32536/tools/profile_phase65_build_button_owner_rebind.ps1" -o "%PATCH%"
if errorlevel 1 goto :fail

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PATCH%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 65 OK
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Na garagem:
echo   1. confira se existe apenas um botao MONTAR
echo   2. clique MONTAR uma vez
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 65 falhou.
echo Nao abra o jogo se o patch nao terminou com PHASE 65 OK.
pause
exit /b 1
