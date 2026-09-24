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
$boot=Join-Path $ProjectRoot "tools\campaign_frontend_boot_v1.py"
$garage=Join-Path $ProjectRoot "tools\campaign_frontend_garage_v3.py"
$career=Join-Path $ProjectRoot "tools\campaign_career_adapter_v3.py"
$careerV2=Join-Path $ProjectRoot "tools\campaign_career_adapter_v2.py"
$catalog=Join-Path $pkg "CampaignCatalog.dat"
$events=Join-Path $pkg "CampaignEvents.dat"
$manifest=Join-Path $pkg "AppxManifest.xml"

foreach($p in @($ams,$igp,$phase2,$core,$python,$boot,$garage,$career,$careerV2,$catalog,$events,$manifest)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectRoot ("_BETA_DIAGNOSTICS\frontend-only-v2-"+$stamp)
New-Item -ItemType Directory -Force -Path $backup|Out-Null
Copy-Item $ams (Join-Path $backup "AMS.before.bin") -Force
Copy-Item $igp (Join-Path $backup "IGPLib.before.bin") -Force

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue

Copy-Item $phase2 $ams -Force
Copy-Item $core $igp -Force

& $python $boot --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Frontend-Only Boot apply failed: $LASTEXITCODE"}

& $python $garage --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Frontend-Only Garage v3 apply failed: $LASTEXITCODE"}

& $python $career --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Campaign Career v3 apply failed: $LASTEXITCODE"}

$coreHash=(Get-FileHash -LiteralPath $igp -Algorithm SHA256).Hash.ToLowerInvariant()
$amsHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[xml]$mx=Get-Content $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$app=$mx.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId=[string]$app.Id
$p=Get-AppxPackage -Name $name|Sort-Object Version -Descending|Select-Object -First 1
if(-not$p){throw "Package not registered"}

$garageTrace=Join-Path $env:LOCALAPPDATA ("Packages\"+$p.PackageFamilyName+"\LocalState\CampaignEdition\GarageTrace.bin")
$garageUiTrace=Join-Path $env:LOCALAPPDATA ("Packages\"+$p.PackageFamilyName+"\LocalState\CampaignEdition\GarageUiTrace.bin")
Remove-Item -LiteralPath $garageTrace -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $garageUiTrace -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "================================================================"
Write-Host " FRONTEND-ONLY V2: STARTUP + GARAGE + CAREER" -ForegroundColor Green
Write-Host "================================================================"
Write-Host ("AMS SHA256:  "+$amsHash)
Write-Host ("Core SHA256: "+$coreHash)
Write-Host ""
Write-Host "Startup:"
Write-Host "  Gameloft splash      : frontend visual only"
Write-Host "  Startup state        : CampaignStartupService"
Write-Host "  Profile              : local"
Write-Host "  Lobby                : local"
Write-Host ""
Write-Host "Garage:"
Write-Host "  MONTAR               : direct local button callback -> CampaignGarageService"
Write-Host "  Ownership authority  : CampaignSave"
Write-Host "  Ownership API        : CampaignFrontendIsOwned(car_id)"
Write-Host "  async build signal   : BYPASSED"
Write-Host ""
Write-Host "Career:"
Write-Host "  Race/UI              : preserved frontend/engine"
Write-Host "  Progress/rewards     : Campaign Career v3"
Write-Host ("  Garage trace         : "+$garageTrace)
Write-Host ("  Garage UI trace      : "+$garageUiTrace)
Write-Host ""
Write-Host "Teste:"
Write-Host "  1. passar da tela Gameloft"
Write-Host "  2. chegar ao lobby"
Write-Host "  3. abrir garagem e clicar MONTAR"
Write-Host "  4. abrir carreira, iniciar e concluir uma corrida"
Write-Host ""
Write-Host ("Backup anterior: "+$backup)
Write-Host "Abrindo jogo..."

Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\"+$p.PackageFamilyName+"!"+$appId)
