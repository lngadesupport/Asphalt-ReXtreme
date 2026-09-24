@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "MAP=%TOOLS%\profile_phase61_garage_slot110_owner.py"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 61 GARAGE SLOT +0x110 OWNER
echo ============================================================
echo.
echo Esta fase NAO altera o AMS.exe.
echo Ela cruza os metodos da GS_Garage com os dispatchers
echo que fazem CALL virtual no slot +0x110.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/7a4158a6f2c283079dfa2d181f6ab5905b9be1a1/tools/profile_phase61_garage_slot110_owner.py" -o "%MAP%"
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
echo PHASE 61 OK
echo.
echo Relatorio:
echo   _PACKAGE_PHASE5\_PHASE61_GARAGE_SLOT110_OWNER\LATEST-PHASE61-GARAGE-SLOT110-OWNER.txt
echo.
echo O AMS.exe nao foi modificado.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 61 falhou.
echo O AMS.exe nao foi modificado.
pause
exit /b 1
