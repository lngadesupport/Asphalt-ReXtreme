@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 30 Connectivity Singleton

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase30_connectivity_singleton.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 30 CONNECTIVITY SINGLETON - FAST
echo ============================================================
echo.
echo Segue o singleton global real de AVAsphaltConnectivityTracker:
echo   0x0193A56C
echo.
echo Mapeia quem le/escreve o objeto, callers dessas funcoes
echo e acessos exatos ao campo booleano +0x5C.
echo.
echo Nao abre o jogo e nao altera save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3dad22bdadb274eee5a1797b36be4c6a0939d136/tools/profile_phase30_connectivity_singleton.ps1" ^
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
echo  PHASE 30 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE30_CONNECTIVITY_SINGLETON\LATEST-PHASE30-CONNECTIVITY-SINGLETON.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 30 falhou.
echo O save nao foi resetado.
pause
exit /b 1
