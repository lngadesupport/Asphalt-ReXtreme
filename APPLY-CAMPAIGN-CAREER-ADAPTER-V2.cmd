@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Campaign Career Adapter v2

set "ROOT=%CD%"
set "PKG=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\campaign_career_adapter_v2.py"
set "CORE=%ROOT%\prebuilt\campaign-core\IGPLib_x86.dll"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 1
)

if not exist "%PKG%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 2
)
if not exist "%PKG%\CampaignEvents.dat" (
  echo [ERRO] CampaignEvents.dat ausente.
  echo Execute BUILD-CAMPAIGN-DATA.cmd primeiro.
  pause
  exit /b 3
)
if not exist "%PKG%\CampaignObjectives.dat" (
  echo [ERRO] CampaignObjectives.dat ausente.
  echo Execute BUILD-CAMPAIGN-DATA.cmd primeiro.
  pause
  exit /b 4
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%ROOT%\prebuilt\campaign-core" mkdir "%ROOT%\prebuilt\campaign-core"

echo ============================================================
echo  CAMPAIGN CAREER ADAPTER V2
echo ============================================================
echo.
echo - PreCareerEventRequest remoto sera aposentado
echo - PostCareerEventRequest remoto sera aposentado
echo - resultados/recompensas: Campaign Core
echo - UI de carreira: preservada
echo.

echo [1/3] Baixando patcher...
curl.exe -fL --retry 3 "%BASE%/tools/campaign_career_adapter_v2.py" -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Baixando Campaign Core atual...
curl.exe -fL --retry 3 "%BASE%/prebuilt/campaign-core/IGPLib_x86.dll" -o "%CORE%"
if errorlevel 1 goto :fail

echo [3/3] Aplicando Career Adapter v2...
python.exe "%PATCH%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  CAREER ADAPTER V2 APLICADO
echo ============================================================
echo.
echo Relatorio:
echo   _TRACE_MONTAR\CAMPAIGN-CAREER-ADAPTER-V2.json
echo.
echo Inicie:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Career Adapter v2 nao foi aplicado.
echo O patcher recusa bytes desconhecidos/parciais.
pause
exit /b 1
