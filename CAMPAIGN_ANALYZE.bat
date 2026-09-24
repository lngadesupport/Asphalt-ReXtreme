@echo off
setlocal
cd /d "%~dp0"

set "SOURCE=%~1"
if "%SOURCE%"=="" set "SOURCE=%CD%"

echo ============================================================
echo Asphalt ReXtreme - Campaign Edition Analyzer
echo ============================================================
echo.
echo Source RAR directory:
echo %SOURCE%
echo.
echo This tool does NOT install/register APPX, open Microsoft Store,
echo launch the game, or change Windows package policies.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\prepare_campaign_source.ps1" -SourceDir "%SOURCE%" -RunAudit
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo Campaign analysis failed with exit code %ERR%.
  pause
  exit /b %ERR%
)

echo Campaign analysis finished successfully.
pause
exit /b 0
