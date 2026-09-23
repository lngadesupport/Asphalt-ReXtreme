@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17.2 Single DLL Deferred
set "ROOT=%CD%"
set "PRE=%ROOT%\prebuilt\r172\IGPLib_x86.dll"
set "TARGET=%ROOT%\_PACKAGE_PHASE5\IGPLib_x86.dll"
set "BACKUPDIR=%ROOT%\_BACKUPS\R172"
set "BACKUP=%BACKUPDIR%\IGPLib_x86.dll"
set "OLDSECOND=%ROOT%\_PACKAGE_PHASE5\ReXtremeLocalRuntime.dll"

if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%" >nul 2>&1
echo ============================================================
echo  Asphalt ReXtreme - R17.2 SINGLE DLL DEFERRED
echo ============================================================
echo.

if not exist "%PRE%" goto :missing
if not exist "%TARGET%" goto :missing_target

if not exist "%BACKUP%" (
  copy /y "%TARGET%" "%BACKUP%" >nul
  if errorlevel 1 goto :fail
)

if exist "%OLDSECOND%" del /q "%OLDSECOND%" >nul 2>&1

copy /y "%PRE%" "%TARGET%" >nul
if errorlevel 1 goto :restore
fc /b "%PRE%" "%TARGET%" >nul
if errorlevel 1 goto :restore

echo R17.2 instalada com sucesso.
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
pause
exit /b 0

:missing
echo [ERRO] prebuilt\r172\IGPLib_x86.dll nao encontrado.
goto :fail
:missing_target
echo [ERRO] _PACKAGE_PHASE5\IGPLib_x86.dll nao encontrado.
goto :fail
:restore
if exist "%BACKUP%" copy /y "%BACKUP%" "%TARGET%" >nul
echo [ERRO] Falha ao aplicar; backup restaurado.
:fail
echo.
pause
exit /b 1
