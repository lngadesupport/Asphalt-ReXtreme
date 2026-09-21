@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Profile Phase 7 Callback Map V2

echo ============================================================
echo  Asphalt ReXtreme - PROFILE PHASE 7 CALLBACK MAP V2
echo  Uses local _PACKAGE_PHASE5 directly - no Appx lookup
echo ============================================================
echo.

if not exist "%CD%\_PACKAGE_PHASE5\AMS.exe" (
    echo [ERRO] Nao encontrei:
    echo %CD%\_PACKAGE_PHASE5\AMS.exe
    echo.
    pause
    exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\profile_phase7_callback_map_v2.ps1" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Phase 7 callback map V2 completed successfully.
) else (
  echo Phase 7 callback map V2 failed with code %RC%.
)
echo.
pause
exit /b %RC%
