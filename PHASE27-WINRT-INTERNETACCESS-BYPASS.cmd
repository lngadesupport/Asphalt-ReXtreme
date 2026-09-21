@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 27 WinRT InternetAccess Bypass

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase27_winrt_internetaccess_bypass.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 27 WINRT INTERNETACCESS BYPASS
echo ============================================================
echo.
echo Forca somente o predicado WinRT que verifica
echo NetworkConnectivityLevel == InternetAccess.
echo.
echo IsOnline global continua FALSE para evitar o freeze antigo.
echo Nao usa backend local.
echo Nao reseta save/LocalState.
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ccdc196dbed6057e95bc21bc8c18972b427f17e4/tools/profile_phase27_winrt_internetaccess_bypass.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando bypass...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 27 APLICADA
echo ============================================================
echo.
echo Abra o jogo pelo launcher normal:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste:
echo   - lobby
echo   - popup SEM CONEXAO
echo   - botao NOVAMENTE
echo   - menus que antes exigiam rede
echo.
echo Me diga se:
echo   1. popup sumiu
echo   2. popup mudou
echo   3. continua igual
echo   4. jogo travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 27 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
