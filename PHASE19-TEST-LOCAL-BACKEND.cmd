@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 19 Local Backend Test

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase19_local_backend_route.ps1"
set "RUNNER=%TOOLS%\run_phase19_local_backend.ps1"
set "BACKEND=%TOOLS%\rextreme_local_backend.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 19 LOCAL BACKEND
echo ============================================================
echo.
echo Este teste:
echo   - NAO altera hosts/DNS do Windows
echo   - NAO liga IsOnline global
echo   - preserva save/tutorial
echo   - faz backup do AMS antes do patch
echo   - redireciona apenas pjsmmm-legacy para localhost
echo.

echo [1/5] Baixando patch Phase 19...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/00737962edad5ad340a56c1024740ff64b6f0de2/tools/profile_phase19_local_backend_route.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/5] Baixando runner...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/e209a5c252cc3022da791795f3344f8d87f52837/tools/run_phase19_local_backend.ps1" ^
  -o "%RUNNER%"
if errorlevel 1 goto :fail

echo [3/5] Baixando servidor local...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c9a78cf14439890ef80b471b147c6eae5f36964a/tools/rextreme_local_backend.ps1" ^
  -o "%BACKEND%"
if errorlevel 1 goto :fail

echo [4/5] Validando e aplicando patch...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%PATCH%','%RUNNER%','%BACKEND%')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){Write-Host ('ERRO em '+$p) -ForegroundColor Red;$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo [5/5] Abrindo jogo com ReXtreme Local Backend...
echo.
echo Deixe esta janela aberta.
echo Quando chegar ao lobby:
echo   - veja se o popup SEM CONEXAO mudou/desapareceu
echo   - depois feche o jogo completamente
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%RUNNER%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Phase 19 terminou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PHASE 19 FINALIZADA
echo ============================================================
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE19_LOCAL_BACKEND_LOGS\LATEST-PHASE19-LOCAL-BACKEND.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Falha ao preparar/aplicar a Phase 19.
echo Nenhum reset de save foi executado.
pause
exit /b 1
