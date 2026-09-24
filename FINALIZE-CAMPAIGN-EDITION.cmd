@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Clean Campaign Runtime V1

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\apply_clean_runtime_v1.ps1" -ProjectRoot "%~dp0"
set "RC=%ERRORLEVEL%"

if not "%REXTREME_NO_PAUSE%"=="1" pause
exit /b %RC%
