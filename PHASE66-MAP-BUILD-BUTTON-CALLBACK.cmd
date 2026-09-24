@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase66_build_button_callback_binding.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 66 CALLBACK BINDING MAP
echo ============================================================
echo.
echo Esta fase:
echo   - desfaz somente a Phase 65, se ela estiver ativa
echo   - volta ao SHA estavel da Phase 64
echo   - mapeia callback/owner do build_button
echo   - NAO adiciona novo patch de gameplay
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/abaad6dc7d0855b60c20d09b43ee1daf78828de2/tools/profile_phase66_build_button_callback_binding.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 66 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie este arquivo:
echo   _PACKAGE_PHASE5\_PHASE66_BUILD_BUTTON_CALLBACK_BINDING\LATEST-PHASE66-BUILD-BUTTON-CALLBACK-BINDING.txt
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 66 falhou.
echo Nada novo deve ser testado no jogo.
pause
exit /b 1
