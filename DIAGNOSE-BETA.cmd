@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme Public Beta - Runtime Probe
echo ============================================================
echo  ASPHALT REXTREME - BETA RUNTIME PROBE
echo ============================================================
echo.
echo O jogo sera iniciado normalmente pelo registro UWP.
echo Quando ele fechar, o diagnostico sera gerado automaticamente.
echo O save nao sera alterado pelo probe.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\capture_beta_runtime.ps1" ^
  -ProjectRoot "%~dp0"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Probe terminou com codigo %RC%.
pause
exit /b %RC%
