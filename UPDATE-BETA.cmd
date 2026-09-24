@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme Public Beta - Update

set "BOOTSTRAP=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/public-beta-0.1/tools/public_beta.ps1?channel=beta1-bootstrap"
set "ENGINE=%~dp0tools\public_beta.ps1"
set "TEMPENGINE=%~dp0tools\public_beta.ps1.update"

echo [ReXtreme Beta] Atualizando motor do updater...
del /q "%TEMPENGINE%" 2>nul
curl.exe -fL --retry 3 -H "Cache-Control: no-cache" "%BOOTSTRAP%" -o "%TEMPENGINE%"
if errorlevel 1 (
  echo.
  echo [ERRO] Nao foi possivel atualizar o motor do updater.
  pause
  exit /b 30
)
if not exist "%TEMPENGINE%" (
  echo.
  echo [ERRO] Download do motor do updater nao foi materializado.
  pause
  exit /b 31
)
move /y "%TEMPENGINE%" "%ENGINE%" >nul
if errorlevel 1 (
  echo.
  echo [ERRO] Nao foi possivel substituir tools\public_beta.ps1.
  pause
  exit /b 32
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ENGINE%" -Action Update
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Atualizacao concluida.
) else (
  echo Atualizacao falhou com codigo %RC%.
)
echo.
pause
exit /b %RC%
