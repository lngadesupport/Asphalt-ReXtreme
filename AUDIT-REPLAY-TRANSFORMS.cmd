@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-REPLAY-TRANSFORMS.cmd ^<AMS.exe^> [output.json]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=replay-transform-audit.json"
where py >nul 2>nul
if errorlevel 1 (
  python -m pip install capstone
  python tools\audit_replay_transform_bindings.py "%~1" --out "%OUT%"
  exit /b %errorlevel%
)
py -3 -m pip install capstone
py -3 tools\audit_replay_transform_bindings.py "%~1" --out "%OUT%"
exit /b %errorlevel%
