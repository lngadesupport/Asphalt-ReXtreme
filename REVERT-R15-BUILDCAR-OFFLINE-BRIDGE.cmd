@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCHER=%TOOLS%\r15_buildcar_offline_bridge.py"

echo ================================================================
echo  ASPHALT ReXTREME - REVERT R15 BUILDCAR OFFLINE BRIDGE
echo ================================================================
echo.

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/a0563b06c85ee94e38695f546fcc8f547060eb5d/tools/r15_buildcar_offline_bridge.py" -o "%PATCHER%"
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
echo [OK] R15 revertida.
pause
exit /b 0

:fail
echo.
echo [ERRO] Falha ao reverter R15.
pause
exit /b 1
