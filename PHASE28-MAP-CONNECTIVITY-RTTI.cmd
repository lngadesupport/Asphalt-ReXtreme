@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 28 Connectivity RTTI

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase28_connectivity_rtti.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 28 CONNECTIVITY RTTI
echo ============================================================
echo.
echo Resolve o RTTI real de AVAsphaltConnectivityTracker:
echo   TypeDescriptor -> CompleteObjectLocator -> vftable -> metodos
echo.
echo Tambem marca metodos que chamam wrappers WinRT/IsOnline.
echo Phase27 e normalizada para o codigo original antes da analise.
echo Nao abre o jogo e nao altera save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/28ea54a217e08ded6b4f458688c6dc6e51af6ab6/tools/profile_phase28_connectivity_rtti.ps1" ^
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
echo  PHASE 28 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE28_CONNECTIVITY_RTTI\LATEST-PHASE28-CONNECTIVITY-RTTI.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 28 falhou.
echo O save nao foi resetado.
pause
exit /b 1
