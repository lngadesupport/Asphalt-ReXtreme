@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Profile Phase 6C

echo ============================================================
echo  Asphalt ReXtreme - PROFILE PHASE 6C
echo  Login/sync failure branch mapper
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase6c_login_error.ps1"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 6C completed successfully.
) else (
  echo Phase 6C failed with code %RC%.
)
echo.
pause
exit /b %RC%
