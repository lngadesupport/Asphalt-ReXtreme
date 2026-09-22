@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r5.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R5
echo ================================================================
echo.
echo R5 SUCCESS / PROFILE TRACE:
echo   - resolve keys de sync do CraftCar result
echo   - trace callback 0x0099E710
echo   - trace helper 0x009A4440
echo   - procura vtable do listener GS_Garage+0x298
echo   - segue success graph ate perfil/ownership/save
echo   - gera candidatos de mutacao com evidencia
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R4 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/4de4f3aa3bca37aa1b95ab18056a47cf3044f4f2/tools/reconstruct_source_r5.py" -o "%GEN%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import capstone" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencia Python: capstone
    py.exe -3 -m pip install --user capstone
    if errorlevel 1 goto :fail
  )
  py.exe -3 -u "%GEN%" --project-root "%ROOT%" --max-depth 10 --max-nodes 10000
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
  python.exe -u "%GEN%" --project-root "%ROOT%" --max-depth 10 --max-nodes 10000
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo ================================================================
echo  SOURCE RECONSTRUCTION R5 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r5\SUCCESS_CALLBACK_GRAPH.json
echo   src-reconstructed\docs\R5-CRAFTCAR-SUCCESS-PROFILE.md
echo.
echo Se existir e for pequeno, envie tambem o ASM do candidato TOP em:
echo   src-reconstructed\reverse\r5\asm\
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R5 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
