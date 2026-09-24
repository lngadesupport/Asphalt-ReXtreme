@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - PHASE 14 V3 VERIFIED

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 14 V3 VERIFIED
echo ============================================================
echo.
echo Payload fixo + verificacao pos-patch dos 30 patches.
echo Nao apaga LocalState nem progresso do tutorial.
echo.

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "PS1=%TOOLS%\profile_phase14_no_connection_ui.ps1"
set "REPORT=%GAME%\PROFILE-PHASE14-NO-CONNECTION-UI-REPORT.json"
set "LAUNCH=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "PAYLOADCOMMIT=16bbff467ff9e48c70755226f17ac253deb48b3a"
set "URL=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/%PAYLOADCOMMIT%/tools/profile_phase14_no_connection_ui.ps1"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado:
  echo   %GAME%\AMS.exe
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/6] Baixando payload imutavel...
curl.exe -fL --retry 3 --retry-delay 1 "%URL%" -o "%PS1%.new"
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

echo [2/6] Confirmando offsets corrigidos...
findstr /c:"00746EDB" "%PS1%" >nul || goto :wrong_payload
findstr /c:"008DA2B4" "%PS1%" >nul || goto :wrong_payload
findstr /c:"009171DC" "%PS1%" >nul || goto :wrong_payload
echo Payload correto confirmado.

echo [3/6] Validando sintaxe...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1};Write-Host 'PowerShell OK' -ForegroundColor Green"
if errorlevel 1 (
  echo [ERRO] Falha de sintaxe.
  pause
  exit /b 14
)

echo [4/6] Aplicando Phase 14 V3...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :patch_fail

echo [5/6] Verificando os 30 patches no AMS...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$r=Get-Content -LiteralPath '%REPORT%' -Raw|ConvertFrom-Json;" ^
  "if([int]$r.PatchCount -ne 30){Write-Host ('ERRO: PatchCount='+$r.PatchCount) -ForegroundColor Red;exit 31};" ^
  "$d=[IO.File]::ReadAllBytes('%GAME%\AMS.exe');" ^
  "$bad=@();" ^
  "foreach($p in $r.Patches){$o=[Convert]::ToInt32(($p.Offset -replace '^0x',''),16);$bs=@($p.After -split ' '|%%{[Convert]::ToByte($_,16)});for($i=0;$i -lt $bs.Count;$i++){if($d[$o+$i] -ne $bs[$i]){$bad+=($p.Name+' @ '+$p.Offset);break}}};" ^
  "if($bad.Count){$bad|%%{Write-Host ('FALHOU: '+$_) -ForegroundColor Red};exit 32};" ^
  "Write-Host '30/30 patches verificados no AMS.' -ForegroundColor Green"
if errorlevel 1 (
  echo.
  echo [ERRO] O script terminou, mas a verificacao binaria falhou.
  pause
  exit /b 32
)

echo [6/6] Phase 14 V3 confirmada.
echo ============================================================
echo  PHASE 14 V3 OK - 30/30 PATCHES VERIFICADOS
echo ============================================================
echo.
echo Seu save/LocalState nao foi apagado.
echo O jogo deve continuar entrando direto no lobby.
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

:wrong_payload
echo.
echo [ERRO] Payload incorreto/antigo detectado. Nada foi aplicado.
pause
exit /b 21

:download_fail
echo.
echo [ERRO] Falha ao baixar o payload fixo.
pause
exit /b 20

:patch_fail
echo.
echo ============================================================
echo  PHASE 14 V3 FALHOU - CODIGO %RC%
echo ============================================================
echo Envie uma captura desta janela.
pause
exit /b %RC%
