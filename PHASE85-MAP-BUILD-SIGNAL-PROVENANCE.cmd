@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase85_build_signal_provenance.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado em _PACKAGE_PHASE5.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ================================================================
echo  ASPHALT ReXTREME - PHASE 85 BUILD SIGNAL PROVENANCE MAX
echo ================================================================
echo.
echo Esta fase NAO altera gameplay.
echo.
echo Modelo confirmado:
echo   GarageBottomBarWidget+0x44 = build signal shared_ptr.object
echo   GarageBottomBarWidget+0x48 = build signal shared_ptr.control
echo.
echo O rastreador parte somente de instancias tipadas da GBBW:
echo   GS_Garage+0x35C
echo e segue ECX, ate 8 argumentos, spills/reloads, LEA, tail-calls
echo e chamadas virtuais resolvidas da GarageBottomBarWidget.
echo.
echo Limites altos:
echo   max states = 500000
echo   max depth  = 64
echo O rastreador para antes se a fila convergir.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/bc373ba4b09552f6761cf9f4edb9f13924d8d7fb/tools/profile_phase85_build_signal_provenance.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%MAP%" --project-root "%ROOT%" --max-states 500000 --max-depth 64
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%MAP%" --project-root "%ROOT%" --max-states 500000 --max-depth 64
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  PHASE 85 OK
echo ================================================================
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE85_BUILD_SIGNAL_PROVENANCE\LATEST-PHASE85-BUILD-SIGNAL-PROVENANCE.txt
echo   _PACKAGE_PHASE5\_PHASE85_BUILD_SIGNAL_PROVENANCE\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 85 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
