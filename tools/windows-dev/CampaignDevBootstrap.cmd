@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Register-CampaignDev.ps1"
if errorlevel 1 (
  echo.
  echo Registration failed. Read the error above.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-CampaignDev.ps1" -CollectDiagnostics
echo.
echo Launch command sent. Diagnostic logs are under ..\_campaign_logs
pause
