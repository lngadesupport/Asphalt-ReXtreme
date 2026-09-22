@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 41 Build State Map

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "SCRIPT=%TOOLS%\profile_phase41_build_state_map.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 41 BUILD STATE MAP v2
echo ============================================================
echo.
echo Mapeia apenas:
echo   - funcao READY_TO_BUILD (0x00573880)
echo   - unico caller da montagem (0x0059F350)
echo   - start/result do CraftCar
echo   - writes locais e branches relacionados
echo.
echo Nao aplica bypass novo.
echo Phase36 permanece ativa.
echo Nao reseta save/LocalState.
echo.

echo [1/2] Baixando mapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ea7862bbb07d9db465478640761b3607d30eb936/tools/profile_phase41_build_state_map.ps1" ^
  -o "%SCRIPT%"
if errorlevel 1 goto :fail

echo [2/2] Validando e executando...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%SCRIPT%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%SCRIPT%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  PHASE 41 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE41_BUILD_STATE_MAP\LATEST-PHASE41-BUILD-STATE-MAP.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 41 falhou.
echo O save nao foi resetado.
pause
exit /b 1
