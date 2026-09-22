@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase49_build_button_map.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 49 BUILD BUTTON / SPINNER MAP
echo ============================================================
echo.
echo Esta fase:
echo   - reverte automaticamente a Phase48
echo   - volta ao estado Phase36-only
echo   - mapeia 0x0096F3B0
echo   - procura build_button/template_build_button
echo   - nao aplica novo bypass
echo   - nao reseta save/LocalState
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/21bc611f9a068a52791ac8101764e6e26f3fac0a/tools/profile_phase49_build_button_map.py" -o "%SCRIPT%"
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
echo PHASE 49 OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE49_BUILD_BUTTON_MAP\LATEST-PHASE49-BUILD-BUTTON-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 49 falhou.
echo O save nao foi resetado.
pause
exit /b 1
