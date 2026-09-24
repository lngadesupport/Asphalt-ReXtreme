@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tools\build_campaign_achievement_catalog.py config\campaign_achievements.json CampaignAchievements.dat --report CampaignAchievements.report.json
  exit /b %errorlevel%
)
python tools\build_campaign_achievement_catalog.py config\campaign_achievements.json CampaignAchievements.dat --report CampaignAchievements.report.json
exit /b %errorlevel%
