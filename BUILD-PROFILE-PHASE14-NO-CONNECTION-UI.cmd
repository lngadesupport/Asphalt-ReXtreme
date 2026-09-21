@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 14 No Connection UI

echo ============================================================
echo  Asphalt ReXtreme - PHASE 14 NO CONNECTION UI
echo  Offline real + onboarding + suppress connection blockers
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase14_no_connection_ui.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 14 aplicada com sucesso.
  echo Launch: _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
) else (
  echo Phase 14 falhou com codigo %RC%.
)
echo.
pause
exit /b %RC%
