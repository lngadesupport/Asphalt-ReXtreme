@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 23 Popup Trace All Copies

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase23_popup_tripwire_all_copies.ps1"
set "RUNNER=%TOOLS%\run_phase23_popup_trace.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 23 POPUP TRACE ALL COPIES
echo ============================================================
echo.
echo Arma as DUAS copias conhecidas de TITLE e DESCRIPTION
echo do popup NO_INTERNET.
echo Quando uma delas for usada, o jogo para/crasha e o tracer
echo registra o callsite real. Depois restaura AMS.exe.
echo.

echo [1/4] Baixando tripwire patcher...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3dd2b4add099d730190832b6638d60fcd4de2c60/tools/profile_phase23_popup_tripwire_all_copies.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/4] Baixando debugger runner...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3a3992f05d85d3e67f69a0fa2c72e8a4916ec21e/tools/run_phase23_popup_trace.ps1" ^
  -o "%RUNNER%"
if errorlevel 1 goto :fail

echo [3/4] Validando scripts...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%PATCH%','%RUNNER%')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){Write-Host ('ERRO em '+$p) -ForegroundColor Red;$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo Instalando tripwires...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :restore

echo.
echo [4/4] Iniciando jogo sob depurador...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%RUNNER%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :restore

echo.
echo ============================================================
echo  PHASE 23 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE23_POPUP_TRACE\LATEST-PHASE23-TRACE.txt
echo.
pause
exit /b 0

:restore
echo.
echo Tentando restaurar AMS.exe pre-Phase23...
if exist "%ROOT%\_PACKAGE_PHASE5\_PHASE23_POPUP_TRACE\AMS.PRE-TRAPS.exe" (
  copy /y "%ROOT%\_PACKAGE_PHASE5\_PHASE23_POPUP_TRACE\AMS.PRE-TRAPS.exe" "%ROOT%\_PACKAGE_PHASE5\AMS.exe" >nul
)
echo [ERRO] Phase 23 falhou, mas foi feita tentativa de restauracao.
pause
exit /b 1

:fail
echo.
echo [ERRO] Falha ao preparar a Phase 23.
pause
exit /b 1
