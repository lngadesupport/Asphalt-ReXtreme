@echo off
setlocal EnableExtensions
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\read_garage_ui_trace.ps1" -ProjectRoot "%ROOT%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
