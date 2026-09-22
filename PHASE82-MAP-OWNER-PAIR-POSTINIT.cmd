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
echo  ASPHALT ReXTREME - PHASE 82 OWNER PAIR POST-INIT
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo A Phase 81 provou que GS_Garage+0x354/+0x358 nasce zerado.
echo Agora mapeamos quem preenche esse par depois da construcao,
echo filtrando por evidencia tipada da GS_Garage.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/d774fa09133dfd2ac3c2611d7a58529bacc70467/tools/profile_phase82_owner_pair_postinit.py" -o "%MAP%"
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
