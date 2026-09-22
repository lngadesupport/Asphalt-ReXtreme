@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase59_virtual_dispatch_bridge.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 59 VIRTUAL DISPATCH BRIDGE
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela compara os CALLs virtuais dos dispatchers do botao
echo com o slot de vtable que contem o build_request_handler.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/38c7f9238aa3dfbb3e33ff651701a9fa00b22385/tools/profile_phase59_virtual_dispatch_bridge.py" -o "%MAP%"
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
echo PHASE 59 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE59_VIRTUAL_DISPATCH_BRIDGE\LATEST-PHASE59-VIRTUAL-DISPATCH-BRIDGE.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 59 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
