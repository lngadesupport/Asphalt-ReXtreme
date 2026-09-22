@echo off
cd /d "%~dp0"
if not exist tools mkdir tools
curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3af9e7d41169ac72bf8214613546829849878d68/tools/profile_phase51_build_button_active.ps1" -o "tools\profile_phase51_build_button_active.ps1"
if errorlevel 1 goto fail
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "tools\profile_phase51_build_button_active.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto fail
echo.
echo PHASE 51 OK
pause
exit /b 0
:fail
echo.
echo PHASE 51 FALHOU
pause
exit /b 1
