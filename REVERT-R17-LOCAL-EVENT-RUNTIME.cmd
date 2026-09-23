@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Revert R17 Local Event Runtime

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\apply_r17_local_event_runtime.ps1" ^
  -Mode Revert ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
