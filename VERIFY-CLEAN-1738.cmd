@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Clean Baseline 1.7.3.8

echo ============================================================
echo  Asphalt ReXtreme - CLEAN BASELINE 1.7.3.8 x86
echo  Phase 1: integrity, identity, inventory and SHA-256 only
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\verify_clean_1738.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Baseline validation completed successfully.
) else (
  echo Baseline validation failed with code %RC%.
)
echo.
pause
exit /b %RC%
