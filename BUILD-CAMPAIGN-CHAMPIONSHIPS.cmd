@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_campaign_championship_catalog.py config\campaign_championships.json CampaignChampionships.dat --event-catalog CampaignEvents.dat --report CampaignChampionships.report.json
  exit /b %errorlevel%
)
python tools\build_campaign_championship_catalog.py config\campaign_championships.json CampaignChampionships.dat --event-catalog CampaignEvents.dat --report CampaignChampionships.report.json
exit /b %errorlevel%
