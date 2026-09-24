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
$phase2=Join-Path $ProjectRoot "_AMS_PHASE2\AMS.exe"
$core=Join-Path $ProjectRoot "prebuilt\campaign-core\IGPLib_x86.dll"
$python=Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
$tool=Join-Path $ProjectRoot "tools\campaign_offline_lobby_v6.py"
$manifest=Join-Path $pkg "AppxManifest.xml"

foreach($p in @($ams,$igp,$phase2,$core,$python,$tool,$manifest)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectRoot ("_BETA_DIAGNOSTICS\offline-v6-backup-"+$stamp)
New-Item -ItemType Directory -Force -Path $backup|Out-Null
Copy-Item $ams (Join-Path $backup "AMS.before.bin") -Force
Copy-Item $igp (Join-Path $backup "IGPLib.before.bin") -Force

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue
Copy-Item $phase2 $ams -Force
Copy-Item $core $igp -Force

& $python $tool --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Offline Lobby v6 apply failed: $LASTEXITCODE"}

[xml]$mx=Get-Content $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$app=$mx.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId=[string]$app.Id
$p=Get-AppxPackage -Name $name|Sort-Object Version -Descending|Select-Object -First 1
if(-not$p){throw "Package not registered"}

Write-Host ""
Write-Host "============================================================"
Write-Host " OFFLINE LOBBY V6 BASELINE READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Profile: local / Phase9-compatible"
Write-Host "Age/onboarding: local"
Write-Host "GS_MessagePopup: untouched"
Write-Host "Post-tutorial NO_INTERNET caller: bypassed"
Write-Host "Garage/Career/Upgrade/Store adapters: NOT APPLIED"
Write-Host ("Backup do build anterior: "+$backup)
Write-Host ""
Write-Host "Abrindo jogo..."

Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\"+$p.PackageFamilyName+"!"+$appId)
