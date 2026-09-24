@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Profile Phase 6B Context

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase6b_context.ps1"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Profile Phase 6B context completed successfully.
) else (
  echo Profile Phase 6B context failed with code %RC%.
)
echo.
pause
exit /b %RC%
