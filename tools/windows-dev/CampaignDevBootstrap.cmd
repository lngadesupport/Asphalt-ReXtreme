@echo off
setlocal
cd /d "%~dp0"

set "GAME_ROOT=%~1"
if "%GAME_ROOT%"=="" (
  if exist "%~dp0..\AppxManifest.xml" (
    set "GAME_ROOT=%~dp0.."
  ) else (
    echo Usage:
    echo   CampaignDevBootstrap.cmd "C:\path\to\extracted\Asphalt ReXtreme"
    echo.
    echo Or copy this tools folder into GAME_ROOT\_campaign_tools and run it there.
    pause
    exit /b 2
  )
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Register-CampaignDev.ps1" -GameRoot "%GAME_ROOT%"
if errorlevel 1 (
  echo.
  echo Registration failed. Read the error above.
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-CampaignDev.ps1" -GameRoot "%GAME_ROOT%" -CollectDiagnostics
echo.
echo Launch command sent. Diagnostic logs are under GAME_ROOT\_campaign_logs
pause
