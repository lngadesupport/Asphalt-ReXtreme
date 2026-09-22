@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r4.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R4
echo ================================================================
echo.
echo R4 BACKEND CONTRACT:
echo   - analisa o corpo real 0x009A4BB0
echo   - extrai campos do request (incluindo car_id)
echo   - resolve globals/chaves usados pelo result handler
echo   - mapeia status/error translation
echo   - gera OfflineCraftCarBackend C++
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R3 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/b6f8d6b3900044ed4019252716a62234b8c155d4/tools/reconstruct_source_r4.py" -o "%GEN%"
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
echo  SOURCE RECONSTRUCTION R4 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r4\CRAFTCAR_BACKEND_CONTRACT.json
echo   src-reconstructed\reverse\r4\EVIDENCE.txt
echo   src-reconstructed\docs\R4-CRAFTCAR-BACKEND-CONTRACT.md
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R4 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
