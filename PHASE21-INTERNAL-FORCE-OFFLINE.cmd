@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 21 Internal Offline

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase21_internal_force_offline.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 21 INTERNAL OFFLINE
echo ============================================================
echo.
echo Esta fase NAO usa servidor local.
echo Ela altera apenas branches internos do AMS.exe para impedir
echo que quatro caminhos conhecidos caiam no popup NO_INTERNET.
echo.
echo IsOnline global continua FALSE.
echo Save/tutorial nao sao resetados.
echo.

echo [1/3] Baixando patch interno...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/bc1055079614bbbb65fdbd4654b7678c3ce0e71b/tools/profile_phase21_internal_force_offline.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando qualquer AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando patch interno...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PATCH APLICADO
echo ============================================================
echo.
echo Agora abra o jogo pelo launcher normal:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Verifique se o popup SEM CONEXAO desapareceu.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 21 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
