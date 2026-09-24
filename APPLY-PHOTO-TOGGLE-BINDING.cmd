@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: APPLY-PHOTO-TOGGLE-BINDING.cmd ^<path-to-AMS.exe^>
  exit /b 2
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 py -3 -m pip install capstone
  py -3 tools\apply_photo_toggle_binding.py "%~1" --project-root "%CD%"
  exit /b %errorlevel%
)
python -c "import capstone" >nul 2>nul
if errorlevel 1 python -m pip install capstone
python tools\apply_photo_toggle_binding.py "%~1" --project-root "%CD%"
exit /b %errorlevel%
