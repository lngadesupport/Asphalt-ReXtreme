@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r3.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R3
echo ================================================================
echo.
echo R3 SEMANTICA:
echo   - trata 0x009A4BB0 como corpo real do CraftCar request
echo   - reconstrui guards do CraftCar caller
echo   - preserva original + Campaign override da Phase54
echo   - tipa campos GS_Garage usados no build
echo   - tipa callback vector/status do CraftCar result
echo   - gera C++ semantico + ASM + SEMANTICS.json
echo.
echo Nenhum byte do jogo sera alterado.
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1/R2 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/1039251cd4596633909db5dca4abebc58a2e4e44/tools/reconstruct_source_r3.py" -o "%GEN%"
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
echo  SOURCE RECONSTRUCTION R3 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r3\SEMANTICS.json
echo   src-reconstructed\docs\R3-GARAGE-CRAFT-SEMANTICS.md
echo.
echo E envie tambem:
echo   src-reconstructed\reverse\r3\asm\CraftCar_RequestBody.asm.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R3 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
