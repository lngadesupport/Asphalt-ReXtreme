@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase79_fixed_ecx_owner_flow.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 79 FIXED ECX OWNER FLOW
echo ============================================================
echo.
echo Esta fase NAO altera gameplay.
echo Corrige o bug da Phase 78: quando GS_Garage+0x35C ja e
echo carregado diretamente em ECX, o CALL thiscall agora e seguido
echo mesmo sem um mov ecx,reg extra.
echo Tambem rastreia o padrao vtable -> call [vtable+slot].
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c08932ba93b7bf73b6c30fb35f988fce57d46a29/tools/profile_phase79_fixed_ecx_owner_flow.py" -o "%MAP%"
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
echo PHASE 79 OK
echo.
echo NAO ABRA O JOGO AINDA.
echo.
echo Envie:
echo   _PACKAGE_PHASE5\_PHASE79_FIXED_ECX_OWNER_FLOW\LATEST-PHASE79-FIXED-ECX-OWNER-FLOW.txt
echo   _PACKAGE_PHASE5\_PHASE79_FIXED_ECX_OWNER_FLOW\SUMMARY.json
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 79 falhou.
echo Nenhum byte de gameplay deveria ter sido alterado.
pause
exit /b 1
