@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - PHASE 14 FIX ONE CLICK

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 14 CONNECTION FIX
echo ============================================================
echo.
echo Corrige os popups de SEM CONEXAO mantendo o jogo offline.
echo Reconstroi sempre a partir do AMS Phase 5 verificado.
echo.

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "PS1=%TOOLS%\profile_phase14_no_connection_ui.ps1"
set "LAUNCH=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado:
  echo   %GAME%\AMS.exe
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/4] Baixando Phase 14...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "%BASE%/tools/profile_phase14_no_connection_ui.ps1" ^
  -o "%PS1%.new"
if errorlevel 1 goto :download_fail

for %%I in ("%PS1%.new") do if %%~zI LSS 1000 (
  echo [ERRO] Download incompleto.
  del /q "%PS1%.new" >nul 2>&1
  pause
  exit /b 11
)

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 (
  echo [ERRO] Nao foi possivel substituir o script local.
  pause
  exit /b 12
)

echo [2/4] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 (
  echo [ERRO] Falha de sintaxe.
  pause
  exit /b 13
)

echo [3/4] Reaplicando Campaign Phase 14...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo ============================================================
  echo  PHASE 14 FALHOU - CODIGO %RC%
  echo ============================================================
  echo.
  echo Envie uma captura desta janela.
  pause
  exit /b %RC%
)

echo.
echo [4/4] Phase 14 pronta.
echo ============================================================
echo  PHASE 14 OK
echo ============================================================
echo.
echo Teste esperado:
echo   onboarding/tutorial continuam funcionando
echo   lobby abre sem SEM CONEXAO / NOVAMENTE
echo.

if exist "%LAUNCH%" (
  echo Iniciando o jogo...
  call "%LAUNCH%"
  exit /b %ERRORLEVEL%
)

echo [AVISO] Launcher nao encontrado:
echo   %LAUNCH%
pause
exit /b 0

:download_fail
echo.
echo [ERRO] Falha ao baixar a Phase 14.
echo.
pause
exit /b 20
