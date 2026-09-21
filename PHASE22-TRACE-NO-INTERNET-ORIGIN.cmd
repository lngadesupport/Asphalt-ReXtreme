@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 22 Popup Trace

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase22_popup_tripwire.ps1"
set "RUNNER=%TOOLS%\run_phase22_popup_trace.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 22 POPUP TRACE
echo ============================================================
echo.
echo Esta fase instala armadilhas temporarias INT3 somente nos
echo PUSH das strings NO_INTERNET.
echo Quando o popup for construido, o jogo vai parar/crashar.
echo O depurador registra o callsite real e restaura AMS.exe.
echo.
echo Save/LocalState nao sao resetados.
echo.

echo [1/4] Baixando tripwire patcher...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/cc241793dd51bb743b0e3cc81a9892c318bd6b9d/tools/profile_phase22_popup_tripwire.ps1" ^
  -o "%PATCH%"
if errorlevel 1 goto :fail

echo [2/4] Baixando debugger runner...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/4a759d1c274f187d082e904390ecce9088869007/tools/run_phase22_popup_trace.ps1" ^
  -o "%RUNNER%"
if errorlevel 1 goto :fail

echo [3/4] Validando scripts...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%PATCH%','%RUNNER%')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){Write-Host ('ERRO em '+$p) -ForegroundColor Red;$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando AMS.exe antigo...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 1 /nobreak >nul

echo Instalando tripwires...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PATCH%" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :restore

echo.
echo [4/4] Iniciando jogo sob depurador...
echo.
echo O comportamento esperado e:
echo   1. jogo abre
echo   2. quando tentaria mostrar SEM CONEXAO, ele para/crasha
echo   3. esta janela gera o trace e restaura AMS.exe
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%RUNNER%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto :restore

echo ============================================================
echo  PHASE 22 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE22_POPUP_TRACE\LATEST-PHASE22-TRACE.txt
echo.
pause
exit /b 0

:restore
echo.
echo Tentando restaurar AMS.exe pre-Phase22...
if exist "%ROOT%\_PACKAGE_PHASE5\_PHASE22_POPUP_TRACE\AMS.PRE-TRAPS.exe" (
  copy /y "%ROOT%\_PACKAGE_PHASE5\_PHASE22_POPUP_TRACE\AMS.PRE-TRAPS.exe" "%ROOT%\_PACKAGE_PHASE5\AMS.exe" >nul
)
echo [ERRO] Phase 22 falhou, mas foi feita tentativa de restauracao.
echo O save nao foi resetado.
pause
exit /b 1

:fail
echo.
echo [ERRO] Falha ao preparar a Phase 22.
pause
exit /b 1
