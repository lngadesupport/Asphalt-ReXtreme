@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Asphalt ReXtreme - Campaign Crash Probe
echo ============================================================
echo.
echo Este probe NAO escaneia a pasta inteira.
echo Ele captura somente a execucao/crash do AMS.exe.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\capture_ams_crash.ps1" ^
  -GameRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Probe terminou com codigo %RC%.
pause
exit /b %RC%
