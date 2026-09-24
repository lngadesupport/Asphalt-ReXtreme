@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Phase 20 Local Online Gates

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 20 LOCAL ONLINE GATES
echo ============================================================
echo.
echo Mantem IsOnline global FALSE.
echo Forca somente 4 gates locais que caem no popup SEM CONEXAO.
echo Mantem pjsmmm redirecionado para localhost.
echo Faz backup do AMS antes do patch.
echo.

echo [1/4] Baixando patch...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/96b7af0fb1678787561cede94342bce0ebd42ff9/tools/profile_phase20_local_online_gates.ps1" ^
  -o "%TOOLS%\profile_phase20_local_online_gates.ps1"
if errorlevel 1 goto :fail

echo [2/4] Baixando runner...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/e9890679224ccf33939b735f3e4675b47aab1c2e/tools/run_phase20_local_gates.ps1" ^
  -o "%TOOLS%\run_phase20_local_gates.ps1"
if errorlevel 1 goto :fail

echo [3/4] Baixando backend local...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c9a78cf14439890ef80b471b147c6eae5f36964a/tools/rextreme_local_backend.ps1" ^
  -o "%TOOLS%\rextreme_local_backend.ps1"
if errorlevel 1 goto :fail

echo Validando scripts...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bad=0;foreach($p in @('%TOOLS%\profile_phase20_local_online_gates.ps1','%TOOLS%\run_phase20_local_gates.ps1','%TOOLS%\rextreme_local_backend.ps1')){$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};$bad=1}};if($bad){exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo Encerrando qualquer instancia antiga do AMS.exe...
taskkill /F /IM AMS.exe >nul 2>nul
timeout /t 2 /nobreak >nul

echo Verificando se AMS.exe ficou livre para escrita...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='%ROOT%\\_PACKAGE_PHASE5\\AMS.exe';$ok=$false;for($i=0;$i -lt 20;$i++){try{$s=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read);$s.Dispose();$ok=$true;break}catch{Start-Sleep -Milliseconds 500}};if(-not $ok){Write-Host 'AMS.exe continua bloqueado apos encerrar AMS.exe.' -ForegroundColor Red;Get-Process AMS -ErrorAction SilentlyContinue|Format-Table Id,ProcessName,Path -AutoSize;exit 21}else{Write-Host 'AMS.exe livre para escrita.' -ForegroundColor Green}"
if errorlevel 1 goto :locked

echo Aplicando Phase 20...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%TOOLS%\profile_phase20_local_online_gates.ps1" ^
  -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo [4/4] Abrindo jogo...
echo.
echo Teste o lobby. Veja se SEM CONEXAO:
echo   - desapareceu
echo   - mudou
echo   - ou continua identico
echo.
echo Depois feche o jogo completamente.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%TOOLS%\run_phase20_local_gates.ps1" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Phase 20 terminou com codigo %RC%.
  pause
  exit /b %RC%
)

echo ============================================================
echo  PHASE 20 FINALIZADA
echo ============================================================
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE20_LOCAL_GATES_LOGS\LATEST-PHASE20.zip
echo.
pause
exit /b 0

:locked
echo.
echo [ERRO] AMS.exe ainda esta bloqueado.
echo Feche o jogo e qualquer janela/launcher antiga e execute este CMD novamente.
echo O save nao foi resetado.
pause
exit /b 21

:fail
echo.
echo [ERRO] Falha ao preparar/aplicar a Phase 20.
echo O save nao foi resetado.
pause
exit /b 1
