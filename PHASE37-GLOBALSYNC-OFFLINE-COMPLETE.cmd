@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 37 GlobalSync Offline Complete

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase37_globalsync_offline_complete.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 37 GLOBALSYNC OFFLINE-COMPLETE
echo ============================================================
echo.
echo Conclui imediatamente requests GlobalSync com codigo 0
echo e pula o transporte online.
echo.
echo Mantem:
echo   - Phase36 GS_MessagePopup bypass
echo   - IsOnline global FALSE
echo   - save/LocalState intactos
echo.
echo Alvo principal:
echo   - compra/montagem de carro
echo   - pos-corrida
echo   - outras esperas GlobalSync equivalentes
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/fb8218ff51ac2a05401dfbc89f8fa99ca3059cb2/tools/profile_phase37_globalsync_offline_complete.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando GlobalSync offline-complete...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 37 APLICADA
echo ============================================================
echo.
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste primeiro a montagem/compra do carro.
echo Depois, se possivel, finalize uma corrida.
echo.
echo Informe:
echo   - compra concluiu ou continua carregando
echo   - pos-corrida voltou ao lobby ou continua carregando
echo   - travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 37 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
