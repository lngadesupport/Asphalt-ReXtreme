@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: RANK-ORIGINAL-UI-CANDIDATES.cmd ^<original-settings-ui-audit.json^> [output.json]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=original-ui-candidate-ranking.json"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\rank_original_ui_candidates.py "%~1" --out "%OUT%"
  exit /b %errorlevel%
)
python tools\rank_original_ui_candidates.py "%~1" --out "%OUT%"
exit /b %errorlevel%
