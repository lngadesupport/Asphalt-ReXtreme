@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 45 Build Callback Map

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase45_build_callback_map.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 45 BUILD CALLBACK/UI MAP
echo ============================================================
echo.
echo Esta fase:
echo   - reverte a Phase42 (falhou)
echo   - volta ao estado Phase36-only
echo   - mapeia +0x298 callback
echo   - mapeia +0x35C UI
echo   - cruza com +0x3AC/+0x3B0 pending
echo.
echo Nao aplica novo bypass.
echo Nao reseta save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/67079bf904ef32da0941665cb2ed3a07b65aadee/tools/profile_phase45_build_callback_map.ps1" ^
  -o "%SCRIPT%"
if errorlevel 1 goto :fail

echo [2/2] Validando e executando...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%SCRIPT%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%SCRIPT%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 45 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE45_BUILD_CALLBACK_MAP\LATEST-PHASE45-BUILD-CALLBACK-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 45 falhou.
echo O save nao foi resetado.
pause
exit /b 1
