@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme Local Backend Discovery

echo ============================================================
echo  ASPHALT ReXTREME - LOCAL BACKEND DISCOVERY
echo ============================================================
echo.
echo Esta etapa NAO altera hosts/DNS do Windows.
echo Ela descobre URLs, dominios, DNS e conexoes do jogo,
echo enquanto deixa o backend local escutando em:
echo   127.0.0.1:80, 443, 8080, 8443
echo.

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GAME=%ROOT%\_PACKAGE_PHASE5"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado em:
  echo   %GAME%
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/5] Baixando servidor local...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c9a78cf14439890ef80b471b147c6eae5f36964a/tools/rextreme_local_backend.ps1" ^
  -o "%TOOLS%\rextreme_local_backend.ps1"
if errorlevel 1 goto :fail

echo [2/5] Baixando scanner de endpoints...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f97fd07f439438a7f876ba816d28f49886d5316f/tools/scan_backend_endpoints.ps1" ^
  -o "%TOOLS%\scan_backend_endpoints.ps1"
if errorlevel 1 goto :fail

echo [3/5] Baixando orquestrador...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/314696cb63431f6fc2f0e9503d08aa111eaabde0/tools/run_local_backend_discovery.ps1" ^
  -o "%TOOLS%\run_local_backend_discovery.ps1"
if errorlevel 1 goto :fail

echo [4/5] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%TOOLS%\rextreme_local_backend.ps1','%TOOLS%\scan_backend_endpoints.ps1','%TOOLS%\run_local_backend_discovery.ps1')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){Write-Host ('ERRO em '+$p) -ForegroundColor Red;$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [5/5] Iniciando descoberta + backend local...
echo.
echo Deixe esta janela aberta.
echo Quando o jogo chegar ao lobby e aparecer SEM CONEXAO,
echo feche o jogo completamente para finalizar o ZIP.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%TOOLS%\run_local_backend_discovery.ps1" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Discovery terminou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PRONTO
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_LOCAL_BACKEND_DISCOVERY\LATEST-LOCAL-BACKEND-DISCOVERY.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar o backend discovery.
pause
exit /b 1
