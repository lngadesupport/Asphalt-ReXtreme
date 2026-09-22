@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 40 CraftCar Tutorial Map

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase40_craftcar_tutorial_map.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 40 CRAFTCAR / TUTORIAL MAP
echo ============================================================
echo.
echo Esta fase:
echo   - reverte Phase39
echo   - confirma Phase38/37 limpas
echo   - mantem Phase36
echo   - NAO aplica novo bypass
echo   - mapeia o handler real do botao de montar
echo.
echo Nao reseta save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/9807d5391ac079e4512663567c8f321d42eef51b/tools/profile_phase40_craftcar_tutorial_map.ps1" ^
  -o "%SCRIPT%"
if errorlevel 1 goto :fail

echo [2/2] Validando e executando...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%SCRIPT%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%SCRIPT%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 40 FINALIZADA
echo ============================================================
echo.
echo Phase39 foi removida; o lobby deve voltar ao estado da Phase36.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE40_CRAFTCAR_TUTORIAL_MAP\LATEST-PHASE40-CRAFTCAR-TUTORIAL-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 40 falhou.
echo O save nao foi resetado.
pause
exit /b 1
