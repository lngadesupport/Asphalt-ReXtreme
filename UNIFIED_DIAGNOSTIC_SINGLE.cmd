@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo Asphalt ReXtreme - Unified Diagnostic v2
echo ============================================================
echo.
echo Este diagnostico coleta analise estatica + execucao + crash.
echo Nenhum arquivo do jogo sera modificado.
echo.

if not exist "%~dp0UNIFIED_DIAGNOSTIC.ps1" (
  echo [ERRO] UNIFIED_DIAGNOSTIC.ps1 nao foi encontrado ao lado deste CMD.
  echo Extraia os dois arquivos juntos na raiz da Campaign Edition.
  echo.
  pause
  exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0UNIFIED_DIAGNOSTIC.ps1" ^
  -GameRoot "%CD%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo Diagnostico terminou com codigo %RC%.
)
echo.
pause
exit /b %RC%
