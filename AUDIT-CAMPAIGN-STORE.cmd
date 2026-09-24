@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Audit Campaign Store

set "ROOT=%CD%"
set "PKG=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "AUDIT=%TOOLS%\audit_campaign_store_keys_from_package.py"
set "REPORT=%PKG%\CampaignStoreKeys.report.json"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

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

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/2] Baixando auditor atual...
curl.exe -fL --retry 3 "%BASE%/tools/audit_campaign_store_keys_from_package.py" -o "%AUDIT%"
if errorlevel 1 goto :fail

echo [2/2] Auditando chaves locais de compra...
python.exe "%AUDIT%" --package "%PKG%" --report "%REPORT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  AUDITORIA DA LOJA CONCLUIDA
echo ============================================================
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\CampaignStoreKeys.report.json
echo.
echo Este comando NAO altera a economia e NAO cria ofertas aproximadas.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Auditoria da loja falhou.
pause
exit /b 1
