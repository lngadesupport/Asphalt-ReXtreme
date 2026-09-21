@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Build Backend Discovery Report

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PS1=%TOOLS%\build_backend_discovery_report.ps1"

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/3] Baixando consolidador...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/158bbc95ebb6f72f6c542dc1574af51098d41605/tools/build_backend_discovery_report.ps1" ^
  -o "%PS1%.new"
if errorlevel 1 goto :fail

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 goto :fail

echo [2/3] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [3/3] Gerando relatorio unico...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Falhou com codigo %RC%.
  pause
  exit /b %RC%
)

echo Envie este unico arquivo:
echo   _PACKAGE_PHASE5\_LOCAL_BACKEND_DISCOVERY\LATEST-LOCAL-BACKEND-DISCOVERY-REPORT.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar o consolidador.
pause
exit /b 1
