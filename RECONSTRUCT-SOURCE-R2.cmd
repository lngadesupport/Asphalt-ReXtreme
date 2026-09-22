@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r2.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R2
echo ================================================================
echo.
echo R2:
echo   - usa AMS.exe como fonte de verdade
echo   - reagrupa shards do atlas em funcoes logicas
echo   - desassembla x86 com Capstone
echo   - reconstrui GarageBottomBarWidget / GS_Garage / CraftCar
echo   - gera ASM completo das funcoes alvo
echo   - atualiza src-reconstructed\ para fase R2
echo.
echo Nenhum byte do jogo sera alterado.
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] R1 nao encontrado. Execute RECONSTRUCT-SOURCE-R1.cmd primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/7f81afca759902d8087237adb02eac4abe3782ff/tools/reconstruct_source_r2.py" -o "%GEN%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    py.exe -3 -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  py.exe -3 -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    python.exe -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  python.exe -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  SOURCE RECONSTRUCTION R2 OK
echo ================================================================
echo.
echo Para eu analisar a R2, envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r2\LOGICAL_FUNCTIONS.json
echo   src-reconstructed\reverse\r2\GARAGE_CHAIN.json
echo.
echo Se puder, envie tambem:
echo   src-reconstructed\docs\R2-GARAGE-CRAFT.md
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R2 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
