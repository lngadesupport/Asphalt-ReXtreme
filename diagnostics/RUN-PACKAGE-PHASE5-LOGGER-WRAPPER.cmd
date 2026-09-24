@echo off
rem REXTREME_RUNTIME_LOGGER_WRAPPER
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "LOGGER=%ROOT%\tools\runtime_session_logger.ps1"
set "ORIGINAL=%~dp0RUN-PACKAGE-PHASE5-ORIGINAL.cmd"

if not exist "%LOGGER%" (
  echo [ERRO] Logger nao encontrado:
  echo   %LOGGER%
  echo.
  pause
  exit /b 40
)

if not exist "%ORIGINAL%" (
  echo [ERRO] Launcher original nao encontrado:
  echo   %ORIGINAL%
  echo.
  pause
  exit /b 41
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%LOGGER%" ^
  -ProjectRoot "%ROOT%" ^
  -OriginalLauncher "%ORIGINAL%"

set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [AVISO] O logger terminou com codigo %RC%.
  echo Verifique _RUNTIME_LOGS.
  echo.
  pause
)
exit /b %RC%
