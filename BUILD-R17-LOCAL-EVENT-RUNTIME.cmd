@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Build R17 Local Event Runtime

echo ============================================================
echo  Asphalt ReXtreme - BUILD R17 LOCAL EVENT RUNTIME
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\build_r17_local_event_runtime.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.

if not "%RC%"=="0" (
  echo Build failed with code %RC%.
  pause
  exit /b %RC%
)

echo Build completed.
echo.
pause
exit /b 0
