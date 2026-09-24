@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "GEN=%TOOLS%\reconstruct_source_r7.py"

echo ================================================================
echo  ASPHALT ReXTREME - SOURCE RECONSTRUCTION R7
echo ================================================================
echo.
echo R7 TYPED CRAFT LISTENER:
echo   - usa vtable FINAL GS_Garage+0x298 = 0x0186AC70
echo   - le o slot virtual +0x04 real
echo   - resolve adjustor thunk automaticamente
echo   - segue apenas o callback real de sucesso
echo   - procura ownership/blueprint/profile/save
echo   - decide se ja podemos preparar patch runtime
echo   - NAO altera AMS.exe
echo.

if not exist "%ROOT%\src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json" (
  echo [ERRO] src-reconstructed nao encontrado. Execute R1-R6 primeiro.
  pause
  exit /b 10
)

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 11
)

if not exist "%TOOLS%" mkdir "%TOOLS%"

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/81b33936da09ed4d1def71ff04b523b3c4088a2d/tools/reconstruct_source_r7.py" -o "%GEN%"
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
echo  SOURCE RECONSTRUCTION R7 OK
echo ================================================================
echo.
echo Envie:
echo   src-reconstructed\reverse\RECONSTRUCTION_MANIFEST.json
echo   src-reconstructed\reverse\r7\TYPED_LISTENER_CALLBACK.json
echo   src-reconstructed\docs\R7-TYPED-CRAFT-LISTENER.md
echo.
echo Se "Can prepare runtime patch: True", envie tambem:
echo   src-reconstructed\reverse\r7\asm\fn_*.asm.txt
echo correspondentes ao handler e aos candidatos TOP.
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Reconstruction R7 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
