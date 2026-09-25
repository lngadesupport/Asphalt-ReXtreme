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
$runtime=Join-Path $ProjectRoot "prebuilt\rex-campaign\IGPLib_x86.dll"
$python=Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
$baseBuilder=Join-Path $ProjectRoot "tools\rex_build_base.ps1"
$contentBuilder=Join-Path $ProjectRoot "tools\rex_build_content.py"
$patcher=Join-Path $ProjectRoot "tools\rex_patch_frontend.py"
$sourceCatalog=Join-Path $pkg "CampaignCatalog.dat"
$newContent=Join-Path $pkg "CampaignContentV1.dat"

foreach($p in @($ams,$runtime,$python,$baseBuilder,$contentBuilder,$patcher,$sourceCatalog)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $baseBuilder -ProjectRoot $ProjectRoot
if($LASTEXITCODE-ne0){throw "REX base build failed: $LASTEXITCODE"}

$baseAms=Join-Path $ProjectRoot "_REX_BASE\AMS.exe"
if(-not(Test-Path -LiteralPath $baseAms -PathType Leaf)){throw "Missing: $baseAms"}

& $python $contentBuilder --source $sourceCatalog --output $newContent
if($LASTEXITCODE-ne0){throw "REX content build failed: $LASTEXITCODE"}

Copy-Item -LiteralPath $baseAms -Destination $ams -Force
Copy-Item -LiteralPath $runtime -Destination (Join-Path $pkg "IGPLib_x86.dll") -Force

& $python $patcher --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "REX frontend patch failed: $LASTEXITCODE"}

$runtimeHash=(Get-FileHash -LiteralPath (Join-Path $pkg "IGPLib_x86.dll") -Algorithm SHA256).Hash.ToLowerInvariant()
$amsHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
$contentHash=(Get-FileHash -LiteralPath $newContent -Algorithm SHA256).Hash.ToLowerInvariant()

$out=Join-Path $ProjectRoot "_TRACE_MONTAR\REX-CAMPAIGN-APPLY.json"
New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent)|Out-Null

[ordered]@{
  schema=1
  runtime="Rex Campaign Edition"
  original_code="frontend presentation only"
  previous_campaign_runtime_used=$false
  previous_campaign_adapters_used=$false
  phase2_used=$false
  network=$false
  multiplayer=$false
  state="CampaignStateV1.dat"
  content="CampaignContentV1.dat"
  runtime_sha256=$runtimeHash
  ams_sha256=$amsHash
  content_sha256=$contentHash
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $out -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " REX CAMPAIGN EDITION APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Original code: frontend presentation only"
Write-Host "Previous Campaign code: NONE"
Write-Host "Phase2: NOT USED"
Write-Host "Network: NONE"
Write-Host "Multiplayer: NONE"
Write-Host ("Runtime SHA256: "+$runtimeHash)
Write-Host ("AMS SHA256:     "+$amsHash)
Write-Host ("Content SHA256: "+$contentHash)
Write-Host ("Report: "+$out)
