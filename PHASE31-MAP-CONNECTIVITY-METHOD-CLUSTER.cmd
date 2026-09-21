@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 31 Connectivity Method Cluster

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase31_connectivity_method_cluster.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 31 CONNECTIVITY METHOD CLUSTER
echo ============================================================
echo.
echo Mapeia os metodos chamados diretamente pelo singleton
echo AVAsphaltConnectivityTracker e seus principais callsites.
echo Nao abre o jogo e nao altera save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/a1bf08843eacc66086ef2de10b2e444d4d7629c9/tools/profile_phase31_connectivity_method_cluster.ps1" ^
  -o "%SCRIPT%"
if errorlevel 1 goto :fail

echo [2/2] Validando e executando...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%SCRIPT%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%SCRIPT%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 31 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE31_CONNECTIVITY_METHOD_CLUSTER\LATEST-PHASE31-CONNECTIVITY-METHOD-CLUSTER.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 31 falhou.
echo O save nao foi resetado.
pause
exit /b 1
