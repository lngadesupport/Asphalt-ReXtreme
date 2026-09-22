@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase82_owner_pair_postinit.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 82 OWNER PAIR POST-INIT FAST
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Esta versao corrige o travamento da Phase 82 original.
echo O indice de funcoes/calls e criado uma unica vez e o progresso
echo aparece na tela em 7 etapas.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/12b27168ee95281eaa4afbaa36c79648be0c8980/tools/profile_phase82_owner_pair_postinit.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 82 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE82_OWNER_PAIR_POSTINIT\LATEST-PHASE82-OWNER-PAIR-POSTINIT.txt
echo   _PACKAGE_PHASE5\_PHASE82_OWNER_PAIR_POSTINIT\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 82 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
