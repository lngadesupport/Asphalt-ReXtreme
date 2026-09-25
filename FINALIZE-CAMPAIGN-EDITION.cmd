@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Asphalt ReXtreme - Rex Campaign Edition

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\rex_apply.ps1" -ProjectRoot "%~dp0"
set "RC=%ERRORLEVEL%"

if not "%REXTREME_NO_PAUSE%"=="1" pause
exit /b %RC%
