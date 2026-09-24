@echo off
setlocal
cd /d "%~dp0"

where dotnet >nul 2>nul
if errorlevel 1 (
  echo [ERROR] .NET 8 SDK nao encontrado.
  echo Instale o .NET 8 SDK para compilar o ReXtreme SDK.
  exit /b 1
)

echo ========================================
echo ReXtreme SDK - Windows x64 standalone
echo ========================================

if exist "dist\ReXtremeSDK" rmdir /s /q "dist\ReXtremeSDK"
mkdir "dist\ReXtremeSDK" >nul 2>nul

dotnet publish "ReXtremeSDK\ReXtremeSDK.csproj" ^
  -c Release ^
  -r win-x64 ^
  --self-contained true ^
  -p:PublishSingleFile=true ^
  -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o "dist\ReXtremeSDK"

if errorlevel 1 (
  echo [ERROR] Build falhou.
  exit /b 1
)

copy /y "ReXtremeSDK\README.md" "dist\ReXtremeSDK\README.txt" >nul

echo.
echo [OK] Executavel standalone:
echo %CD%\dist\ReXtremeSDK\ReXtremeSDK.exe
exit /b 0
