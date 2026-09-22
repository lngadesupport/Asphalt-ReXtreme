@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase76_delegate_registration.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 76 DELEGATE REGISTRATION
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela compara o registro do build_button com os callbacks irmaos
echo e abre a cadeia:
echo   0x0096E4B0 -> 0x0096E2D0 -> 0x00905680 -> 0x009077D0
echo para descobrir onde o handle/contexto do clique e mantido.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/9f77505ebc24bebe91caf159805fe3fc2c3f4fe9/tools/profile_phase76_delegate_registration.py" -o "%MAP%"
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
echo PHASE 76 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE76_DELEGATE_REGISTRATION\LATEST-PHASE76-DELEGATE-REGISTRATION.txt
echo   _PACKAGE_PHASE5\_PHASE76_DELEGATE_REGISTRATION\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 76 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
