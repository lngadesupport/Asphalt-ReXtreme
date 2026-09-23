@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Build Campaign Production Data

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 10
)

echo Gerando CampaignCatalog.dat, CampaignEvents.dat e CampaignUpgrades.dat
echo diretamente de _PACKAGE_PHASE5\data\xml.bin...
echo.

python.exe tools\build_campaign_production_data.py --project-root "%CD%"
if errorlevel 1 (
  echo.
  echo [ERRO] Os catalogos de producao nao foram instalados.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  CAMPAIGN PRODUCTION DATA OK
echo ============================================================
echo.
echo Arquivos instalados em _PACKAGE_PHASE5:
echo   CampaignCatalog.dat
echo   CampaignEvents.dat
echo   CampaignUpgrades.dat
echo.
echo Auditoria:
echo   _CAMPAIGN_PRODUCTION_DATA\production-data-report.json
echo.
pause
