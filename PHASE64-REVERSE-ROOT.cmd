@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase64_reverse_root.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 64 REVERSE ROOT
echo ============================================================
echo.
echo Esta fase:
echo   1. Reverte apenas a Phase 63, se estiver ativa.
echo   2. Mantem Phase 53/54/55 e IsOnline global FALSE.
echo   3. Faz o caminho inverso:
echo      CraftCar ^< build handler ^< vtable +0x110 ^< delegates/callbacks.
echo   4. Cruza esse caminho com template_build_button/build_button.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/e7847375dd3a44fd31527c739d21af68564ed6ee/tools/profile_phase64_reverse_root.py" -o "%MAP%"
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
echo PHASE 64 OK
echo.
echo Relatorios:
echo   _PACKAGE_PHASE5\_PHASE64_REVERSE_ROOT\LATEST-PHASE64-REVERSE-ROOT.txt
echo   _PACKAGE_PHASE5\_PHASE64_REVERSE_ROOT\SUMMARY.json
echo.
echo NAO abra o jogo ainda.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 64 falhou.
echo O script so reverte a Phase 63 se os guards estiverem corretos.
pause
exit /b 1
