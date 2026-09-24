@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r9.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R9
echo ================================================================
echo.
echo R9 SUCCESS-EFFECT WRITERS:
echo   - classifica SafeProfileRunning 0x00C1E2E0
echo   - analisa os success roots 0x00F6F320 e 0x00F74EA0
echo   - ranqueia WRITES reais em objeto/global
echo   - separa UI de ownership/profile/save
echo   - decide entre patch de mutacao existente ou injecao no ramo de sucesso
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R8 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/7c4d0fd5c365a911cce865904460c92b1cb9397b/tools/reconstruct_source_r9.py" -o "%GEN%"
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
echo  SOURCE RECONSTRUCTION R9 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r9\SUCCESS_EFFECT_WRITES.json
echo   src-reconstructed\docs\R9-SUCCESS-EFFECT-WRITES.md
echo.
echo Se Recommended strategy = PATCH_EXISTING_MUTATION,
echo envie tambem os ASM TOP de:
echo   src-reconstructed\reverse\r9\asm\
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R9 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
