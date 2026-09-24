@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme Public Beta - Fix Local Profile

set "PY=%~dp0runtime\python312-x86\python.exe"
set "TOOL=%~dp0tools\campaign_profile_adapter_v2.py"

echo ============================================================
echo  ASPHALT REXTREME - LOCAL PROFILE FIX V2
echo ============================================================
echo.
echo Este patch remove a autoridade do sync/cloud legado.
echo Global IsOnline continua FALSE.
echo O perfil usa validacao local e remove a tela de sync sem forcar GlobalSync amplo.
echo.

if not exist "%PY%" (
  echo [ERRO] Runtime Python do beta nao encontrado.
  echo Rode INSTALL-BETA.cmd ou UPDATE-BETA.cmd primeiro.
  pause
  exit /b 10
)
if not exist "%TOOL%" (
  echo [ERRO] campaign_profile_adapter_v1.py nao encontrado.
  echo Rode UPDATE-BETA.cmd primeiro.
  pause
  exit /b 11
)

taskkill /F /IM AMS.exe >nul 2>nul

"%PY%" "%TOOL%" --project-root "%~dp0."
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Perfil Campaign local aplicado.
  echo A tela "verificando perfil online" nao deve mais ser usada.
  echo Use PLAY-BETA.cmd para testar.
) else (
  echo Falha ao aplicar o Profile Adapter. Codigo %RC%.
)
echo.
pause
exit /b %RC%
