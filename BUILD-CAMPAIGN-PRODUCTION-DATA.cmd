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

echo Gerando dados autoritativos da Campaign Edition
echo diretamente de _PACKAGE_PHASE5\data\xml.bin...
echo.

python.exe tools\build_campaign_production_data.py --project-root "%CD%"
if errorlevel 1 (
  echo.
  echo [ERRO] Catalogos base de producao nao foram instalados.
  pause
  exit /b 1
)

python.exe tools\build_campaign_auxiliary_data.py ^
  --xml-bin "%CD%\_PACKAGE_PHASE5\data\xml.bin" ^
  --package-dir "%CD%\_PACKAGE_PHASE5" ^
  --report-dir "%CD%\_CAMPAIGN_PRODUCTION_DATA"
if errorlevel 3 (
  echo.
  echo [ERRO] Objetivos reais precisam de novo mapeamento.
  echo Consulte _CAMPAIGN_PRODUCTION_DATA\CampaignObjectives.report.json
  pause
  exit /b 3
)
if errorlevel 1 (
  echo.
  echo [ERRO] Falha nos catalogos auxiliares.
  pause
  exit /b 2
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
echo   CampaignObjectives.dat
if exist "_PACKAGE_PHASE5\CampaignUpgradeUiMap.dat" echo   CampaignUpgradeUiMap.dat
echo.
echo Auditoria:
echo   _CAMPAIGN_PRODUCTION_DATA\production-data-report.json
echo.
pause
