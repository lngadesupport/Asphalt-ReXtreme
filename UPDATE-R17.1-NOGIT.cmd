@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17.1 NO-GIT UPDATE

set "ROOT=%CD%"
set "PRE=%ROOT%\prebuilt\r171"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"
set "APPLY=%ROOT%\APPLY-R17.1-DELAYED-CORE.cmd"

echo ============================================================
echo  Asphalt ReXtreme - R17.1 NO-GIT UPDATE
echo ============================================================
echo.
echo Nao usa Git e nao precisa de Visual Studio.
echo.

where curl.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] curl.exe nao encontrado.
  echo.
  pause
  exit /b 1
)

if not exist "%PRE%" mkdir "%PRE%" >nul 2>&1

echo [1/3] Baixando aplicador...
curl.exe -fL --retry 3 --connect-timeout 20 "%BASE%/APPLY-R17.1-DELAYED-CORE.cmd" -o "%APPLY%"
if errorlevel 1 goto :download_error

echo [2/3] Baixando bootstrap IGP...
curl.exe -fL --retry 3 --connect-timeout 20 "%BASE%/prebuilt/r171/IGPLib_x86.dll" -o "%PRE%\IGPLib_x86.dll"
if errorlevel 1 goto :download_error

echo [3/3] Baixando runtime local...
curl.exe -fL --retry 3 --connect-timeout 20 "%BASE%/prebuilt/r171/ReXtremeLocalRuntime.dll" -o "%PRE%\ReXtremeLocalRuntime.dll"
if errorlevel 1 goto :download_error

for %%F in ("%PRE%\IGPLib_x86.dll") do set "BOOTSIZE=%%~zF"
for %%F in ("%PRE%\ReXtremeLocalRuntime.dll") do set "RUNSIZE=%%~zF"

if not "%BOOTSIZE%"=="3072" (
  echo [ERRO] Bootstrap com tamanho inesperado: %BOOTSIZE% bytes
  pause
  exit /b 1
)

if "%RUNSIZE%"=="" (
  echo [ERRO] Runtime nao foi baixado corretamente.
  pause
  exit /b 1
)

if %RUNSIZE% LSS 100000 (
  echo [ERRO] Runtime parece invalido: %RUNSIZE% bytes
  pause
  exit /b 1
)

echo.
echo Downloads conferidos.
echo Bootstrap: %BOOTSIZE% bytes
echo Runtime:   %RUNSIZE% bytes
echo.
call "%APPLY%"
exit /b %ERRORLEVEL%

:download_error
echo.
echo [ERRO] Falha no download da R17.1.
echo Verifique a internet e tente novamente.
echo.
pause
exit /b 1
