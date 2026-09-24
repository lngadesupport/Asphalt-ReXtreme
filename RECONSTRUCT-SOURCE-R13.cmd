@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r13.py"

echo ================================================================
echo  ASPHALT ReXTREME - R13 WRITABLE OWNER RUNTIME PROBE
echo ================================================================
echo.
echo R13:
echo   - NAO usa x32dbg
echo   - codigo do probe fica em secao executavel
echo   - dados do probe ficam em secao PE gravavel
echo   - nao dereferencia owner dentro do jogo
echo   - watcher externo le owner/vtable com ReadProcessMemory
echo   - preserva a logica original do clique MONTAR
echo.
echo IMPORTANTE:
echo   - R12 deve estar revertida antes de continuar.
echo   - Este comando e apenas PLAN; nao altera AMS.exe.
echo.

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/59a3a0816902c6ea4db54d0613865a2aad3ad8e4/tools/reconstruct_source_r13.py" -o "%GEN%"
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
echo  R13 PLAN READY
echo ================================================================
echo.
echo Nenhum byte foi alterado.
echo.
echo Envie:
echo   src-reconstructed\reverse\r13\WRITABLE_OWNER_PROBE.json
echo.
echo Depois da validacao, usaremos:
echo   R13-APPLY-WRITABLE-OWNER-PROBE.cmd
echo   R13-WATCH-WRITABLE-OWNER-PROBE.cmd
echo   R13-REVERT-WRITABLE-OWNER-PROBE.cmd
echo.
echo NAO execute APPLY ainda.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] R13 plan falhou.
echo Nenhum byte deveria ter sido alterado.
pause
exit /b 1
