@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 33 Connectivity State Machine

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase33_connectivity_state_machine.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 33 CONNECTIVITY STATE MACHINE
echo ============================================================
echo.
echo Analise focada do bloco de state machine/callback do
echo AVAsphaltConnectivityTracker.
echo.
echo Reverte automaticamente apenas o experimento da Phase 32.
echo Nao reseta save/LocalState.
echo Deve terminar muito rapido.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f8a11fe1c348d2bc1b2ae808c1dec5b93d24852e/tools/profile_phase33_connectivity_state_machine.ps1" ^
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
echo  PHASE 33 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE33_CONNECTIVITY_STATE_MACHINE\LATEST-PHASE33-CONNECTIVITY-STATE-MACHINE.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 33 falhou.
echo O save nao foi resetado.
pause
exit /b 1
