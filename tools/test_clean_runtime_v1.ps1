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
$runtime=Join-Path $ProjectRoot "prebuilt\campaign-runtime\IGPLib_x86.dll"
$python=Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
$shell=Join-Path $ProjectRoot "tools\campaign_frontend_shell_v1.py"
$catalog=Join-Path $pkg "CampaignCatalog.dat"
$manifest=Join-Path $pkg "AppxManifest.xml"

foreach($p in @($ams,$igp,$phase2,$runtime,$python,$shell,$catalog,$manifest)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectRoot ("_BETA_DIAGNOSTICS\clean-runtime-v1-"+$stamp)
New-Item -ItemType Directory -Force -Path $backup|Out-Null
Copy-Item $ams (Join-Path $backup "AMS.before.bin") -Force
Copy-Item $igp (Join-Path $backup "IGPLib.before.bin") -Force

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue

# Clean baseline: no transitional Boot/Garage/Career adapters are applied.
Copy-Item $phase2 $ams -Force
Copy-Item $runtime $igp -Force

& $python $shell --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Clean Frontend Shell v1 failed: $LASTEXITCODE"}

$runtimeHash=(Get-FileHash -LiteralPath $igp -Algorithm SHA256).Hash.ToLowerInvariant()
$amsHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[xml]$mx=Get-Content $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$app=$mx.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId=[string]$app.Id
$p=Get-AppxPackage -Name $name|Sort-Object Version -Descending|Select-Object -First 1
if(-not$p){throw "Package not registered"}

Write-Host ""
Write-Host "================================================================"
Write-Host " CLEAN CAMPAIGN RUNTIME V1" -ForegroundColor Green
Write-Host "================================================================"
Write-Host ("AMS SHA256:     "+$amsHash)
Write-Host ("Runtime SHA256: "+$runtimeHash)
Write-Host ""
Write-Host "Original code allowed:"
Write-Host "  frontend/render/widgets/assets only"
Write-Host ""
Write-Host "Original gameplay structures:"
Write-Host "  NONE"
Write-Host ""
Write-Host "MONTAR:"
Write-Host "  frontend click -> BUILD_SELECTED_CAR -> Runtime V1 -> save -> view model"
Write-Host "  no GS_Garage / no CraftCar / no signal / no completion / no server"
Write-Host ""
Write-Host "State:"
Write-Host "  CampaignRuntimeV1.dat"
Write-Host ""
Write-Host ("Backup anterior: "+$backup)
Write-Host "Abrindo jogo..."

Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\"+$p.PackageFamilyName+"!"+$appId)
