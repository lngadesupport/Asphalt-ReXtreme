@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_campaign_challenge_catalog.py config\campaign_challenges.json CampaignChallenges.dat --report CampaignChallenges.report.json
  exit /b %errorlevel%
)
python tools\build_campaign_challenge_catalog.py config\campaign_challenges.json CampaignChallenges.dat --report CampaignChallenges.report.json
exit /b %errorlevel%
