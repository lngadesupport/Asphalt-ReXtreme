@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "TRACER=%TOOLS%\trace_montar_frida.py"

echo ================================================================
echo  ASPHALT ReXTREME - TRACE MONTAR (SEM x32dbg)
echo ================================================================
echo.
echo Este tracer:
echo   - NAO altera AMS.exe
echo   - NAO usa x32dbg
echo   - anexa temporariamente ao AMS.exe com Frida
echo   - grava o caminho do clique MONTAR
echo   - rastreia CALLs no mesmo thread
echo   - marca SignalInvoke / BuildCar / CraftCar
echo   - observa WinINet para URL/verbo HTTP
echo.
echo Saida:
echo   _TRACE_MONTAR\MONTAR-TRACE-*.jsonl
echo   _TRACE_MONTAR\MONTAR-SUMMARY-*.json
echo.

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/088cadbd87c279f32d6567c5e77013b33ca5a9f5/tools/trace_montar_frida.py" -o "%TRACER%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import frida" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando Frida...
    py.exe -3 -m pip install --user --upgrade frida frida-tools
    if errorlevel 1 goto :fail
  )
  goto :run_py
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import frida" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando Frida...
    python.exe -m pip install --user --upgrade frida frida-tools
    if errorlevel 1 goto :fail
  )
  goto :run_python
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:run_py
tasklist /FI "IMAGENAME eq AMS.exe" | find /I "AMS.exe" >nul
if errorlevel 1 (
  echo [INFO] AMS.exe ainda nao esta aberto.
  echo [INFO] Abrindo o launcher do jogo...
  start "" "%ROOT%\_PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd"
)
py.exe -3 -u "%TRACER%" --project-root "%ROOT%" --seconds 180
if errorlevel 1 goto :fail
goto :ok

:run_python
tasklist /FI "IMAGENAME eq AMS.exe" | find /I "AMS.exe" >nul
if errorlevel 1 (
  echo [INFO] AMS.exe ainda nao esta aberto.
  echo [INFO] Abrindo o launcher do jogo...
  start "" "%ROOT%\_PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd"
)
python.exe -u "%TRACER%" --project-root "%ROOT%" --seconds 180
if errorlevel 1 goto :fail
goto :ok

:ok
echo.
echo ================================================================
echo  TRACE MONTAR FINALIZADO
echo ================================================================
echo.
echo Envie os 2 arquivos mais recentes da pasta:
echo   _TRACE_MONTAR
echo.
echo Principalmente:
echo   MONTAR-SUMMARY-*.json
echo   MONTAR-TRACE-*.jsonl
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] O tracer falhou.
echo O AMS.exe nao foi modificado no disco.
echo Se aparecer erro de permissao ao anexar, execute este CMD como Administrador.
echo.
pause
exit /b 1
