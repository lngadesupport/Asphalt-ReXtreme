@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - FINALIZE Campaign Edition

set "ROOT=%CD%"
set "PKG=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "PRE=%ROOT%\prebuilt\campaign-core"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

if not exist "%PKG%\AMS.exe" (
  echo [ERRO] _PACKAGE_PHASE5\AMS.exe nao encontrado.
  pause
  exit /b 10
)
where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 11
)
where curl.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] curl.exe nao encontrado.
  pause
  exit /b 12
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%PRE%" mkdir "%PRE%"
if not exist "%ROOT%\_TRACE_MONTAR" mkdir "%ROOT%\_TRACE_MONTAR"

echo ============================================================
echo  ASPHALT REXTREME - CAMPAIGN EDITION FINALIZER
echo ============================================================
echo.
echo Este processo nao usa R17/R18/R19/Phase39/Phase48.
echo Core: x86 /NOENTRY / sem CRT.
echo.

call :get tools/xtea_assets.py tools\xtea_assets.py || goto :download_fail
call :get tools/rextreme_economy.py tools\rextreme_economy.py || goto :download_fail
call :get tools/economy_audit.py tools\economy_audit.py || goto :download_fail
call :get tools/build_campaign_vehicle_catalog.py tools\build_campaign_vehicle_catalog.py || goto :download_fail
call :get tools/build_campaign_event_catalog.py tools\build_campaign_event_catalog.py || goto :download_fail
call :get tools/build_campaign_upgrade_catalog.py tools\build_campaign_upgrade_catalog.py || goto :download_fail
call :get tools/build_campaign_objective_catalog.py tools\build_campaign_objective_catalog.py || goto :download_fail
call :get tools/build_campaign_objective_catalog_from_package.py tools\build_campaign_objective_catalog_from_package.py || goto :download_fail
call :get tools/build_campaign_upgrade_ui_map.py tools\build_campaign_upgrade_ui_map.py || goto :download_fail
call :get tools/build_campaign_production_data.py tools\build_campaign_production_data.py || goto :download_fail
call :get tools/build_campaign_auxiliary_data.py tools\build_campaign_auxiliary_data.py || goto :download_fail
call :get tools/build_campaign_store_catalog.py tools\build_campaign_store_catalog.py || goto :download_fail
call :get tools/build_campaign_store_from_shop.py tools\build_campaign_store_from_shop.py || goto :download_fail
call :get tools/audit_campaign_store_keys_from_package.py tools\audit_campaign_store_keys_from_package.py || goto :download_fail
call :get tools/campaign_garage_v2.py tools\campaign_garage_v2.py || goto :download_fail
call :get tools/campaign_career_adapter_v2.py tools\campaign_career_adapter_v2.py || goto :download_fail
call :get tools/campaign_upgrade_adapter_v1.py tools\campaign_upgrade_adapter_v1.py || goto :download_fail
call :get tools/campaign_store_adapter_v1.py tools\campaign_store_adapter_v1.py || goto :download_fail
call :get tools/validate_campaign_final.py tools\validate_campaign_final.py || goto :download_fail

echo [CORE] Baixando Campaign Core atual...
curl.exe -fL --retry 3 "%BASE%/prebuilt/campaign-core/IGPLib_x86.dll" -o "%PRE%\IGPLib_x86.dll"
if errorlevel 1 goto :download_fail

taskkill /F /IM AMS.exe >nul 2>nul
del /q "%PKG%\ReXtremeLocalRuntime.dll" 2>nul

echo.
echo [DATA 1/2] Gerando carros, eventos e upgrades de producao...
python.exe "%TOOLS%\build_campaign_production_data.py" --project-root "%ROOT%"
if errorlevel 1 goto :data_fail

echo.
echo [DATA 2/2] Gerando objetivos + mapa visual de upgrade...
python.exe "%TOOLS%\build_campaign_auxiliary_data.py" ^
  --xml-bin "%PKG%\data\xml.bin" ^
  --package-dir "%PKG%" ^
  --report-dir "%ROOT%\_CAMPAIGN_PRODUCTION_DATA"
set "AUXERR=%ERRORLEVEL%"
if %AUXERR% GEQ 3 (
  echo [BLOQUEIO] Objetivos possuem tipos ainda nao mapeados.
  goto :data_fail
)
if errorlevel 1 goto :data_fail

echo.
echo [STORE] Auditando chaves da loja legada...
python.exe "%TOOLS%\audit_campaign_store_keys_from_package.py" ^
  --package "%PKG%" ^
  --report "%ROOT%\_CAMPAIGN_PRODUCTION_DATA\CampaignStoreKeys.report.json"
if errorlevel 1 echo [AVISO] Auditoria de chaves da loja falhou; monetizacao ainda sera aposentada.

echo.
echo [STORE] Gerando CampaignStore.dat do asphaltshop.xtea real...
del /q "%PKG%\CampaignStore.dat" 2>nul
python.exe "%TOOLS%\build_campaign_store_from_shop.py" ^
  --xml-bin "%PKG%\data\xml.bin" ^
  --output "%PKG%\CampaignStore.dat" ^
  --report "%ROOT%\_CAMPAIGN_PRODUCTION_DATA\CampaignStore.report.json" ^
  --multiplier 0.20
set "STOREERR=%ERRORLEVEL%"
if "%STOREERR%"=="3" (
  echo [BLOQUEIO] Houve colisao entre chaves reais de ofertas.
  goto :data_fail
)
if "%STOREERR%"=="4" (
  echo [AVISO] Nenhuma oferta local verificavel foi encontrada.
  echo [AVISO] A monetizacao antiga sera aposentada sem loja local ativa.
  >"%ROOT%\_CAMPAIGN_PRODUCTION_DATA\store-offline.json" echo {"schema":1,"offers":[]}
  python.exe "%TOOLS%\build_campaign_store_catalog.py" ^
    "%ROOT%\_CAMPAIGN_PRODUCTION_DATA\store-offline.json" ^
    -o "%PKG%\CampaignStore.dat"
  if errorlevel 1 goto :data_fail
) else (
  if not "%STOREERR%"=="0" goto :data_fail
)

echo.
echo [PATCH 1/4] Garagem / ownership / MONTAR...
python.exe "%TOOLS%\campaign_garage_v2.py" --project-root "%ROOT%"
if errorlevel 1 goto :patch_fail

echo.
echo [PATCH 2/4] Carreira / corrida / recompensas...
python.exe "%TOOLS%\campaign_career_adapter_v2.py" --project-root "%ROOT%"
if errorlevel 1 goto :patch_fail

echo.
echo [PATCH 3/4] Upgrades / Pro-Kits...
if exist "%PKG%\CampaignUpgradeUiMap.dat" (
  python.exe "%TOOLS%\campaign_upgrade_adapter_v1.py" --project-root "%ROOT%"
  if errorlevel 1 goto :patch_fail
) else (
  echo [BLOQUEIO] CampaignUpgradeUiMap.dat nao foi reconstruido.
  goto :data_fail
)

echo.
echo [PATCH 4/4] Loja online -> CampaignStore local...
python.exe "%TOOLS%\campaign_store_adapter_v1.py" --project-root "%ROOT%"
if errorlevel 1 goto :patch_fail

echo.
echo [VALIDATE] Validando Campaign Edition...
python.exe "%TOOLS%\validate_campaign_final.py" ^
  --project-root "%ROOT%" ^
  --output "%ROOT%\_TRACE_MONTAR\CAMPAIGN-FINAL-STATUS.json" ^
  --require-complete
set "VALERR=%ERRORLEVEL%"

echo.
echo ============================================================
echo  FINALIZACAO CONCLUIDA
echo ============================================================
echo.
echo Status:
echo   _TRACE_MONTAR\CAMPAIGN-FINAL-STATUS.json
echo.
echo Dados:
echo   _CAMPAIGN_PRODUCTION_DATA
echo.
echo Inicie:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
if not "%VALERR%"=="0" (
  echo BLOQUEIO: a reconstrucao literal ainda nao esta completa.
  echo Consulte CAMPAIGN-FINAL-STATUS.json para o subsistema exato.
)
pause
exit /b %VALERR%

:get
curl.exe -fL --retry 3 "%BASE%/%~1" -o "%ROOT%\%~2"
exit /b %ERRORLEVEL%

:download_fail
echo.
echo [ERRO] Falha ao baixar os componentes atuais.
pause
exit /b 20

:data_fail
echo.
echo [ERRO] Falha/bloqueio ao reconstruir os dados Campaign.
echo Verifique _CAMPAIGN_PRODUCTION_DATA.
pause
exit /b 21

:patch_fail
echo.
echo [ERRO] Um patch guardado recusou o AMS atual.
echo Nenhum byte desconhecido foi forçado.
pause
exit /b 22
