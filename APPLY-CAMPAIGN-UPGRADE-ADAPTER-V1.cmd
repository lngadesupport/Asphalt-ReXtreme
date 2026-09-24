@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Campaign Upgrade Adapter v1

set "ROOT=%CD%"
set "PKG=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\campaign_upgrade_adapter_v1.py"
set "CORE=%ROOT%\prebuilt\campaign-core\IGPLib_x86.dll"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 1
)

if not exist "%PKG%\CampaignUpgrades.dat" (
  echo [ERRO] CampaignUpgrades.dat ausente.
  echo O adapter nao usa precos/levels antigos como fallback.
  pause
  exit /b 2
)

if not exist "%PKG%\CampaignUpgradeUiMap.dat" (
  echo [ERRO] CampaignUpgradeUiMap.dat ausente.
  echo O adapter nao adivinha o slot de upgrade.
  pause
  exit /b 3
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%ROOT%\prebuilt\campaign-core" mkdir "%ROOT%\prebuilt\campaign-core"

echo ============================================================
echo  CAMPAIGN UPGRADE ADAPTER V1
echo ============================================================
echo.
echo UpgradeCarRequestImpl deixa de ser criado pela acao da UI.
echo Precos, saldo e level: Campaign Core.
echo UI visual: preservada.
echo.

echo [1/3] Baixando patcher...
curl.exe -fL --retry 3 "%BASE%/tools/campaign_upgrade_adapter_v1.py" -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Baixando Campaign Core atual...
curl.exe -fL --retry 3 "%BASE%/prebuilt/campaign-core/IGPLib_x86.dll" -o "%CORE%"
if errorlevel 1 goto :fail

echo [3/3] Aplicando...
python.exe "%PATCH%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo Campaign Upgrade Adapter v1 aplicado.
echo Relatorio:
echo   _TRACE_MONTAR\CAMPAIGN-UPGRADE-ADAPTER-V1.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Upgrade Adapter v1 nao foi aplicado.
echo Bytes desconhecidos e catalogos ausentes nunca sao forçados.
pause
exit /b 1
