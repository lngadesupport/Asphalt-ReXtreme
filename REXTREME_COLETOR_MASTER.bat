@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Coletor Mestre

echo ============================================================
echo              ASPHALT REXTREME - COLETOR MESTRE
echo ============================================================
echo.
echo Este coletor foi feito para acompanhar o projeto inteiro.
echo Ele NAO modifica nem executa o jogo.
echo.
echo Modos:
echo   [1] COMPLETO SEGURO  - recomendado
echo       Coleta manifesto, inventario, hashes, binarios, configs,
echo       strings, URLs, economia, video, rede e metadados.
echo       Saves/perfis: somente inventario, sem copiar conteudo.
echo.
echo   [2] PROFUNDO
echo       Faz tudo do modo seguro e tambem copia snapshots de
echo       LocalState/RoamingState/Settings quando encontrados.
echo       Use quando estivermos analisando saves/perfis.
echo.
set /p "MODE_CHOICE=Escolha 1 ou 2 [1]: "
if "%MODE_CHOICE%"=="" set "MODE_CHOICE=1"
if "%MODE_CHOICE%"=="2" (
    set "COLLECT_MODE=Deep"
) else (
    set "COLLECT_MODE=Safe"
)

echo.
if not "%~1"=="" (
    set "GAME_DIR=%~1"
) else (
    if exist "%~dp0collector-last-path.txt" (
        set /p "LAST_PATH="<"%~dp0collector-last-path.txt"
        if exist "%LAST_PATH%\" (
            echo Ultima pasta usada:
            echo   %LAST_PATH%
            set /p "USE_LAST=Usar essa pasta? [S/n]: "
            if /I not "%USE_LAST%"=="N" set "GAME_DIR=%LAST_PATH%"
        )
    )
)

if not defined GAME_DIR (
    echo.
    echo Arraste a pasta EXTRAIDA do Asphalt Xtreme para esta janela
    echo ou cole o caminho abaixo.
    set /p "GAME_DIR=Pasta do jogo: "
)

set "GAME_DIR=%GAME_DIR:"=%"

if not exist "%GAME_DIR%\" (
    echo.
    echo ERRO: pasta nao encontrada:
    echo   %GAME_DIR%
    echo.
    pause
    exit /b 2
)

> "%~dp0collector-last-path.txt" echo %GAME_DIR%

echo.
echo Pasta:
echo   %GAME_DIR%
echo Modo:
echo   %COLLECT_MODE%
echo.
echo Iniciando coleta...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\rextreme_collect_master.ps1" ^
    -GameDir "%GAME_DIR%" ^
    -Mode "%COLLECT_MODE%" ^
    -OutputRoot "%~dp0collector-output"

set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo ============================================================
    echo A coleta terminou com erro. Codigo: %RC%
    echo Verifique o arquivo collector.log na pasta de saida.
    echo ============================================================
    echo.
    pause
    exit /b %RC%
)

echo.
echo ============================================================
echo COLETA CONCLUIDA
echo ============================================================
echo.
echo Abra:
echo   %~dp0collector-output
echo.
echo Envie no chat o arquivo ZIP mais recente:
echo   ReXtreme-Collector-*.zip
echo.
echo O mesmo BAT pode ser reutilizado em todas as etapas futuras.
echo.
pause
