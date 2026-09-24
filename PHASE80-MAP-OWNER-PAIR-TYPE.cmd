@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase80_owner_pair_type.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 80 OWNER PAIR TYPE
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela mapeia o par GS_Garage+0x354/+0x358 que e passado ao
echo construtor da GarageBottomBarWidget e armazenado em +0x04/+0x08.
echo O objetivo e descobrir se esse par permite recuperar um this
echo valido da GS_Garage para o handler +0x110.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/4be2665d554d999678395736ac83a9b0742fc604/tools/profile_phase80_owner_pair_type.py" -o "%MAP%"
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
echo PHASE 80 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE80_OWNER_PAIR_TYPE\LATEST-PHASE80-OWNER-PAIR-TYPE.txt
echo   _PACKAGE_PHASE5\_PHASE80_OWNER_PAIR_TYPE\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 80 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
