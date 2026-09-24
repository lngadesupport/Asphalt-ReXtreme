@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title ReXtreme - Recover Phase 18 Results

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PS1=%TOOLS%\recover_phase18_backend_url_map.ps1"

if not exist "%TOOLS%" mkdir "%TOOLS%"

echo [1/2] Baixando recuperador...
curl.exe -fL --retry 3 --retry-delay 1 ^
  "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/cb3f758037442f78326f10a43c7ae4e433d28444/tools/recover_phase18_backend_url_map.ps1" ^
  -o "%PS1%"
if errorlevel 1 goto :fail

echo [2/2] Empacotando resultado que ja foi mapeado...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -ProjectRoot "%ROOT%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Nao foi possivel recuperar os arquivos existentes.
  echo Nesse caso use o mapper Phase 18 corrigido.
  pause
  exit /b %RC%
)

echo Envie:
echo   _PACKAGE_PHASE5\PROFILE-PHASE18-BACKEND-URL-MAP.zip
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Falha ao baixar o recuperador.
pause
exit /b 1
