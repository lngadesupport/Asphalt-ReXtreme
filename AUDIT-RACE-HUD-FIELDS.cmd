@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-RACE-HUD-FIELDS.cmd ^<AMS.exe^> --frame-audit ^<replay-frame-audit.json^>
  exit /b 2
)
where py >nul 2>nul
if errorlevel 1 (
  python -m pip install capstone
  python tools\audit_race_hud_fields.py %*
  exit /b %errorlevel%
)
py -3 -m pip install capstone
py -3 tools\audit_race_hud_fields.py %*
exit /b %errorlevel%
