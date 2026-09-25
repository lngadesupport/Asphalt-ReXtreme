param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($ProjectRoot)){
  $ProjectRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}else{
  $ProjectRoot=$ProjectRoot.Trim().Trim('"').TrimEnd("\")
  $ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
}

$pkg=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$ams=Join-Path $pkg "AMS.exe"
$igp=Join-Path $pkg "IGPLib_x86.dll"
$manifest=Join-Path $pkg "AppxManifest.xml"
$apply=Join-Path $ProjectRoot "tools\rex_apply.ps1"

foreach($p in @($ams,$igp,$manifest,$apply)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectRoot ("_BETA_DIAGNOSTICS\rex-campaign-"+$stamp)
New-Item -ItemType Directory -Force -Path $backup|Out-Null
Copy-Item $ams (Join-Path $backup "AMS.before.bin") -Force
Copy-Item $igp (Join-Path $backup "IGPLib.before.bin") -Force

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $apply -ProjectRoot $ProjectRoot
if($LASTEXITCODE-ne0){throw "REX Campaign apply failed: $LASTEXITCODE"}

[xml]$mx=Get-Content -LiteralPath $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$app=$mx.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId=[string]$app.Id
$p=Get-AppxPackage -Name $name|Sort-Object Version -Descending|Select-Object -First 1
if(-not$p){throw "Package not registered: $name"}

Write-Host ""
Write-Host "Teste:"
Write-Host "  1. Gameloft -> lobby"
Write-Host "  2. abrir garagem"
Write-Host "  3. verificar se MONTAR aparece sem spinner"
Write-Host "  4. clicar MONTAR"
Write-Host ("Backup: "+$backup)
Write-Host "Abrindo jogo..."

Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\"+$p.PackageFamilyName+"!"+$appId)
