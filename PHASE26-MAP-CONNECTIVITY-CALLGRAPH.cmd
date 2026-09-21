@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 26 Connectivity Callgraph

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase26_connectivity_callgraph.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 26 CONNECTIVITY CALLGRAPH
echo ============================================================
echo.
echo Esta fase NAO abre o jogo e NAO altera save/LocalState.
echo Ela sobe 2 niveis acima dos wrappers WinRT de conectividade
echo e tenta resolver RTTI/pointer-chain de AVAsphaltConnectivityTracker.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/245adb18e89cac632463eb6bffce142ced667ac0/tools/profile_phase26_connectivity_callgraph.ps1" ^
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
echo  PHASE 26 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE26_CONNECTIVITY_CALLGRAPH\LATEST-PHASE26-CONNECTIVITY-CALLGRAPH.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 26 falhou.
echo O save nao foi resetado.
pause
exit /b 1
