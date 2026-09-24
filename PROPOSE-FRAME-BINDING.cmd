@echo off
setlocal
cd /d "%~dp0"
if "%~4"=="" (
  echo Usage: PROPOSE-FRAME-BINDING.cmd ^<audit.json^> ^<AMS.exe^> ^<method-va^> ^<replay^|photo^> [output.json]
  exit /b 2
)
set "OUT=%~5"
if "%OUT%"=="" set "OUT=%~4-frame-binding.review.json"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\propose_frame_binding.py "%~1" "%~2" --method-va "%~3" --kind "%~4" --out "%OUT%"
  exit /b %errorlevel%
)
python tools\propose_frame_binding.py "%~1" "%~2" --method-va "%~3" --kind "%~4" --out "%OUT%"
exit /b %errorlevel%
