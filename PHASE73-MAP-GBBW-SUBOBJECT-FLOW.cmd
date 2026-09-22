@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase73_gbbw_subobject_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 73 GBBW SUBOBJECT FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo A Phase 72 nao achou setter direto de +0x44.
echo Agora seguimos ponteiros derivados como this+0x34,
echo this+0x40 etc. atraves dos helpers e somamos os offsets
echo para achar escritas efetivas em GBBW+0x44.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/dc819c56e814636e934ada627bd583f45353feb0/tools/profile_phase73_gbbw_subobject_flow.py" -o "%MAP%"
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
echo PHASE 73 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE73_GBBW_SUBOBJECT_FLOW\LATEST-PHASE73-GBBW-SUBOBJECT-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE73_GBBW_SUBOBJECT_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 73 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
