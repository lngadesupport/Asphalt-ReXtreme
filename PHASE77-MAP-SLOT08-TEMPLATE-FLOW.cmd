@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase77_slot08_template_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 77 SLOT08 / TEMPLATE FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue a inicializacao da GarageBottomBarWidget:
echo   slot+0x08 0x0096F380
echo   template_build 0x0096F3B0
echo   ready_ui 0x00974480
echo e procura quem escreve/endereca os campos de callback,
echo especialmente +0x44 usado pelo MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/017da66c5ba7ea39a95f93d53eebeedfbf88385f/tools/profile_phase77_slot08_template_flow.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 77 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE77_SLOT08_TEMPLATE_FLOW\LATEST-PHASE77-SLOT08-TEMPLATE-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE77_SLOT08_TEMPLATE_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 77 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
