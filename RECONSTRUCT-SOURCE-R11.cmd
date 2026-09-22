@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r11.py"

echo ================================================================
echo  ASPHALT ReXTREME - R11 GS SUBOBJECT OWNER FALLBACK PLAN
echo ================================================================
echo.
echo IMPORTANTE:
echo   1. Reverta a R10 primeiro:
echo      R10-REVERT-OWNER-FALLBACK.cmd
echo   2. Este comando R11 e apenas PLAN.
echo.
echo R11:
echo   - enumera vtables finais instaladas pelo ctor de GS_Garage
echo   - filtra subobjetos com slots ate +0xDC
echo   - testa GBBW+0x04 contra essas vtables secundarias
echo   - ajusta owner - subobject_offset
echo   - valida novamente vtable primaria 0x0186A9CC
echo   - so entao chama BuildCar +0x110
echo   - gera APPLY e REVERT
echo   - NAO altera AMS.exe neste comando
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/e112e2ccf96d173119843d76312a894183a6dce3/tools/reconstruct_source_r11.py" -o "%GEN%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    py.exe -3 -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  py.exe -3 -u "%GEN%" --project-root "%ROOT%" --plan
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
  python.exe -u "%GEN%" --project-root "%ROOT%" --plan
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  R11 PLAN READY
echo ================================================================
echo.
echo Nenhum byte foi alterado.
echo.
echo Envie:
echo   src-reconstructed\reverse\r11\SUBOBJECT_OWNER_FALLBACK.json
echo.
echo NAO execute R11-APPLY-SUBOBJECT-OWNER-FALLBACK.cmd ainda.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R11 plan falhou.
echo Nenhum byte deveria ter sido alterado.
pause
exit /b 1
