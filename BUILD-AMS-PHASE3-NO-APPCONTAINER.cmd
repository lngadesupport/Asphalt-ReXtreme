@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - AMS Phase 3

echo ============================================================
echo  Asphalt ReXtreme - AMS PHASE 3
echo  Clears AppContainer on a COPY of the verified Phase 2 AMS.
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\build_ams_phase3_no_appcontainer.ps1" ^
  -SourceDir "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo AMS Phase 3 completed successfully.
) else (
  echo AMS Phase 3 failed with code %RC%.
)
echo.
pause
exit /b %RC%
