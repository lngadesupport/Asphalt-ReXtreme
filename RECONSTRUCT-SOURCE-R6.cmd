@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r6.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R6
echo ================================================================
echo.
echo R6 TYPED LISTENER / LOCAL CRAFT TRANSACTION:
echo   - descarta falso positivo ESP+0x298 da R5
echo   - parte do ctor real de GS_Garage
echo   - rastreia this tipado ate GS_Garage+0x298
echo   - identifica ctor/vtable real do listener
echo   - classifica callback 0x0099E710
echo   - separa grafo estreito do caminho de sucesso
echo   - procura ownership/blueprint/profile/save
echo   - gera LocalCraftTransaction C++
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R5 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/3283b1907070ec1a280a258fec85d29f89c58ca9/tools/reconstruct_source_r6.py" -o "%GEN%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    py.exe -3 -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  py.exe -3 -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    python.exe -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  python.exe -u "%GEN%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  SOURCE RECONSTRUCTION R6 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r6\LOCAL_CRAFT_TRANSACTION.json
echo   src-reconstructed\docs\R6-LOCAL-CRAFT-TRANSACTION.md
echo.
echo Se aparecer Listener vtables maior que 0, envie tambem:
echo   src-reconstructed\reverse\r6\asm\
echo apenas os arquivos fn_*.asm.txt correspondentes aos candidatos TOP.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R6 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
