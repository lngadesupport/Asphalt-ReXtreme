@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-ORIGINAL-SETTINGS-UI.cmd ^<game-directory^> [output.json]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=original-settings-ui-audit.json"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\audit_original_settings_ui.py "%~1" --out "%OUT%"
  exit /b %errorlevel%
)
python tools\audit_original_settings_ui.py "%~1" --out "%OUT%"
exit /b %errorlevel%
