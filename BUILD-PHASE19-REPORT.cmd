@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
if not exist "%TOOLS%" mkdir "%TOOLS%"
curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/d139dca2e3934af8e8023d1001a6e97d4009b0a7/tools/build_phase19_report.ps1" -o "%TOOLS%\build_phase19_report.ps1"
if errorlevel 1 goto :fail
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%TOOLS%\build_phase19_report.ps1" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail
echo.
echo Envie:
echo _PACKAGE_PHASE5\_PHASE19_LOCAL_BACKEND_LOGS\LATEST-PHASE19-LOCAL-BACKEND-REPORT.txt
echo.
pause
exit /b 0
:fail
echo [ERRO] Falha ao gerar relatorio Phase 19.
pause
exit /b 1
