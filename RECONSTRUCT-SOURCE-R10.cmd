@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r10.py"

echo ================================================================
echo  ASPHALT ReXTREME - R10 GUARDED OWNER FALLBACK PLAN
echo ================================================================
echo.
echo R10:
echo   - NAO aplica patch neste comando
echo   - procura padding executavel seguro usando o tamanho EXATO do stub
echo   - prepara trampoline no callback 0x00973C90
echo   - preserva buildSignal original quando existir
echo   - se buildSignal for NULL, testa GBBW+0x04
echo   - so chama BuildCar se vtable == GS_Garage 0x0186A9CC
echo   - aceita CC/90/00 somente sem referencias decodificadas
echo   - gera APPLY e REVERT prontos
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%ROOT%\_PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX\FUNCTIONS.csv" (
  echo [ERRO] FULL GAME ATLAS MAX nao encontrado.
  pause
  exit /b 12
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/aaaea85d5dd4dd9b2624c21300788b456e4268e6/tools/reconstruct_source_r10.py" -o "%GEN%"
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
echo  R10 PATCH PLAN READY
echo ================================================================
echo.
echo Nenhum byte do AMS.exe foi alterado.
echo.
echo Envie:
echo   src-reconstructed\reverse\r10\OWNER_FALLBACK_PATCH.json
echo.
echo O script tambem gerou:
echo   R10-APPLY-OWNER-FALLBACK.cmd
echo   R10-REVERT-OWNER-FALLBACK.cmd
echo.
echo NAO execute APPLY ainda; primeiro envie o JSON para validacao.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R10 plan falhou.
echo Nenhum byte deveria ter sido alterado.
pause
exit /b 1
