@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - AMS Phase 2

echo ============================================================
echo  Asphalt ReXtreme - AMS PHASE 2
echo  Builds a verified patched COPY. Original AMS stays untouched.
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\build_ams_phase2.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo AMS Phase 2 completed successfully.
) else (
  echo AMS Phase 2 failed with code %RC%.
)
echo.
pause
exit /b %RC%
