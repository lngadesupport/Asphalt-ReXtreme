@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_race_hud_binding_catalog.py config\race-hud-bindings.verified.json CampaignRaceHudBindings.dat --report CampaignRaceHudBindings.report.json
  exit /b %errorlevel%
)
python tools\build_race_hud_binding_catalog.py config\race-hud-bindings.verified.json CampaignRaceHudBindings.dat --report CampaignRaceHudBindings.report.json
exit /b %errorlevel%
