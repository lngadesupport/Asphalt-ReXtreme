@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_replay_binding_catalog.py config\replay-bindings.verified.json CampaignReplayBindings.dat --report CampaignReplayBindings.report.json
  exit /b %errorlevel%
)
python tools\build_replay_binding_catalog.py config\replay-bindings.verified.json CampaignReplayBindings.dat --report CampaignReplayBindings.report.json
exit /b %errorlevel%
