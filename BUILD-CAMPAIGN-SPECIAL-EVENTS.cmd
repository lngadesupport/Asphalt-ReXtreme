@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: BUILD-CAMPAIGN-SPECIAL-EVENTS.cmd ^<CampaignEvents.dat^> [output.dat]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=CampaignSpecialEvents.dat"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_campaign_special_event_catalog.py config\campaign_special_events.json "%OUT%" --event-catalog "%~1" --report CampaignSpecialEvents.report.json
  exit /b %errorlevel%
)
python tools\build_campaign_special_event_catalog.py config\campaign_special_events.json "%OUT%" --event-catalog "%~1" --report CampaignSpecialEvents.report.json
exit /b %errorlevel%
