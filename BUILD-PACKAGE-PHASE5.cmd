@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Package Phase 5

echo ============================================================
echo  Asphalt ReXtreme - PACKAGE PHASE 5
echo  Local UWP registration - no Microsoft Store required
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\build_package_phase5.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Package Phase 5 registered successfully.
) else (
  echo Package Phase 5 failed with code %RC%.
)
echo.
pause
exit /b %RC%
