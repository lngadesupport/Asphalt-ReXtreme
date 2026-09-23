@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "PKG=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "POLICY=%ROOT%\config\campaign_economy.json"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 1
)

if not exist "%PKG%" (
  echo [ERRO] _PACKAGE_PHASE5 nao encontrado.
  pause
  exit /b 2
)

echo.
echo [1/3] Gerando CampaignCatalog.dat dos dados reais do pacote...
python.exe "%TOOLS%\build_campaign_vehicle_catalog_from_package.py" ^
  --package "%PKG%" ^
  --policy "%POLICY%" ^
  --output "%PKG%\CampaignCatalog.dat" ^
  --report "%PKG%\CampaignCatalog.report.json"
if errorlevel 1 goto :fail

echo.
echo [2/3] Gerando CampaignEvents.dat da carreira real...
python.exe "%TOOLS%\build_campaign_event_catalog_from_package.py" ^
  --package "%PKG%" ^
  --output "%PKG%\CampaignEvents.dat" ^
  --report "%PKG%\CampaignEvents.report.json"
if errorlevel 1 goto :fail

echo.
echo [3/3] Reconstruindo CampaignObjectives.dat da carreira real...
python.exe "%TOOLS%\build_campaign_objective_catalog_from_package.py" ^
  --package "%PKG%" ^
  --output "%PKG%\CampaignObjectives.dat" ^
  --report "%PKG%\CampaignObjectives.report.json"
if errorlevel 3 goto :objectives_need_map
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  CAMPAIGN DATA GERADO
echo ============================================================
echo.
echo CampaignCatalog.dat
echo CampaignEvents.dat
echo CampaignObjectives.dat
echo.
echo Relatorios:
echo _PACKAGE_PHASE5\CampaignCatalog.report.json
echo _PACKAGE_PHASE5\CampaignEvents.report.json
echo _PACKAGE_PHASE5\CampaignObjectives.report.json
echo.
pause
exit /b 0

:objectives_need_map
echo.
echo ============================================================
echo  OBJETIVOS PRECISAM DE MAPEAMENTO
echo ============================================================
echo.
echo O builder encontrou tipos/campos de objetivo que ainda nao
echo possuem equivalencia comprovada no Campaign Core.
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\CampaignObjectives.report.json
echo.
echo Nenhum CampaignObjectives.dat aproximado foi criado.
pause
exit /b 3

:fail
echo.
echo [ERRO] Falha ao gerar dados Campaign.
echo Nenhum catalogo invalido deve ser usado pelo runtime.
pause
exit /b 1
