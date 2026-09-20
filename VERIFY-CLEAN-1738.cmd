@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\verify_clean_1738.ps1" -SourceDir "%CD%"
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" pause
exit /b %RC%
