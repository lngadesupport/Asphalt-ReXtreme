@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r12.py"

echo ================================================================
echo  ASPHALT ReXTREME - R12 ASLR-SAFE OWNER RUNTIME PROBE
echo ================================================================
echo.
echo IMPORTANTE:
echo   - Reverta R10/R11 antes de rodar este PLAN.
echo   - Este comando apenas prepara o probe.
echo   - Nao chama BuildCar e nao muda a logica do clique.
echo.
echo R12 captura em runtime:
echo   - quantas vezes o callback MONTAR executou
echo   - GBBW this
echo   - GBBW+0x44 buildSignal
echo   - GBBW+0x04 owner
echo   - GBBW+0x08 owner control
echo   - vtable REAL do owner
echo   - delta ASLR e vtable normalizada
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/993f4d7b5918273f8b7155900d5605bd1097fe01/tools/reconstruct_source_r12.py" -o "%GEN%"
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
echo  R12 PLAN READY
echo ================================================================
echo.
echo Nenhum byte foi alterado ainda.
echo.
echo Envie:
echo   src-reconstructed\reverse\r12\OWNER_RUNTIME_PROBE.json
echo.
echo O plano tambem gera:
echo   R12-APPLY-OWNER-PROBE.cmd
echo   R12-WATCH-OWNER-PROBE.cmd
echo   R12-REVERT-OWNER-PROBE.cmd
echo.
echo NAO execute APPLY ainda; primeiro envie o JSON do PLAN.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R12 plan falhou.
echo Nenhum byte deveria ter sido alterado.
pause
exit /b 1
