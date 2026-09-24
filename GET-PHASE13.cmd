@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 13 Local Onboarding

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/3] profile_phase13_local_onboarding.ps1
curl.exe -fL "%BASE%/tools/profile_phase13_local_onboarding.ps1" -o "tools\profile_phase13_local_onboarding.ps1" || goto :fail

echo [2/3] BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd" -o "BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd" || goto :fail

echo [3/3] RESTORE-PROFILE-PHASE13.cmd
curl.exe -fL "%BASE%/RESTORE-PROFILE-PHASE13.cmd" -o "RESTORE-PROFILE-PHASE13.cmd" || goto :fail

for %%F in (
 "tools\profile_phase13_local_onboarding.ps1"
 "BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd"
 "RESTORE-PROFILE-PHASE13.cmd"
) do (
 if not exist %%F (
   echo [ERRO] Arquivo ausente: %%F
   goto :fail
 )
)

echo.
echo ============================================================
echo  PHASE 13 FILES READY
echo ============================================================
echo Execute:
echo   BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar a Phase 13.
echo.
pause
exit /b 1
