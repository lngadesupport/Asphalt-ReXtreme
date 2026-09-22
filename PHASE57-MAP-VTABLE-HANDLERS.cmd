@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase57_vtable_handler_map.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 57 VTABLE / HANDLER MAP
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela identifica qual variante de classe usa o botao MONTAR
echo e desmonta os handlers equivalentes das duas vtables.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/b224bbe4ac32308ec56e369608a144777f7bcece/tools/profile_phase57_vtable_handler_map.py" -o "%MAP%"
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
echo PHASE 57 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE57_VTABLE_HANDLER_MAP\LATEST-PHASE57-VTABLE-HANDLER-MAP.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 57 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
