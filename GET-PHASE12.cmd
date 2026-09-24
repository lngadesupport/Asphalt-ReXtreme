@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 12

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/3] profile_phase12_local_offline.ps1
curl.exe -fL "%BASE%/tools/profile_phase12_local_offline.ps1" -o "tools\profile_phase12_local_offline.ps1" || goto :fail

echo [2/3] BUILD-PROFILE-PHASE12-LOCAL-OFFLINE.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE12-LOCAL-OFFLINE.cmd" -o "BUILD-PROFILE-PHASE12-LOCAL-OFFLINE.cmd" || goto :fail

echo [3/3] RESTORE-PROFILE-PHASE12.cmd
curl.exe -fL "%BASE%/RESTORE-PROFILE-PHASE12.cmd" -o "RESTORE-PROFILE-PHASE12.cmd" || goto :fail

for %%F in (
 "tools\profile_phase12_local_offline.ps1"
 "BUILD-PROFILE-PHASE12-LOCAL-OFFLINE.cmd"
 "RESTORE-PROFILE-PHASE12.cmd"
) do (
 if not exist %%F (
   echo [ERRO] Arquivo ausente: %%F
   goto :fail
 )
)

echo.
echo ============================================================
echo  PHASE 12 FILES READY
echo ============================================================
echo Execute:
echo   BUILD-PROFILE-PHASE12-LOCAL-OFFLINE.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar a Phase 12.
echo.
pause
exit /b 1
