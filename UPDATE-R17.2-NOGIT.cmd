@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - R17.2 NO-GIT
set "ROOT=%CD%"
set "PRE=%ROOT%\prebuilt\r172"
set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo ============================================================
echo  Asphalt ReXtreme - R17.2 NO-GIT
echo ============================================================
echo.

where curl.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] curl.exe nao encontrado.
  pause
  exit /b 1
)

if not exist "%PRE%" mkdir "%PRE%" >nul 2>&1

echo [1/2] Baixando R17.2...
curl.exe -fL --retry 3 --connect-timeout 20 "%BASE%/prebuilt/r172/IGPLib_x86.dll" -o "%PRE%\IGPLib_x86.dll"
if errorlevel 1 goto :download_error

echo [2/2] Baixando aplicador...
curl.exe -fL --retry 3 --connect-timeout 20 "%BASE%/APPLY-R17.2-SINGLE-DLL.cmd" -o "%ROOT%\APPLY-R17.2-SINGLE-DLL.cmd"
if errorlevel 1 goto :download_error

for %%F in ("%PRE%\IGPLib_x86.dll") do set "SIZE=%%~zF"
if "%SIZE%"=="" goto :download_error
if %SIZE% LSS 100000 goto :bad_size

call "%ROOT%\APPLY-R17.2-SINGLE-DLL.cmd"
exit /b %ERRORLEVEL%

:bad_size
echo [ERRO] DLL R17.2 parece invalido: %SIZE% bytes
pause
exit /b 1

:download_error
echo [ERRO] Falha no download.
pause
exit /b 1
