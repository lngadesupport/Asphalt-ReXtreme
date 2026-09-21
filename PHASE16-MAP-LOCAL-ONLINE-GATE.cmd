@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Phase 16 Local Online Gate Map

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 16 LOCAL ONLINE GATE MAP
echo  Read-only: procura chamadas locais ao IsOnline
echo ============================================================
echo.

if not exist "tools" mkdir "tools"
set "PAYLOADCOMMIT=42abf3d0a46d08196701667525bc04a9260c3b91"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/%PAYLOADCOMMIT%"
set "PS1=tools\profile_phase16_local_online_gate_map.ps1"

echo [1/3] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "%BASE%/tools/profile_phase16_local_online_gate_map.ps1" ^
  -o "%PS1%.new"
if errorlevel 1 goto :fail

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 goto :fail

echo [2/3] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%CD%\%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [3/3] Localizando chamadas ao IsOnline...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%CD%\%PS1%" ^
  -ProjectRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Phase 16 falhou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PRONTO
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\PROFILE-PHASE16-LOCAL-ONLINE-GATE-MAP.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar/executar a Phase 16.
pause
exit /b 1
