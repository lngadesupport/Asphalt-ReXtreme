@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Install Runtime Logger

echo ============================================================
echo  ASPHALT ReXTREME - INSTALL RUNTIME LOGGER
echo ============================================================
echo.
echo Instala logging automatico em RUN-PACKAGE-PHASE5.cmd.
echo Seu launcher atual sera preservado como:
echo   RUN-PACKAGE-PHASE5-ORIGINAL.cmd
echo.

set "ROOT=%CD%"
set "GAME=%ROOT%\_PACKAGE_PHASE5"
set "TOOLS=%ROOT%\tools"
set "LIVE=%GAME%\RUN-PACKAGE-PHASE5.cmd"
set "BACKUP=%GAME%\RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
set "LOGGER=%TOOLS%\runtime_session_logger.ps1"
set "WRAPPER=%ROOT%\_runtime_wrapper.tmp.cmd"

if not exist "%GAME%\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado em:
  echo   %GAME%
  pause
  exit /b 10
)

if not exist "%LIVE%" (
  echo [ERRO] Launcher atual nao encontrado:
  echo   %LIVE%
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/5] Baixando logger...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/95cf8af4923e9bf688a46a18713349d1932abef7/tools/runtime_session_logger.ps1" ^
  -o "%LOGGER%.new"
if errorlevel 1 goto :fail

echo [2/5] Baixando wrapper...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/553b12d99ecca4652eb990a930ef1facc7fcd120/diagnostics/RUN-PACKAGE-PHASE5-LOGGER-WRAPPER.cmd" ^
  -o "%WRAPPER%"
if errorlevel 1 goto :fail

move /y "%LOGGER%.new" "%LOGGER%" >nul
if errorlevel 1 goto :fail

echo [3/5] Validando PowerShell...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%LOGGER%',[ref]$t,[ref]$e);if($e.Count){$e|%%{Write-Host $_.Message -ForegroundColor Red};exit 1}else{Write-Host 'PowerShell OK' -ForegroundColor Green}"
if errorlevel 1 goto :fail

echo [4/5] Preservando launcher original...
findstr /c:"REXTREME_RUNTIME_LOGGER_WRAPPER" "%LIVE%" >nul 2>&1
if errorlevel 1 (
  if not exist "%BACKUP%" (
    copy /y "%LIVE%" "%BACKUP%" >nul
    if errorlevel 1 goto :fail
  )
) else (
  if not exist "%BACKUP%" (
    echo [ERRO] Wrapper ja esta instalado, mas o backup original sumiu.
    echo Nao vou sobrescrever nada.
    pause
    exit /b 20
  )
)

echo [5/5] Instalando wrapper automatico...
copy /y "%WRAPPER%" "%LIVE%" >nul
if errorlevel 1 goto :fail
del /q "%WRAPPER%" >nul 2>&1

if not exist "%GAME%\_RUNTIME_LOGS" mkdir "%GAME%\_RUNTIME_LOGS"

echo.
echo ============================================================
echo  RUNTIME LOGGER INSTALADO
echo ============================================================
echo.
echo A partir de agora, abrir:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo gera automaticamente logs em:
echo   _PACKAGE_PHASE5\_RUNTIME_LOGS
echo.
echo O ZIP mais recente ficara em:
echo   _PACKAGE_PHASE5\_RUNTIME_LOGS\LATEST-RUNTIME-LOG.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Falha ao instalar o runtime logger.
if exist "%WRAPPER%" del /q "%WRAPPER%" >nul 2>&1
if exist "%LOGGER%.new" del /q "%LOGGER%.new" >nul 2>&1
echo.
pause
exit /b 1
