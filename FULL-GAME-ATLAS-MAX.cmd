@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\full_game_atlas_max.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado em _PACKAGE_PHASE5.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ================================================================
echo  ASPHALT ReXTREME - FULL GAME ATLAS MAX
echo ================================================================
echo.
echo MODO MAXIMO:
echo   - AMS.exe inteiro
echo   - todas as funcoes detectaveis
echo   - todos CALL/JMP diretos
echo   - call graph global
echo   - imports
echo   - strings ASCII/UTF16
echo   - RTTI
echo   - vtables
echo   - endpoints/rede/gameplay
echo   - pacote _PACKAGE_PHASE5 inteiro
echo   - dump HEX de TODOS os corpos de funcao indexados
echo.
echo Esta fase NAO altera nenhum byte do jogo.
echo O processamento e grande, mas mostra progresso por etapas.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/451c3a114280561a4c91d95258d9710cf113b947/tools/full_game_atlas_max.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%MAP%" --project-root "%ROOT%" --dump-bodies
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%MAP%" --project-root "%ROOT%" --dump-bodies
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  FULL GAME ATLAS MAX OK
echo ================================================================
echo.
echo Resultado:
echo   _PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX
echo.
echo Para eu analisar primeiro, envie:
echo   _PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX\SUMMARY.json
echo   _PACKAGE_PHASE5\_FULL_GAME_ATLAS_MAX\ATLAS-SUMMARY.txt
echo.
echo Os arquivos grandes ficam ai, incluindo:
echo   FUNCTIONS.csv
echo   CALL_GRAPH.csv
echo   JUMP_GRAPH.csv
echo   RTTI.csv
echo   VTABLES.csv
echo   STRINGS.csv
echo   STRING_XREFS.csv
echo   PACKAGE_FILES.csv
echo   PACKAGE_ENDPOINT_REFS.csv
echo   FUNCTION_BODIES_HEX.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] FULL GAME ATLAS MAX falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
