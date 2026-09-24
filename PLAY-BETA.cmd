@echo off
setlocal
cd /d "%~dp0"
title Asphalt ReXtreme 0.1.0-beta.1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\public_beta.ps1" -Action Play
exit /b %ERRORLEVEL%
