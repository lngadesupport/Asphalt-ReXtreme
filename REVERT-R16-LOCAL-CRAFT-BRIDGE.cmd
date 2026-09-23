@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCHER=%TOOLS%\r16_local_craft_bridge.py"

echo ================================================================
echo  ASPHALT ReXTREME - REVERT R16 LOCAL CRAFT BRIDGE
echo ================================================================
echo.

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3aa4e716936013ec071e9d1ebac414c4489e7fe6/tools/r16_local_craft_bridge.py" -o "%PATCHER%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%PATCHER%" --project-root "%ROOT%" --revert
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%PATCHER%" --project-root "%ROOT%" --revert
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo [OK] R16 revertida. R15 permanece aplicada.
pause
exit /b 0

:fail
echo.
echo [ERRO] Falha ao reverter R16.
echo Verifique _BACKUPS\R16\state.json e a mensagem acima.
pause
exit /b 1
