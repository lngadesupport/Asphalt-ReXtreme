@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase81_gs_base_owner_init.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 81 GS BASE OWNER INIT
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela segue a cadeia de base constructors da GS_Garage,
echo iniciando em 0x00B070C0, para descobrir quem inicializa
echo efetivamente GS_Garage+0x354/+0x358 e qual valor e gravado.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/b5124b287fc787ea19193947267e0c68ec42989b/tools/profile_phase81_gs_base_owner_init.py" -o "%MAP%"
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
echo PHASE 81 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE81_GS_BASE_OWNER_INIT\LATEST-PHASE81-GS-BASE-OWNER-INIT.txt
echo   _PACKAGE_PHASE5\_PHASE81_GS_BASE_OWNER_INIT\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 81 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
