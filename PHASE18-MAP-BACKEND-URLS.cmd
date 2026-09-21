@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 18 Backend URL Map

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PS1=%TOOLS%\profile_phase18_backend_url_map.ps1"

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/3] Baixando mapper Phase 18...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/89d30df34d08fc34bd13e545a73565bae33ac562/tools/profile_phase18_backend_url_map.ps1" ^
  -o "%PS1%.new"
if errorlevel 1 goto :fail

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 goto :fail

echo [2/3] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [3/3] Mapeando URLs de backend...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Phase 18 falhou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PRONTO
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\PROFILE-PHASE18-BACKEND-URL-MAP.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar/executar a Phase 18.
pause
exit /b 1
