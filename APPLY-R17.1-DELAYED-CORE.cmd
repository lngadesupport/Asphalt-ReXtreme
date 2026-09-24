@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17.1 Delayed Core

set "ROOT=%CD%"
set "PRE=%ROOT%\prebuilt\r171"
set "BOOT=%PRE%\IGPLib_x86.dll"
set "RUNTIME=%PRE%\ReXtremeLocalRuntime.dll"
set "PACKAGE=%ROOT%\_PACKAGE_PHASE5"
set "TARGET_BOOT=%PACKAGE%\IGPLib_x86.dll"
set "TARGET_RUNTIME=%PACKAGE%\ReXtremeLocalRuntime.dll"
set "BACKUPDIR=%ROOT%\_BACKUPS\R171"
set "BACKUP_BOOT=%BACKUPDIR%\IGPLib_x86.dll"
set "TRACE=%ROOT%\_TRACE_MONTAR"
set "LOG=%TRACE%\R171-DELAYED-CORE-APPLY.log"

if not exist "%TRACE%" mkdir "%TRACE%" >nul 2>&1
if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%" >nul 2>&1

> "%LOG%" echo R17.1 DELAYED CORE APPLY
>>"%LOG%" echo Date: %DATE% %TIME%

echo ============================================================
echo  Asphalt ReXtreme - R17.1 DELAYED CORE
echo ============================================================
echo.
echo Bootstrap IGP: /NOENTRY
echo Runtime: carregado somente apos InitBridgeClass/XAML
echo UI overlay: desativada neste teste de estabilidade
echo.

if not exist "%BOOT%" goto :missing
if not exist "%RUNTIME%" goto :missing
if not exist "%TARGET_BOOT%" goto :missing_target

if not exist "%BACKUP_BOOT%" (
    echo [1/4] Salvando IGPLib atual...
    copy /y "%TARGET_BOOT%" "%BACKUP_BOOT%" >nul
    if errorlevel 1 goto :fail
) else (
    echo [1/4] Backup R17.1 ja existe.
)

echo [2/4] Instalando bootstrap IGP...
copy /y "%BOOT%" "%TARGET_BOOT%" >nul
if errorlevel 1 goto :restore

echo [3/4] Instalando runtime local atrasado...
copy /y "%RUNTIME%" "%TARGET_RUNTIME%" >nul
if errorlevel 1 goto :restore

echo [4/4] Verificando arquivos...
fc /b "%BOOT%" "%TARGET_BOOT%" >nul
if errorlevel 1 goto :restore
fc /b "%RUNTIME%" "%TARGET_RUNTIME%" >nul
if errorlevel 1 goto :restore

>>"%LOG%" echo RESULT: SUCCESS

echo.
echo ============================================================
echo  R17.1 INSTALADA COM SUCESSO
echo ============================================================
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Teste o botao MONTAR.
echo O esperado e NAO aparecer o erro de sincronizacao.
echo.
pause
exit /b 0

:missing
echo [ERRO] Arquivos prebuilt R17.1 nao encontrados em:
echo   %PRE%
>>"%LOG%" echo ERROR: prebuilt missing
goto :fail

:missing_target
echo [ERRO] _PACKAGE_PHASE5\IGPLib_x86.dll nao encontrado.
>>"%LOG%" echo ERROR: target missing
goto :fail

:restore
echo [ERRO] Falha ao instalar/verificar. Restaurando bootstrap anterior...
if exist "%BACKUP_BOOT%" copy /y "%BACKUP_BOOT%" "%TARGET_BOOT%" >nul
if exist "%TARGET_RUNTIME%" del /q "%TARGET_RUNTIME%" >nul 2>&1
>>"%LOG%" echo ERROR: install failed and rollback attempted

:fail
echo.
echo R17.1 nao foi aplicada.
echo Log:
echo   %LOG%
echo.
pause
exit /b 1
