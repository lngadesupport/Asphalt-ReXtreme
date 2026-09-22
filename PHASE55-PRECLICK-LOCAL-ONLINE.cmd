@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase55_preclick_local_online.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 55 PRE-CLICK LOCAL ONLINE
echo ============================================================
echo.
echo Mantem:
echo   - Phase53 MONTAR ativo
echo   - Phase54 CraftCar state 2
echo   - Phase36 popup bypass
echo   - IsOnline global FALSE
echo.
echo Altera somente:
echo   - desvio offline do handler pre-clique
echo.
echo Nao reseta save e nao liga a rede global.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ba06f4ac0c23dbc7d37b754de77bd5f9b77636cf/tools/profile_phase55_preclick_local_online.ps1" -o "%PATCH%"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PATCH%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 55 OK
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Clique em MONTAR uma vez.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 55 falhou.
echo O save nao foi resetado.
pause
exit /b 1
