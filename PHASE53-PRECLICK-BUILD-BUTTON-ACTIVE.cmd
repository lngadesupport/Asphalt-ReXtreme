@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase53_preclick_build_button_active.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 53 PRE-CLICK BUILD BUTTON ACTIVE
echo ============================================================
echo.
echo Alvo: spinner que aparece no lugar do botao MONTAR.
echo.
echo Faz somente:
echo   - build_button pre-click state = 1
echo   - mantem Phase36
echo   - mantem IsOnline global FALSE
echo   - nao toca CraftCar/request/completion
echo   - nao reseta save/LocalState
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ac6d0ec5a5aacd703448f1507033823e489b02f4/tools/profile_phase53_preclick_build_button_active.ps1" -o "%PATCH%"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PATCH%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 53 OK
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Veja se o spinner virou o botao MONTAR.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 53 falhou.
echo O save nao foi resetado.
pause
exit /b 1
