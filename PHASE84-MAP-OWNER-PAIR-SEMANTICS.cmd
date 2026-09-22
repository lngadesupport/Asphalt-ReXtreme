@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase84_owner_pair_semantics.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 84 OWNER PAIR SEMANTICS
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Ela classifica writers de +0x354/+0x358 como:
echo   ZERO_INIT / CONST_INIT / ARG_COPY / CALL_RETURN / REG_COPY
echo e prioriza padroes reais de shared_ptr.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/ce2011c12b84a5b78fb39cb22cd58976ce09e442/tools/profile_phase84_owner_pair_semantics.py" -o "%MAP%"
if errorlevel 1 goto :fail

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -u "%MAP%" --project-root "%ROOT%"
  if errorlevel 1 goto :fail
  goto :ok
)

echo [ERRO] Python 3 nao encontrado.
goto :fail

:ok
echo.
echo PHASE 84 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE84_OWNER_PAIR_SEMANTICS\LATEST-PHASE84-OWNER-PAIR-SEMANTICS.txt
echo   _PACKAGE_PHASE5\_PHASE84_OWNER_PAIR_SEMANTICS\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 84 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
