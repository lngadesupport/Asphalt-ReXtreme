@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 14 Connection UI Map

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 14 CONNECTION UI MAP
echo  Read-only: procura TODOS os erros de internet/conexao
echo ============================================================
echo.

if not exist "tools" mkdir "tools"

set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"
set "PS1=tools\profile_phase14_connection_ui_map.ps1"

echo [1/3] Baixando mapper Phase 14...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "%BASE%/tools/profile_phase14_connection_ui_map.ps1" ^
  -o "%PS1%.new"
if errorlevel 1 goto :fail

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 goto :fail

echo [2/3] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%CD%\%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [3/3] Mapeando somente UI/fluxos de conexao...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%CD%\%PS1%" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Phase 14 mapper falhou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PRONTO
echo ============================================================
echo.
echo Envie este arquivo:
echo   _PACKAGE_PHASE5\PROFILE-PHASE14-CONNECTION-UI-MAP.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar/executar o Phase 14 mapper.
echo.
pause
exit /b 1
