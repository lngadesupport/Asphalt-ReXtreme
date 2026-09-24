@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - RUN GAME WITH RUNTIME LOG

set "ROOT=%CD%"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "LOGROOT=%GAME%\_RUNTIME_LOGS"
set "LOGGER=%TOOLS%\runtime_session_logger.ps1"
set "LIVE=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "BACKUP=%GAME%\RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
set "BOOT=%LOGROOT%\BOOTSTRAP-LAST.txt"

echo ============================================================
echo  ASPHALT ReXTREME - RUN GAME WITH RUNTIME LOG
echo ============================================================
echo.

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado:
  echo   %GAME%\AMS.exe
  pause
  exit /b 10
)

if not exist "%TOOLS%" mkdir "%TOOLS%"
if not exist "%LOGROOT%" mkdir "%LOGROOT%"

> "%BOOT%" echo [%DATE% %TIME%] bootstrap iniciou
>>"%BOOT%" echo ROOT=%ROOT%
>>"%BOOT%" echo GAME=%GAME%
>>"%BOOT%" echo LIVE=%LIVE%
>>"%BOOT%" echo BACKUP=%BACKUP%

echo [1/5] Pasta de logs confirmada:
echo   %LOGROOT%
echo.
echo bootstrap iniciou>"%LOGROOT%\LOGGER-STARTED.marker"

echo [2/5] Baixando logger verificado...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/95cf8af4923e9bf688a46a18713349d1932abef7/tools/runtime_session_logger.ps1" ^
  -o "%LOGGER%.new"
if errorlevel 1 (
  >>"%BOOT%" echo ERRO download logger
  echo [ERRO] Falha ao baixar o logger.
  pause
  exit /b 20
)

move /y "%LOGGER%.new" "%LOGGER%" >nul
if errorlevel 1 (
  >>"%BOOT%" echo ERRO move logger
  echo [ERRO] Falha ao instalar o logger local.
  pause
  exit /b 21
)

echo [3/5] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%LOGGER%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1};Write-Host 'PowerShell OK' -ForegroundColor Green"
if errorlevel 1 (
  >>"%BOOT%" echo ERRO sintaxe logger
  echo [ERRO] Logger nao passou na validacao.
  pause
  exit /b 22
)

set "ORIGINAL="
if exist "%BACKUP%" (
  set "ORIGINAL=%BACKUP%"
) else (
  if exist "%LIVE%" (
    findstr /c:"REXTREME_RUNTIME_LOGGER_WRAPPER" "%LIVE%" >nul 2>&1
    if errorlevel 1 (
      set "ORIGINAL=%LIVE%"
    )
  )
)

if not defined ORIGINAL (
  >>"%BOOT%" echo ERRO launcher original nao encontrado
  echo [ERRO] Nao encontrei um launcher original seguro.
  echo Esperado:
  echo   %BACKUP%
  echo ou um RUN-PACKAGE-PHASE5.cmd sem wrapper.
  pause
  exit /b 23
)

>>"%BOOT%" echo ORIGINAL=%ORIGINAL%

echo [4/5] Criando teste de escrita...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='%LOGROOT%\POWERSHELL-WRITE-TEST.txt';[IO.File]::WriteAllText($p,(Get-Date).ToString('o'));if(-not(Test-Path -LiteralPath $p)){exit 1};Write-Host 'Escrita em _RUNTIME_LOGS OK' -ForegroundColor Green"
if errorlevel 1 (
  >>"%BOOT%" echo ERRO teste escrita PowerShell
  echo [ERRO] PowerShell nao conseguiu escrever em:
  echo   %LOGROOT%
  pause
  exit /b 24
)

echo [5/5] Abrindo jogo com logger...
>>"%BOOT%" echo chamando runtime_session_logger.ps1
echo.
echo IMPORTANTE:
echo   deixe esta janela aberta enquanto joga.
echo   quando o popup SEM CONEXAO aparecer, feche o jogo.
echo   o ZIP sera finalizado apos o AMS.exe fechar.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%LOGGER%" ^
  -ProjectRoot "%ROOT%" ^
  -OriginalLauncher "%ORIGINAL%"

set "RC=%ERRORLEVEL%"
>>"%BOOT%" echo logger terminou RC=%RC%

echo.
if exist "%LOGROOT%\LATEST-RUNTIME-LOG.zip" (
  echo ============================================================
  echo  LOG CRIADO COM SUCESSO
  echo ============================================================
  echo   %LOGROOT%\LATEST-RUNTIME-LOG.zip
) else (
  echo ============================================================
  echo  LOG FINAL NAO FOI CRIADO
  echo ============================================================
  echo.
  echo Mesmo assim, envie estes arquivos se existirem:
  echo   %BOOT%
  echo   %LOGROOT%\POWERSHELL-WRITE-TEST.txt
)

echo.
pause
exit /b %RC%
