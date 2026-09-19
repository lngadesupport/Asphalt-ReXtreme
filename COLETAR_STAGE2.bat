@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo Asphalt ReXtreme - Stage 2 Collector
echo ============================================
echo.
echo Este script COPIA arquivos para analise.
echo Ele nao modifica o jogo.
echo.

if not "%~1"=="" (
  set "GAME_DIR=%~1"
) else (
  set /p "GAME_DIR=Pasta extraida do Asphalt Xtreme: "
)
set "GAME_DIR=%GAME_DIR:"=%"

if not exist "%GAME_DIR%\" (
  echo Pasta nao encontrada.
  pause
  exit /b 2
)

set "OUT=%~dp0stage2"
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"

for %%F in (
  "AppxManifest.xml"
  "Gameoptions_W8.json"
  "in-app-purchase_w8.1.xml"
  "AMS.exe"
  "InAppPurchaseComponentW8.dll"
  "IGPLib_x86.dll"
  "Microsoft.Live.dll"
  "Facebook.dll"
  "WCPToolkit.dll"
) do (
  if exist "%GAME_DIR%\%%~F" copy /y "%GAME_DIR%\%%~F" "%OUT%\" >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root='%GAME_DIR%'; $out='%OUT%';" ^
  "Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Name -match '(?i)(gameoptions|purchase|econom|currency|credit|token|save|profile|config|event|reward|garage)' -and $_.Length -lt 20MB } | ForEach-Object {" ^
  "  $rel=$_.FullName.Substring($root.Length).TrimStart('\');" ^
  "  $dst=Join-Path $out ('extra\'+$rel);" ^
  "  New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null;" ^
  "  Copy-Item -LiteralPath $_.FullName -Destination $dst -Force" ^
  "}"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path '%OUT%\*' -DestinationPath '%~dp0ReXtreme-stage2.zip' -Force"

echo.
echo Pronto:
echo %~dp0ReXtreme-stage2.zip
echo.
echo Envie esse ZIP no chat.
pause
