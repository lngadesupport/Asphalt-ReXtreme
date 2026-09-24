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
$cleanBase=Join-Path $ProjectRoot "_AMS_CLEAN_BASE\AMS.exe"
$cleanBaseBuilder=Join-Path $ProjectRoot "tools\build_clean_ams_base_v1.ps1"
$runtime=Join-Path $ProjectRoot "prebuilt\campaign-runtime\IGPLib_x86.dll"
$python=Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
$shell=Join-Path $ProjectRoot "tools\campaign_frontend_shell_v1.py"
$catalog=Join-Path $pkg "CampaignCatalog.dat"

foreach($p in @($ams,$igp,$runtime,$python,$shell,$catalog,$cleanBaseBuilder)){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing: $p"}
}

Get-Process AMS -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $cleanBaseBuilder -ProjectRoot $ProjectRoot
if($LASTEXITCODE-ne0){throw "Clean AMS Base V1 build failed: $LASTEXITCODE"}
if(-not(Test-Path -LiteralPath $cleanBase -PathType Leaf)){throw "Missing: $cleanBase"}

Copy-Item $cleanBase $ams -Force
Copy-Item $runtime $igp -Force

& $python $shell --project-root $ProjectRoot
if($LASTEXITCODE-ne0){throw "Clean Frontend Shell v1 failed: $LASTEXITCODE"}

$runtimeHash=(Get-FileHash -LiteralPath $igp -Algorithm SHA256).Hash.ToLowerInvariant()
$amsHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$out=Join-Path $ProjectRoot "_TRACE_MONTAR\CLEAN-RUNTIME-V1-APPLY.json"
New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent)|Out-Null
[ordered]@{
  schema=1
  runtime="Campaign Runtime V1"
  frontend_only_original_code=$true
  original_gameplay_structures=$false
  legacy_adapters_used=$false
  phase2_used=$false
  clean_base="_AMS_CLEAN_BASE\\AMS.exe"
  runtime_sha256=$runtimeHash
  ams_sha256=$amsHash
  state="CampaignRuntimeV1.dat"
} | ConvertTo-Json | Set-Content -LiteralPath $out -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " CLEAN CAMPAIGN RUNTIME V1 APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Runtime SHA256: "+$runtimeHash)
Write-Host ("AMS SHA256:     "+$amsHash)
Write-Host "Original gameplay structures: NONE"
Write-Host "Legacy adapters used: NONE"
Write-Host ("Report: "+$out)
