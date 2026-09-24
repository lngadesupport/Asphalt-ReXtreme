@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 9

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/3] profile_phase9_internal.ps1
curl.exe -fL "%BASE%/tools/profile_phase9_internal.ps1" -o "tools\profile_phase9_internal.ps1" || goto :fail

echo [2/3] BUILD-PROFILE-PHASE9-INTERNAL.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE9-INTERNAL.cmd" -o "BUILD-PROFILE-PHASE9-INTERNAL.cmd" || goto :fail

echo [3/3] RESTORE-PROFILE-PHASE9.cmd
curl.exe -fL "%BASE%/RESTORE-PROFILE-PHASE9.cmd" -o "RESTORE-PROFILE-PHASE9.cmd" || goto :fail

for %%F in (
 "tools\profile_phase9_internal.ps1"
 "BUILD-PROFILE-PHASE9-INTERNAL.cmd"
 "RESTORE-PROFILE-PHASE9.cmd"
) do (
 if not exist %%F (
   echo [ERRO] Arquivo ausente: %%F
   goto :fail
 )
)

echo.
echo ============================================================
echo  PHASE 9 FILES READY
echo ============================================================
echo Execute:
echo   BUILD-PROFILE-PHASE9-INTERNAL.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar a Phase 9.
echo.
pause
exit /b 1
