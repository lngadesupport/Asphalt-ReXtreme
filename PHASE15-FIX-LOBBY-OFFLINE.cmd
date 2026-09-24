@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - PHASE 15 LOBBY OFFLINE FIX

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 15 LOBBY OFFLINE FIX
echo ============================================================
echo.
echo Mantem seu save/tutorial e remove o ramo especifico
echo do popup SEM CONEXAO no dispatcher do lobby.
echo.

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "PS1=%TOOLS%\profile_phase15_lobby_offline.ps1"
set "REPORT=%GAME%\PROFILE-PHASE15-LOBBY-OFFLINE-REPORT.json"
set "LAUNCH=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "PAYLOADCOMMIT=72430531ddbc9cc21ab66efe9c6c2e14c6def1f0"
set "URL=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/%PAYLOADCOMMIT%/tools/profile_phase15_lobby_offline.ps1"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado:
  echo   %GAME%\AMS.exe
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/6] Baixando payload Phase 15 fixo...
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
  echo [ERRO] Nao foi possivel atualizar o script local.
  pause
  exit /b 12
)

echo [2/6] Confirmando patch do dispatcher do lobby...
findstr /c:"00916B30" "%PS1%" >nul || goto :wrong_payload
findstr /c:"00916B3C" "%PS1%" >nul || goto :wrong_payload
findstr /c:"0x0BC2" "%PS1%" >nul || goto :wrong_payload
findstr /c:"0x0FAA" "%PS1%" >nul || goto :wrong_payload
echo Dispatcher Phase 15 confirmado.

echo [3/6] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%PS1%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1};Write-Host 'PowerShell OK' -ForegroundColor Green"
if errorlevel 1 (
  echo [ERRO] Falha de sintaxe.
  pause
  exit /b 14
)

echo [4/6] Aplicando Phase 15 a partir do Phase 5 verificado...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :patch_fail

echo [5/6] Verificando 32/32 patches no AMS...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$r=Get-Content -LiteralPath '%REPORT%' -Raw|ConvertFrom-Json;" ^
  "if([int]$r.PatchCount -ne 32){Write-Host ('ERRO: PatchCount='+$r.PatchCount) -ForegroundColor Red;exit 31};" ^
  "$d=[IO.File]::ReadAllBytes('%GAME%\AMS.exe');$bad=@();" ^
  "foreach($p in $r.Patches){$o=[Convert]::ToInt32(($p.Offset -replace '^0x',''),16);$bs=@($p.After -split ' '|%%{[Convert]::ToByte($_,16)});for($i=0;$i -lt $bs.Count;$i++){if($d[$o+$i] -ne $bs[$i]){$bad+=($p.Name+' @ '+$p.Offset);break}}};" ^
  "if($bad.Count){$bad|%%{Write-Host ('FALHOU: '+$_) -ForegroundColor Red};exit 32};" ^
  "Write-Host '32/32 patches verificados no AMS.' -ForegroundColor Green"
if errorlevel 1 (
  echo.
  echo [ERRO] Verificacao binaria falhou.
  pause
  exit /b 32
)

echo [6/6] Phase 15 pronta.
echo ============================================================
echo  PHASE 15 OK - 32/32 PATCHES VERIFICADOS
echo ============================================================
echo.
echo LocalState/save nao foi apagado.
echo Esperado: boot direto no lobby, sem SEM CONEXAO/NOVAMENTE.
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
echo [ERRO] Payload Phase 15 incorreto. Nada foi aplicado.
pause
exit /b 21

:download_fail
echo.
echo [ERRO] Falha ao baixar o payload Phase 15.
pause
exit /b 20

:patch_fail
echo.
echo ============================================================
echo  PHASE 15 FALHOU - CODIGO %RC%
echo ============================================================
echo Envie uma captura desta janela.
pause
exit /b %RC%
