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
$garage=Join-Path $ProjectRoot "tools\campaign_frontend_garage_v1.py"
$career=Join-Path $ProjectRoot "tools\campaign_career_adapter_v3.py"
$careerV2=Join-Path $ProjectRoot "tools\campaign_career_adapter_v2.py"
$catalog=Join-Path $pkg "CampaignCatalog.dat"
$events=Join-Path $pkg "CampaignEvents.dat"
$manifest=Join-Path $pkg "AppxManifest.xml"

foreach($p in @($ams,$igp,$phase2,$core,$python,$boot,$garage,$career,$careerV2,$catalog,$events,$manifest)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectRoot ("_BETA_DIAGNOSTICS\frontend-only-garage-v1-"+$stamp)
New-Item -ItemType Directory -Force -Path $backup|Out-Null
Copy-Item $ams (Join-Path $backup "AMS.before.bin") -Force
Copy-Item $igp (Join-Path $backup "IGPLib.before.bin") -Force

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue

# Always rebuild this experiment from the clean Phase2 baseline.
Copy-Item $phase2 $ams -Force
Copy-Item $core $igp -Force

& $python $boot --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Frontend-Only Boot v1 apply failed: $LASTEXITCODE"}

& $python $garage --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Frontend-Only Garage v1 apply failed: $LASTEXITCODE"}

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

Write-Host ""
Write-Host "================================================================"
Write-Host " FRONTEND-ONLY V2: BOOT + GARAGE + OWNERSHIP + CAREER" -ForegroundColor Green
Write-Host "================================================================"
Write-Host ("AMS SHA256:  "+$amsHash)
Write-Host ("Core SHA256: "+$coreHash)
Write-Host ""
Write-Host "Authority:"
Write-Host "  Boot/Profile/Lobby : CampaignFrontendBridge"
Write-Host "  MONTAR             : CampaignGarageService"
Write-Host "  Ownership global   : CampaignSave (conditional ownership shim)"
Write-Host "  Career progression : Campaign Career v3 / CampaignSave"
Write-Host "  Race simulation/UI : original frontend/engine"
Write-Host ""
Write-Host "Retired from these routes:"
Write-Host "  CraftCar / remote request / GlobalSync ownership authority"
Write-Host "  unconditional 0x00E530E0 ownership replacement"
Write-Host ""
Write-Host "Teste:"
Write-Host "  1. entrar no lobby"
Write-Host "  2. abrir garagem"
Write-Host "  3. clicar MONTAR"
Write-Host "  4. sair/reentrar na garagem e conferir ownership"
Write-Host "  5. abrir modo carreira e iniciar uma corrida"
Write-Host "  6. concluir a corrida e conferir retorno/progresso"
Write-Host ""
Write-Host ("Backup anterior: "+$backup)
Write-Host "Abrindo jogo..."

Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\"+$p.PackageFamilyName+"!"+$appId)
