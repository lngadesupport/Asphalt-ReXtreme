@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17 Easy Apply

set "ROOT=%CD%"
set "PREBUILT=%ROOT%\prebuilt\r17\IGPLib_x86.dll"
set "PACKAGE=%ROOT%\_PACKAGE_PHASE5"
set "TARGET=%PACKAGE%\IGPLib_x86.dll"
set "BACKUPDIR=%ROOT%\_BACKUPS\R17"
set "BACKUP=%BACKUPDIR%\IGPLib_x86.dll"
set "TRACEDIR=%ROOT%\_TRACE_MONTAR"
set "LOG=%TRACEDIR%\R17-EASY-APPLY.log"

if not exist "%TRACEDIR%" mkdir "%TRACEDIR%" >nul 2>&1

> "%LOG%" echo ============================================================
>>"%LOG%" echo R17 EASY APPLY
>>"%LOG%" echo Root: %ROOT%
>>"%LOG%" echo Date: %DATE% %TIME%
>>"%LOG%" echo ============================================================

echo ============================================================
echo  Asphalt ReXtreme - R17 EASY APPLY
echo ============================================================
echo.
echo Este modo NAO precisa de Visual Studio.
echo Este modo NAO compila nada no seu PC.
echo.

if not exist "%PREBUILT%" (
    echo [ERRO] DLL precompilado nao encontrado:
    echo   %PREBUILT%
    echo.
    echo Atualize a branch campaign-edition-win32 e tente novamente:
    echo   git pull --ff-only origin campaign-edition-win32
    >>"%LOG%" echo ERROR: prebuilt runtime missing: %PREBUILT%
    goto :fail
)

if not exist "%PACKAGE%\" (
    echo [ERRO] Pasta _PACKAGE_PHASE5 nao encontrada.
    echo   %PACKAGE%
    >>"%LOG%" echo ERROR: package directory missing: %PACKAGE%
    goto :fail
)

if not exist "%TARGET%" (
    echo [ERRO] O pacote nao possui IGPLib_x86.dll.
    echo   %TARGET%
    >>"%LOG%" echo ERROR: package target missing: %TARGET%
    goto :fail
)

if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%" >nul 2>&1

if not exist "%BACKUP%" (
    echo [1/3] Criando backup do IGPLib_x86.dll atual...
    copy /y "%TARGET%" "%BACKUP%" >nul
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar o backup.
        >>"%LOG%" echo ERROR: backup copy failed.
        goto :fail
    )
    >>"%LOG%" echo Backup created: %BACKUP%
) else (
    echo [1/3] Backup R17 ja existe. Mantendo o original salvo.
    >>"%LOG%" echo Backup already exists: %BACKUP%
)

echo [2/3] Instalando o runtime R17 precompilado...
copy /y "%PREBUILT%" "%TARGET%" >nul
if errorlevel 1 (
    echo [ERRO] Nao foi possivel copiar o runtime para o pacote.
    >>"%LOG%" echo ERROR: runtime copy failed.
    goto :restore_and_fail
)

echo [3/3] Verificando a copia byte a byte...
fc /b "%PREBUILT%" "%TARGET%" >nul
if errorlevel 1 (
    echo [ERRO] A verificacao binaria falhou.
    >>"%LOG%" echo ERROR: binary verification failed.
    goto :restore_and_fail
)

for %%F in ("%PREBUILT%") do set "R17SIZE=%%~zF"
>>"%LOG%" echo Runtime source: %PREBUILT%
>>"%LOG%" echo Runtime target: %TARGET%
>>"%LOG%" echo Runtime size: %R17SIZE% bytes
>>"%LOG%" echo RESULT: SUCCESS

echo.
echo ============================================================
echo  R17 INSTALADO COM SUCESSO
echo ============================================================
echo.
echo DLL:
echo   %TARGET%
echo.
echo Backup:
echo   %BACKUP%
echo.
echo Log:
echo   %LOG%
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
pause
exit /b 0

:restore_and_fail
if exist "%BACKUP%" (
    echo Restaurando o DLL anterior...
    copy /y "%BACKUP%" "%TARGET%" >nul
    >>"%LOG%" echo Previous DLL restored from backup.
)

:fail
echo.
echo A R17 NAO foi aplicada.
echo Veja o log:
echo   %LOG%
echo.
pause
exit /b 1
