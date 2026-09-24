@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%CD%"
set "SCRIPT=%ROOT%\tools\profile_phase46_craftcar_observer_map.ps1"
if not exist "%ROOT%\tools" mkdir "%ROOT%\tools"
curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f940e82f907b8dc18bb1660ab62799798c30c41c/tools/profile_phase46_craftcar_observer_map.ps1" -o "%SCRIPT%"
if errorlevel 1 goto fail
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto fail
echo.
echo PHASE 46 OK
echo Envie:
echo _PACKAGE_PHASE5\_PHASE46_BUILD_OBSERVER_MAP\LATEST-PHASE46-BUILD-OBSERVER-MAP.txt
pause
exit /b 0
:fail
echo Phase 46 falhou. Save nao foi resetado.
pause
exit /b 1
