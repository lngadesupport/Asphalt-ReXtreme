@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Asphalt ReXtreme - Build Analyzer
echo ============================================
echo.
echo Este processo e SOMENTE LEITURA.
echo Ele nao modifica nem executa o jogo.
echo.

if not "%~1"=="" (
    set "GAME_DIR=%~1"
) else (
    echo Cole ou arraste aqui a pasta onde voce extraiu o APPX do Asphalt Xtreme.
    echo Depois pressione ENTER.
    echo.
    set /p "GAME_DIR=Pasta do jogo: "
)

set "GAME_DIR=%GAME_DIR:"=%"

if not exist "%GAME_DIR%\" (
    echo.
    echo ERRO: pasta nao encontrada:
    echo %GAME_DIR%
    echo.
    pause
    exit /b 2
)

echo.
echo Analisando:
echo %GAME_DIR%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\analyze_build.ps1" -GameDir "%GAME_DIR%" -OutDir "%~dp0analysis-output"

if errorlevel 1 (
    echo.
    echo A analise terminou com erro.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Analise concluida.
echo ============================================
echo.
echo Envie para o ChatGPT a pasta:
echo %~dp0analysis-output
echo.
echo Arquivos principais:
echo   summary.txt
echo   inventory.csv
echo   binary-hashes.csv
echo   keyword-hits.txt
echo.
pause
