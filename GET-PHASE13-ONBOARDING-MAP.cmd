@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 13 Onboarding Map

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/2] profile_phase13_onboarding_map.ps1
curl.exe -fL "%BASE%/tools/profile_phase13_onboarding_map.ps1" -o "tools\profile_phase13_onboarding_map.ps1" || goto :fail

echo [2/2] RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd
curl.exe -fL "%BASE%/RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd" -o "RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd" || goto :fail

for %%F in (
 "tools\profile_phase13_onboarding_map.ps1"
 "RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd"
) do (
 if not exist %%F (
   echo [ERRO] Arquivo ausente: %%F
   goto :fail
 )
)

echo.
echo ============================================================
echo  PHASE 13 ONBOARDING MAPPER READY
echo ============================================================
echo Execute:
echo   RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar o mapper da Phase 13.
echo.
pause
exit /b 1
