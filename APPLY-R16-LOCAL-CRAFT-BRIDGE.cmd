@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCHER=%TOOLS%\r16_local_craft_bridge.py"

echo ================================================================
echo  ASPHALT ReXTREME - R16 LOCAL CRAFT BRIDGE
echo ================================================================
echo.
echo R16 substitui o backend CraftCar morto por conclusao local:
echo   1. preserva a operacao criada pelo CraftCarCaller
echo   2. ignora somente a antiga chamada de rede
echo   3. deixa GS_Garage registrar o listener original
echo   4. apos o pos-build, dispara status SUCCESS=0 localmente
echo.
echo PRE-REQUISITO:
echo   R15 deve estar aplicada.
echo.
echo O patch:
echo   - valida todos os bytes
echo   - procura cave executavel somente em padding CC
echo   - usa apenas rel32 (ASLR-safe)
echo   - cria backup e state.json
echo   - pode ser revertido cirurgicamente
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3aa4e716936013ec071e9d1ebac414c4489e7fe6/tools/r16_local_craft_bridge.py" -o "%PATCHER%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 goto :py

where python.exe >nul 2>nul
if not errorlevel 1 goto :python

echo [ERRO] Python 3 nao encontrado.
goto :fail

:py
echo [1/2] Validando plano R16...
py.exe -3 -u "%PATCHER%" --project-root "%ROOT%" --plan
if errorlevel 1 goto :fail
echo.
echo [2/2] Aplicando R16...
py.exe -3 -u "%PATCHER%" --project-root "%ROOT%" --apply
if errorlevel 1 goto :fail
goto :ok

:python
echo [1/2] Validando plano R16...
python.exe -u "%PATCHER%" --project-root "%ROOT%" --plan
if errorlevel 1 goto :fail
echo.
echo [2/2] Aplicando R16...
python.exe -u "%PATCHER%" --project-root "%ROOT%" --apply
if errorlevel 1 goto :fail
goto :ok

:ok
echo.
echo ================================================================
echo  R16 APLICADA
echo ================================================================
echo.
echo TESTE NORMAL, SEM x32dbg e SEM Frida:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Va para a garagem e clique MONTAR uma vez.
echo.
echo Se funcionar, observe:
echo   - se o carro passa a ser adquirido/montado
echo   - se os blueprints mudam
echo   - se o botao/garagem atualiza
echo   - se o estado persiste depois de reiniciar o jogo
echo.
echo Relatorio:
echo   _TRACE_MONTAR\R16-LOCAL-CRAFT-BRIDGE.json
echo.
echo Se houver crash ou comportamento incorreto, NAO aplique outro patch.
echo Execute:
echo   REVERT-R16-LOCAL-CRAFT-BRIDGE.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R16 nao foi aplicada.
echo Nenhum byte desconhecido e sobrescrito de proposito.
echo.
pause
exit /b 1
