@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-PRESENTATION-CAPABILITIES.cmd ^<game-dir-or-AMS.exe^> [output.json]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=presentation-capability-audit.json"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\audit_presentation_capabilities.py "%~1" --out "%OUT%"
  exit /b %errorlevel%
)
python tools\audit_presentation_capabilities.py "%~1" --out "%OUT%"
exit /b %errorlevel%
