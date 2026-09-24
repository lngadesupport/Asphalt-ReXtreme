@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCHER=%TOOLS%\r15_buildcar_offline_bridge.py"

echo ================================================================
echo  ASPHALT ReXTREME - R15 BUILDCAR OFFLINE BRIDGE
echo ================================================================
echo.
echo Patch local ao GS_Garage::BuildCar:
echo   JNE online_path  -^>  JMP online_path
echo.
echo GlobalIsOnline continua FALSE globalmente.
echo Nenhum outro fluxo de rede e reativado.
echo.
echo O patch:
echo   - valida bytes antes de alterar
echo   - cria backup
echo   - verifica bytes depois
echo   - gera relatorio JSON
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/a0563b06c85ee94e38695f546fcc8f547060eb5d/tools/r15_buildcar_offline_bridge.py" -o "%PATCHER%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 goto :use_py

where python.exe >nul 2>nul
if not errorlevel 1 goto :use_python

echo [ERRO] Python 3 nao encontrado.
goto :fail

:use_py
echo [1/2] Validando...
py.exe -3 -u "%PATCHER%" --project-root "%ROOT%" --plan
if errorlevel 1 goto :fail
echo.
echo [2/2] Aplicando...
py.exe -3 -u "%PATCHER%" --project-root "%ROOT%" --apply
if errorlevel 1 goto :fail
goto :ok

:use_python
echo [1/2] Validando...
python.exe -u "%PATCHER%" --project-root "%ROOT%" --plan
if errorlevel 1 goto :fail
echo.
echo [2/2] Aplicando...
python.exe -u "%PATCHER%" --project-root "%ROOT%" --apply
if errorlevel 1 goto :fail
goto :ok

:ok
echo.
echo ================================================================
echo  R15 APLICADA
echo ================================================================
echo.
echo Agora execute:
echo   TRACE-MONTAR-R14.cmd
echo.
echo Quando aparecer:
echo   ^>^>^> AGORA clique MONTAR UMA VEZ no jogo. ^<^<^<
echo clique MONTAR uma vez.
echo.
echo Envie os novos:
echo   _TRACE_MONTAR\MONTAR-SUMMARY-*.json
echo   _TRACE_MONTAR\MONTAR-TRACE-*.jsonl
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R15 nao foi aplicada.
echo Confira a mensagem acima. Bytes desconhecidos sao recusados de proposito.
echo.
pause
exit /b 1
