@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Apply R17 Local Event Runtime

call "%~dp0BUILD-R17-LOCAL-EVENT-RUNTIME.cmd"
if errorlevel 1 exit /b %ERRORLEVEL%

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\apply_r17_local_event_runtime.ps1" ^
  -Mode Apply ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.

if "%RC%"=="0" (
  echo ============================================================
  echo  R17 LOCAL EVENT RUNTIME APPLIED
  echo ============================================================
  echo.
  echo Run:
  echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo R17 apply failed with code %RC%.
)

echo.
pause
exit /b %RC%
