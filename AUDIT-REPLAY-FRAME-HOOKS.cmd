@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-REPLAY-FRAME-HOOKS.cmd ^<path-to-AMS.exe^> [output.json]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=replay-frame-hook-audit.json"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 py -3 -m pip install capstone
  py -3 tools\audit_replay_frame_hooks.py "%~1" --out "%OUT%"
  exit /b %errorlevel%
)

python -c "import capstone" >nul 2>nul
if errorlevel 1 python -m pip install capstone
python tools\audit_replay_frame_hooks.py "%~1" --out "%OUT%"
exit /b %errorlevel%
