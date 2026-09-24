@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "TOOLS=%ROOT%\tools"
set "PATCH=%TOOLS%\profile_phase63_force_garage_slot14.ps1"

if not exist "%ROOT%\_PACKAGE_PHASE5\AMS.exe" (
  echo [ERRO] AMS.exe nao encontrado.
  pause
  exit /b 10
)
if not exist "%TOOLS%" mkdir "%TOOLS%"

echo ============================================================
echo  ASPHALT ReXTREME - PHASE 63 FORCE GARAGE SLOT +0x14
echo ============================================================
echo.
echo Patch focal:
echo   GarageBottomBarWidget click router
echo   JE skip +0x14  ^>  NOP NOP
echo.
echo IsOnline global continua FALSE.
echo.

curl.exe -fL "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/c2c79ea71b93baebc1296ac54d7b47ed29c9def9/tools/profile_phase63_force_garage_slot14.ps1" -o "%PATCH%"
if errorlevel 1 goto :fail

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PATCH%" -ProjectRoot "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo PHASE 63 OK
echo.
echo Agora execute:
echo   _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
echo.
echo No jogo, clique MONTAR uma vez.
pause
exit /b 0

:fail
echo.
echo [ERRO] Phase 63 falhou.
echo Nenhum teste deve ser feito ate corrigirmos o erro acima.
pause
exit /b 1
