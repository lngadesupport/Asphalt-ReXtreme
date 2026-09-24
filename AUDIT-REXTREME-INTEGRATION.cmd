@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: AUDIT-REXTREME-INTEGRATION.cmd ^<game-directory^> [output-directory]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=_TRACE_MONTAR\REXTREME-INTEGRATION-AUDIT"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 py -3 -m pip install capstone
  py -3 tools\audit_game_integration_bundle.py "%~1" --out-dir "%OUT%"
  exit /b %errorlevel%
)

python -c "import capstone" >nul 2>nul
if errorlevel 1 python -m pip install capstone
python tools\audit_game_integration_bundle.py "%~1" --out-dir "%OUT%"
exit /b %errorlevel%
