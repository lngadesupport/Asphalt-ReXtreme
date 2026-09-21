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
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/962a37a818bd6b825dd899732b13081e20c90cbd/tools/profile_phase20_local_online_gates.ps1" ^
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

:fail
echo.
echo [ERRO] Falha ao preparar/aplicar a Phase 20.
echo O save nao foi resetado.
pause
exit /b 1
