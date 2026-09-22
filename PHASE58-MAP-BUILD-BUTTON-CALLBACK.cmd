@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase58_build_button_callback.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 58 ACTUAL BUILD_BUTTON CALLBACK
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo.
echo Alvo confirmado pela registracao do build_button:
echo   callback VA 0x00973C90
echo.
echo Ela compara tambem os callbacks vizinhos 0x00973D20
echo e 0x00973E40 para identificar o fluxo especifico do MONTAR.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/f4eddad52738c46e3318188fd0b73e79845c54f7/tools/profile_phase58_build_button_callback.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :done
)

where python.exe >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado.
  pause
  exit /b 11
)

python.exe "%MAP%" --project-root "%ROOT%"
if errorlevel 1 goto :fail

:done
echo.
echo PHASE 58 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE58_BUILD_BUTTON_CALLBACK\LATEST-PHASE58-BUILD-BUTTON-CALLBACK.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 58 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
