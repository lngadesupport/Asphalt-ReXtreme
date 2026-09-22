@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r1.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R1
echo ================================================================
echo.
echo Entrada:
echo   _PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX
echo.
echo Saida:
echo   src-reconstructed\
echo.
echo R1:
echo   - indexa 100%% das funcoes do atlas
echo   - consome CALL graph, RTTI, vtables e string XREFs
echo   - cria mapa VA ^<-> source
echo   - gera subgrafos Garage/UI/Network/Profile
echo   - cria classes iniciais GarageBottomBarWidget / GS_Garage / CraftCar
echo   - cria arquitetura OfflineBackend
echo   - preserva todas as funcoes nao resolvidas em CSV
echo.
echo Nenhum byte do jogo sera alterado.
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX\SUMMARY.json" (
  echo [ERRO] FULL GAME ATLAS MAX nao encontrado.
  echo Execute primeiro FULL-GAME-ATLAS-MAX.cmd.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f1be942177865868a4565a83581fda956aa96495/tools/reconstruct_source_r1.py" -o "%GEN%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  SOURCE RECONSTRUCTION R1 OK
echo ================================================================
echo.
echo Abra:
echo   src-reconstructed\README.md
echo.
echo Para a proxima etapa, envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\GARAGE_SUBGRAPH.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R1 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
