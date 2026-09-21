@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 38 OnlinePurchase Local Success

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase38_onlinepurchase_local_success.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 38 ONLINE PURCHASE LOCAL SUCCESS
echo ============================================================
echo.
echo Corrige a familia OnlinePurchaseRequest:
echo   - nao envia ao backend
echo   - usa o callback original do AsphaltShop
echo   - resultado local = SUCCESS
echo.
echo Tambem:
echo   - remove o experimento amplo da Phase37
echo   - mantem Phase36 para o popup SEM CONEXAO
echo   - mantem IsOnline global FALSE
echo   - nao reseta save/LocalState
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/e4ce4a76c20278414dab28f092ce4ac45658c4f8/tools/profile_phase38_onlinepurchase_local_success.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando OnlinePurchase offline local...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 38 APLICADA
echo ============================================================
echo.
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste a montagem do Ford.
echo Informe:
echo   - montou e avancou
echo   - spinner sumiu mas nao montou
echo   - continua carregando
echo   - travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 38 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
