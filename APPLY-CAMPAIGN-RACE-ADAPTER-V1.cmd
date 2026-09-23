@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Asphalt ReXtreme - Campaign Race Adapter v1

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\campaign_race_adapter_v1.py"
set "CORE=%ROOT%\prebuilt\campaign-core\IGPLib_x86.dll"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 1
)

if not exist "%ROOT%\_PACKAGE_PHASE5\CampaignEvents.dat" (
  echo [ERRO] CampaignEvents.dat ausente.
  pause
  exit /b 2
)
if not exist "%ROOT%\_PACKAGE_PHASE5\CampaignObjectives.dat" (
  echo [ERRO] CampaignObjectives.dat ausente.
  echo O adapter nao sera aplicado sem objetivos Campaign autoritativos.
  pause
  exit /b 3
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%ROOT%\prebuilt\campaign-core" mkdir "%ROOT%\prebuilt\campaign-core"

echo [1/3] Baixando patcher...
curl.exe -fL --retry 3 "%BASE%/tools/campaign_race_adapter_v1.py" -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Baixando Campaign Core...
curl.exe -fL --retry 3 "%BASE%/prebuilt/campaign-core/IGPLib_x86.dll" -o "%CORE%"
if errorlevel 1 goto :fail

echo [3/3] Aplicando BEGIN/FINISH...
python.exe "%PATCH%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo Campaign Race Adapter v1 aplicado.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Adapter nao aplicado.
pause
exit /b 1
