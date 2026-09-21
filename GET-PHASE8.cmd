@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Asphalt ReXtreme - Get Phase 8 Files

if not exist "tools" mkdir "tools"

set "BASE=https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/campaign-edition-win32"

echo [1/4] profile_phase8_embed.ps1
curl.exe -fL "%BASE%/tools/profile_phase8_embed.ps1" -o "tools\profile_phase8_embed.ps1" || goto :fail

echo [2/4] profile_phase8_runtime.ps1
curl.exe -fL "%BASE%/tools/profile_phase8_runtime.ps1" -o "tools\profile_phase8_runtime.ps1" || goto :fail

echo [3/4] BUILD-PROFILE-PHASE8-EMBEDDED.cmd
curl.exe -fL "%BASE%/BUILD-PROFILE-PHASE8-EMBEDDED.cmd" -o "BUILD-PROFILE-PHASE8-EMBEDDED.cmd" || goto :fail

echo [4/4] RUN-CAMPAIGN-PHASE8.cmd
curl.exe -fL "%BASE%/RUN-CAMPAIGN-PHASE8.cmd" -o "RUN-CAMPAIGN-PHASE8.cmd" || goto :fail

for %%F in (
  "tools\profile_phase8_embed.ps1"
  "tools\profile_phase8_runtime.ps1"
  "BUILD-PROFILE-PHASE8-EMBEDDED.cmd"
  "RUN-CAMPAIGN-PHASE8.cmd"
) do (
  if not exist %%F (
    echo [ERRO] Arquivo ausente: %%F
    goto :fail
  )
)

echo.
echo ============================================================
echo  PHASE 8 FILES READY
echo ============================================================
echo Execute agora:
echo   BUILD-PROFILE-PHASE8-EMBEDDED.cmd
echo.
pause
exit /b 0

:fail
echo.
echo [ERRO] Nao foi possivel preparar todos os arquivos da Phase 8.
echo.
pause
exit /b 1
