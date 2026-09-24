@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

title Asphalt ReXtreme - Exportar Projeto Completo

echo ============================================================
echo  ASPHALT ReXTREME - EXPORTAR PROJETO COMPLETO
echo  Nenhum arquivo da pasta baseline sera excluido
echo ============================================================
echo.

for %%I in ("%CD%") do set "BASENAME=%%~nxI"
for %%I in ("%CD%\..") do set "PARENT=%%~fI"

for /f "usebackq delims=" %%T in (`powershell.exe -NoProfile -Command "(Get-Date).ToString('yyyyMMdd-HHmmss')"`) do set "STAMP=%%T"

set "REPOFILE=Asphalt-ReXtreme-GitHub-campaign-edition-win32-%STAMP%.zip"
set "REPOZIP=%PARENT%\%REPOFILE%"
set "OUTFILE=Asphalt-ReXtreme-PROJETO-COMPLETO-%STAMP%.tar"
set "OUT=%PARENT%\%OUTFILE%"
set "HASHFILE=%OUT%.sha256.txt"
set "INVENTORY=%PARENT%\Asphalt-ReXtreme-INVENTARIO-%STAMP%.txt"

echo Pasta do projeto:
echo   %CD%
echo.
echo Pacote final:
echo   %OUT%
echo.
echo IMPORTANTE:
echo   O pacote .tar sera criado FORA da pasta baseline.
echo   Assim ele nao inclui a si proprio durante a criacao.
echo.

where tar.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] tar.exe nao foi encontrado neste Windows.
  echo Instale/ative o tar do Windows ou use Windows 10/11 atualizado.
  pause
  exit /b 2
)

where curl.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] curl.exe nao foi encontrado neste Windows.
  pause
  exit /b 3
)

echo [1/4] Gerando inventario COMPLETO da pasta baseline...
(
  echo Asphalt ReXtreme - Inventario completo
  echo Gerado em: %DATE% %TIME%
  echo Pasta: %CD%
  echo.
  dir /a /s /b "%CD%"
) > "%INVENTORY%"

if errorlevel 1 (
  echo [ERRO] Falha ao gerar inventario.
  pause
  exit /b 4
)

echo [2/4] Baixando snapshot atual do branch campaign-edition-win32...
curl.exe -fL "https://github.com/lngadesupport/Asphalt-ReXtreme/archive/refs/heads/campaign-edition-win32.zip" -o "%REPOZIP%"
if errorlevel 1 (
  echo.
  echo [AVISO] Nao foi possivel baixar o snapshot do GitHub.
  echo O baseline local ainda sera empacotado integralmente.
  echo Criando marcador de falha no lugar do snapshot...
  > "%REPOZIP%.DOWNLOAD-FAILED.txt" echo Nao foi possivel baixar o snapshot GitHub em %DATE% %TIME%.
  set "REPOFILE=%REPOFILE%.DOWNLOAD-FAILED.txt"
)

echo [3/4] Empacotando TODO o baseline sem exclusoes...
echo Isso pode gerar um arquivo de varios GB.
echo.

tar.exe -cf "%OUT%" -C "%PARENT%" "%BASENAME%" "%REPOFILE%" "Asphalt-ReXtreme-INVENTARIO-%STAMP%.txt"
if errorlevel 1 (
  echo.
  echo [ERRO] tar.exe nao conseguiu concluir o pacote.
  echo Nenhum arquivo da pasta baseline foi apagado ou alterado.
  pause
  exit /b 5
)

echo [4/4] Calculando SHA-256 do pacote final...
powershell.exe -NoLogo -NoProfile -Command ^
  "$p='%OUT%'; $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant();" ^
  "('SHA256  '+$h+[Environment]::NewLine+'FILE    '+$p) | Set-Content -Encoding UTF8 -LiteralPath '%HASHFILE%';" ^
  "Write-Host ('SHA-256: '+$h)"

if errorlevel 1 (
  echo [AVISO] O pacote foi criado, mas o arquivo de hash falhou.
)

echo.
echo ============================================================
echo  EXPORTACAO CONCLUIDA
echo ============================================================
echo.
echo Pacote completo:
echo   %OUT%
echo.
echo Hash:
echo   %HASHFILE%
echo.
echo Inventario:
echo   %INVENTORY%
echo.
echo Snapshot GitHub:
echo   %REPOZIP%
echo.
echo A pasta baseline original NAO foi alterada nem limpa.
echo Nenhum arquivo do baseline foi excluido.
echo.
pause
exit /b 0
