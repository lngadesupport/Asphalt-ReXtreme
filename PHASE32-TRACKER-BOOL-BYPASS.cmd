@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 32 Tracker Bool Bypass

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase32_tracker_bool_bypass.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 32 TRACKER BOOL BYPASS
echo ============================================================
echo.
echo Forca o metodo virtual booleano do AVAsphaltConnectivityTracker
echo em 0x0098CF80 para TRUE.
echo.
echo IsOnline global continua FALSE.
echo Nao reseta save/LocalState.
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/608eec7533387841a2ece213a605f0a25c1feb95/tools/profile_phase32_tracker_bool_bypass.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando bypass...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 32 APLICADA
echo ============================================================
echo.
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Me diga apenas:
echo   - popup sumiu
echo   - popup mudou
echo   - continua igual
echo   - jogo travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 32 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
