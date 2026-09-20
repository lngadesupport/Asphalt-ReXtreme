@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "GAME=%~1"
if "%GAME%"=="" set "GAME=%CD%"

echo ============================================================
echo Asphalt ReXtreme - Unified Diagnostic
echo ============================================================
echo.
echo Game root:
echo %GAME%
echo.
echo This is ONE diagnostic pass:
echo   - build integrity and key hashes
echo   - PE imports/exports for core binaries
echo   - Store/UWP/XAML/ad/IAP references
echo   - Windows/package/runtime state
echo   - AMS.exe execution
echo   - loaded modules
echo   - WER crash dump
echo   - Application/AppModel/TWinUI events
echo   - one final ZIP
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0tools\unified_diagnostic.ps1" ^
  -GameRoot "%GAME%"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Diagnostic returned code %RC%.
pause
exit /b %RC%
