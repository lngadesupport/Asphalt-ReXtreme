@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 48 CraftCar Direct Completion

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase48_craftcar_direct_completion.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 48 CRAFTCAR DIRECT COMPLETION
echo ============================================================
echo.
echo Usa o callback real de conclusao da montagem:
echo   - status local = 0 (sucesso)
echo   - limpa pending original
echo   - pula start remoto
echo   - pula ativacao do spinner
echo   - mantem Phase36
echo   - mantem IsOnline global FALSE
echo.
echo Nao reseta save/LocalState.
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/70d9b67708a89985feb4fc6f43b0a6bd770cd16a/tools/profile_phase48_craftcar_direct_completion.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando direct completion...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 48 APLICADA
echo ============================================================
echo.
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste somente o botao MONTAR do Ford.
echo Informe:
echo   - montou e avancou
echo   - spinner sumiu mas nao montou
echo   - spinner continua
echo   - travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 48 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
