@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 11

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/3] profile_phase11_no_connection_errors.ps1
curl.exe -fL "%BASE%/tools/profile_phase11_no_connection_errors.ps1" -o "tools\profile_phase11_no_connection_errors.ps1" || goto :fail

echo [2/3] BUILD-PROFILE-PHASE11-NO-CONNECTION-ERRORS.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE11-NO-CONNECTION-ERRORS.cmd" -o "BUILD-PROFILE-PHASE11-NO-CONNECTION-ERRORS.cmd" || goto :fail

echo [3/3] RESTORE-PROFILE-PHASE11.cmd
curl.exe -fL "%BASE%/RESTORE-PROFILE-PHASE11.cmd" -o "RESTORE-PROFILE-PHASE11.cmd" || goto :fail

for %%F in (
  "tools\profile_phase11_no_connection_errors.ps1"
  "BUILD-PROFILE-PHASE11-NO-CONNECTION-ERRORS.cmd"
  "RESTORE-PROFILE-PHASE11.cmd"
) do (
  if not exist %%F (
    echo [ERRO] Arquivo ausente: %%F
    goto :fail
  )
)

echo.
echo ============================================================
echo  PHASE 11 FILES READY
echo ============================================================
echo Execute:
echo   BUILD-PROFILE-PHASE11-NO-CONNECTION-ERRORS.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar a Phase 11.
echo.
pause
exit /b 1
