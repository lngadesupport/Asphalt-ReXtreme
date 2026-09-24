@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 42 Build Button Local Online

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase42_build_button_local_online.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 42 BUILD BUTTON LOCAL-ONLINE
echo ============================================================
echo.
echo Faz no botao MONTAR o mesmo principio usado para liberar
echo o lobby: somente esse handler toma o caminho "online".
echo.
echo Global IsOnline continua FALSE.
echo Phase36 continua ativa.
echo Nao reseta save/LocalState.
echo.

echo [1/3] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/6224bba95c9398a874b399c56b43557f248431ff/tools/profile_phase42_build_button_local_online.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/3] Validando script...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PATCH%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo [3/3] Aplicando bypass local...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 42 APLICADA
echo ============================================================
echo.
echo Abra:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste o botao MONTAR do Ford.
echo Informe:
echo   - montou e avancou
echo   - spinner continua
echo   - mudou o comportamento
echo   - travou/fechou
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 42 nao foi aplicada.
echo O save nao foi resetado.
pause
exit /b 1
