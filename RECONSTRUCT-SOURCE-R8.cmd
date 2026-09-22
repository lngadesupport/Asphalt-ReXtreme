@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r8.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R8
echo ================================================================
echo.
echo R8 STATUS=0 SUCCESS SLICE:
echo   - executa simbolicamente o callback 0x00AA4D00
echo   - compara status 0 contra codigos de erro conhecidos
echo   - separa CALLs exclusivas do sucesso
echo   - verifica se 0x009C51E0 e success-only
echo   - classifica 0x00AC9D60 / own_car como mutacao ou UI
echo   - procura ownership/profile/sync ANTES do refresh visual
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R7 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/d6df49d3878d3f3c63fbc93a08e5953e4c570af2/tools/reconstruct_source_r8.py" -o "%GEN%"
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
echo  SOURCE RECONSTRUCTION R8 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r8\STATUS0_SUCCESS_SLICE.json
echo   src-reconstructed\docs\R8-STATUS0-SUCCESS-SLICE.md
echo.
echo Se "Can prepare runtime patch: True", envie tambem:
echo   src-reconstructed\reverse\r8\asm\fn_*.asm.txt
echo dos candidatos TOP.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R8 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
