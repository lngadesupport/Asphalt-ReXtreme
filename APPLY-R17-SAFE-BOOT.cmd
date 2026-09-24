@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17 SAFE BOOT

set "ROOT=%CD%"
set "SAFE=%ROOT%\prebuilt\r17-safe\IGPLib_x86.dll"
set "TARGET=%ROOT%\_PACKAGE_PHASE5\IGPLib_x86.dll"
set "BACKUPDIR=%ROOT%\_BACKUPS\R17"
set "BACKUP=%BACKUPDIR%\IGPLib_x86.dll"
set "TRACEDIR=%ROOT%\_TRACE_MONTAR"
set "LOG=%TRACEDIR%\R17-SAFE-BOOT.log"

if not exist "%TRACEDIR%" mkdir "%TRACEDIR%" >nul 2>&1
if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%" >nul 2>&1

> "%LOG%" echo R17 SAFE BOOT
>>"%LOG%" echo Date: %DATE% %TIME%
>>"%LOG%" echo Root: %ROOT%

echo ============================================================
echo  Asphalt ReXtreme - R17 SAFE BOOT
echo ============================================================
echo.
echo Este teste usa um IGPLib sem DllMain, sem thread,
echo sem UI e sem hooks.
echo.

if not exist "%SAFE%" (
  echo [ERRO] Safe DLL nao encontrado:
  echo   %SAFE%
  >>"%LOG%" echo ERROR: safe DLL missing
  goto :fail
)

if not exist "%TARGET%" (
  echo [ERRO] IGPLib_x86.dll do pacote nao encontrado:
  echo   %TARGET%
  >>"%LOG%" echo ERROR: target missing
  goto :fail
)

if not exist "%BACKUP%" (
  echo [1/3] Salvando o DLL anterior...
  copy /y "%TARGET%" "%BACKUP%" >nul
  if errorlevel 1 goto :backup_fail
) else (
  echo [1/3] Backup anterior preservado.
)

echo [2/3] Instalando R17 SAFE BOOT...
copy /y "%SAFE%" "%TARGET%" >nul
if errorlevel 1 goto :copy_fail

echo [3/3] Verificando byte a byte...
fc /b "%SAFE%" "%TARGET%" >nul
if errorlevel 1 goto :verify_fail

for %%F in ("%SAFE%") do set "SAFESIZE=%%~zF"
>>"%LOG%" echo Safe DLL size: %SAFESIZE%
>>"%LOG%" echo RESULT: SUCCESS

echo.
echo ============================================================
echo  R17 SAFE BOOT INSTALADO
echo ============================================================
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo Se o jogo abrir, confirmamos que o crash estava
echo na inicializacao ativa da R17 e nao nos exports IGP.
echo.
pause
exit /b 0

:backup_fail
echo [ERRO] Falha ao criar backup.
>>"%LOG%" echo ERROR: backup failed
goto :fail

:copy_fail
echo [ERRO] Falha ao copiar o Safe DLL.
>>"%LOG%" echo ERROR: copy failed
goto :restore_fail

:verify_fail
echo [ERRO] Safe DLL copiado mas verificacao falhou.
>>"%LOG%" echo ERROR: verify failed
goto :restore_fail

:restore_fail
if exist "%BACKUP%" copy /y "%BACKUP%" "%TARGET%" >nul

:fail
echo.
echo SAFE BOOT nao foi aplicado.
echo Log:
echo   %LOG%
echo.
pause
exit /b 1
