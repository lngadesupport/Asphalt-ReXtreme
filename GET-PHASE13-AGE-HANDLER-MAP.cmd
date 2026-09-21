@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Get Phase 13 Age Handler Focus

if not exist "tools" mkdir "tools"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/2] Baixando tracer focal da Phase 13...
curl.exe -fL "%BASE%/tools/profile_phase13_age_handler_map.ps1" -o "tools\profile_phase13_age_handler_map.ps1" || goto :fail

echo [2/2] Baixando launcher...
curl.exe -fL "%BASE%/RUN-PROFILE-PHASE13-AGE-HANDLER-MAP.cmd" -o "RUN-PROFILE-PHASE13-AGE-HANDLER-MAP.cmd" || goto :fail

echo.
echo Phase 13 focus ready.
echo Execute:
echo   RUN-PROFILE-PHASE13-AGE-HANDLER-MAP.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar o tracer focal da Phase 13.
echo.
pause
exit /b 1
