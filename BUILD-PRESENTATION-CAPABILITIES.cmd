@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_presentation_capability_catalog.py config\presentation-capabilities.verified.json CampaignPresentationOptions.dat --report CampaignPresentationOptions.report.json
  exit /b %errorlevel%
)
python tools\build_presentation_capability_catalog.py config\presentation-capabilities.verified.json CampaignPresentationOptions.dat --report CampaignPresentationOptions.report.json
exit /b %errorlevel%
