@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 25 Connectivity Map

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase25_connectivity_tracker_map.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 25 CONNECTIVITY MAP
echo ============================================================
echo.
echo Esta fase:
echo   - restaura AMS.exe pre-Phase24 com verificacao de hash
echo   - NAO abre o jogo
echo   - NAO altera save/LocalState
echo   - mapeia AVAsphaltConnectivityTracker
echo   - mapeia Windows.Networking.Connectivity
echo   - cruza essas funcoes com os CALLs diretos de IsOnline
echo.

echo Encerrando qualquer AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 2 /nobreak >nul

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/9107e9f9c56b9e72495b755cc847693190d26ab6/tools/profile_phase25_connectivity_tracker_map.ps1" ^
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
echo  PHASE 25 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE25_CONNECTIVITY_MAP\LATEST-PHASE25-CONNECTIVITY-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 25 falhou.
echo O save nao foi resetado.
pause
exit /b 1
