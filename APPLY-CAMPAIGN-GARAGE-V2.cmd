@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - CampaignGarage v2

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\campaign_garage_v2.py"
set "CORE=%ROOT%\prebuilt\campaign-core\IGPLib_x86.dll"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado.
  echo Use o pacote precompilado quando publicado ou instale Python 3.
  pause
  exit /b 1
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%ROOT%\prebuilt\campaign-core" mkdir "%ROOT%\prebuilt\campaign-core"

echo [1/3] Baixando CampaignGarage v2...
curl.exe -fL --retry 3 "%BASE%/tools/campaign_garage_v2.py" -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Baixando Campaign Core v2...
curl.exe -fL --retry 3 "%BASE%/prebuilt/campaign-core/IGPLib_x86.dll" -o "%CORE%"
if errorlevel 1 goto :fail

echo [3/3] Aplicando...
python.exe "%PATCH%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo CampaignGarage v2 aplicado.
echo Inicie com:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] CampaignGarage v2 nao foi aplicado.
echo Nenhum byte desconhecido e sobrescrito pelo patcher.
pause
exit /b 1
