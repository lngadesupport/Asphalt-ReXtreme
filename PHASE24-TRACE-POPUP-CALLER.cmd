@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 24 Popup Call Trace

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase24_popup_callsite_tripwire.ps1"
set "RUNNER=%TOOLS%\run_phase24_popup_call_trace.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 24 POPUP CALL TRACE
echo ============================================================
echo.
echo Arma todos os CALL rel32 diretos para 0x00870510.
echo Quando qualquer popup dessa familia for construido, o jogo
echo para/crasha no caller real e o tracer grava o endereco.
echo Depois AMS.exe e restaurado automaticamente.
echo.

echo [1/4] Baixando patcher...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/5052576ca8b9c1f4cbc374afa5fde43662a71039/tools/profile_phase24_popup_callsite_tripwire.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/4] Baixando tracer...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/5740ca7c1d3513723892eb4ae8d773239d0d09bf/tools/run_phase24_popup_call_trace.ps1" ^
  -o "%RUNNER%"
if errorlevel 1 goto :fail

echo [3/4] Validando scripts...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%PATCH%','%RUNNER%')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){Write-Host ('ERRO em '+$p) -ForegroundColor Red;$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo Instalando callsite traps...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :restore

echo.
echo [4/4] Iniciando jogo sob depurador...
echo O jogo deve parar/crashar no primeiro popup dessa familia.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%RUNNER%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :restore

echo.
echo ============================================================
echo  PHASE 24 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE24_POPUP_CALL_TRACE\LATEST-PHASE24-TRACE.txt
echo.
pause
exit /b 0

:restore
echo.
echo Tentando restaurar AMS.exe pre-Phase24...
if exist "%ROOT%\_PACKAGE_PHASE5\_PHASE24_POPUP_CALL_TRACE\AMS.PRE-CALL-TRAPS.exe" (
  copy /y "%ROOT%\_PACKAGE_PHASE5\_PHASE24_POPUP_CALL_TRACE\AMS.PRE-CALL-TRAPS.exe" "%ROOT%\_PACKAGE_PHASE5\AMS.exe" >nul
)
echo [ERRO] Phase 24 falhou, mas foi feita tentativa de restauracao.
echo O save nao foi resetado.
pause
exit /b 1

:fail
echo.
echo [ERRO] Falha ao preparar a Phase 24.
pause
exit /b 1
