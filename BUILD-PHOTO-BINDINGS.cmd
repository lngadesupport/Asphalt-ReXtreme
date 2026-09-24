@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_photo_binding_catalog.py config\photo-bindings.verified.json CampaignPhotoBindings.dat --report CampaignPhotoBindings.report.json
  exit /b %errorlevel%
)
python tools\build_photo_binding_catalog.py config\photo-bindings.verified.json CampaignPhotoBindings.dat --report CampaignPhotoBindings.report.json
exit /b %errorlevel%
