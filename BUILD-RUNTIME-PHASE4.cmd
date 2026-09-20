@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Build Runtime Phase 4

echo ============================================================
echo  Asphalt ReXtreme - BUILD RUNTIME PHASE 4
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\build_runtime_phase4.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Runtime Phase 4 build completed successfully.
) else (
  echo Runtime Phase 4 build failed with code %RC%.
)
echo.
pause
exit /b %RC%
