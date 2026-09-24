@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 10

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/3] profile_phase10_local_sync.ps1
curl.exe -fL "%BASE%/tools/profile_phase10_local_sync.ps1" -o "tools\profile_phase10_local_sync.ps1" || goto :fail

echo [2/3] BUILD-PROFILE-PHASE10-LOCAL-SYNC.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE10-LOCAL-SYNC.cmd" -o "BUILD-PROFILE-PHASE10-LOCAL-SYNC.cmd" || goto :fail

echo [3/3] RESTORE-PROFILE-PHASE10.cmd
curl.exe -fL "%BASE%/RESTORE-PROFILE-PHASE10.cmd" -o "RESTORE-PROFILE-PHASE10.cmd" || goto :fail

echo.
echo ============================================================
echo  PHASE 10 FILES READY
echo ============================================================
echo Execute:
echo   BUILD-PROFILE-PHASE10-LOCAL-SYNC.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar a Phase 10.
echo.
pause
exit /b 1
