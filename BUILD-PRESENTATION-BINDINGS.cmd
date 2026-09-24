@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_presentation_binding_catalog.py config\presentation-bindings.verified.json config\presentation-capabilities.verified.json CampaignPresentationBindings.dat --report CampaignPresentationBindings.report.json
  exit /b %errorlevel%
)
python tools\build_presentation_binding_catalog.py config\presentation-bindings.verified.json config\presentation-capabilities.verified.json CampaignPresentationBindings.dat --report CampaignPresentationBindings.report.json
exit /b %errorlevel%
