@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - PHASE 13 FIX ONE CLICK

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 13 FIX ONE CLICK
echo ============================================================
echo.
echo Este CMD:
echo   1. baixa o script Phase 13 corrigido
echo   2. restaura automaticamente o Phase 5 verificado se necessario
echo   3. reaplica a Phase 13
echo   4. inicia o jogo se tudo der certo
echo.

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PS1=%TOOLS%\profile_phase13_local_onboarding.ps1"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "LAUNCH=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "FIXCOMMIT=46fb9bbbd3cbe5c5a38a2a4a127d95f0603ace7a"
set "URL=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/%FIXCOMMIT%/tools/profile_phase13_local_onboarding.ps1"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado:
  echo   %GAME%\AMS.exe
  echo.
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/4] Baixando Phase 13 corrigida...
where curl.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] curl.exe nao foi encontrado.
  pause
  exit /b 11
)

curl.exe -fL --retry 3 --retry-delay 1 ^
  "%URL%?v=%FIXCOMMIT%" ^
  -o "%PS1%.new"

if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao baixar o script corrigido.
  if exist "%PS1%.new" del /q "%PS1%.new" >nul 2>&1
  pause
  exit /b 12
)

for %%I in ("%PS1%.new") do if %%~zI LSS 1000 (
  echo [ERRO] Download invalido ou incompleto.
  del /q "%PS1%.new" >nul 2>&1
  pause
  exit /b 13
)

move /y "%PS1%.new" "%PS1%" >nul
if errorlevel 1 (
  echo [ERRO] Nao foi possivel atualizar:
  echo   %PS1%
  pause
  exit /b 14
)

echo [2/4] Validando sintaxe PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"

if errorlevel 1 (
  echo [ERRO] O script baixado nao passou na validacao.
  pause
  exit /b 15
)

echo [3/4] Aplicando Phase 13...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo ============================================================
  echo  PHASE 13 FALHOU - CODIGO %RC%
  echo ============================================================
  echo.
  echo Nao abra o jogo ainda.
  echo Tire uma captura desta janela e me envie.
  echo.
  pause
  exit /b %RC%
)

echo.
echo [4/4] Phase 13 aplicada com sucesso.
echo.

if exist "%GAME%\PROFILE-PHASE13-LOCAL-ONBOARDING-REPORT.json" (
  echo Relatorio criado:
  echo   %GAME%\PROFILE-PHASE13-LOCAL-ONBOARDING-REPORT.json
) else (
  echo [AVISO] O patch terminou sem erro, mas o relatorio nao foi encontrado.
)

echo.
echo ============================================================
echo  PHASE 13 OK
echo ============================================================
echo.

if exist "%LAUNCH%" (
  echo Iniciando Asphalt ReXtreme...
  call "%LAUNCH%"
  exit /b %ERRORLEVEL%
)

echo [AVISO] Launcher nao encontrado:
echo   %LAUNCH%
echo.
echo Abra o jogo pelo metodo que voce ja estava usando.
pause
exit /b 0
