param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

function Resolve-Root([string]$candidate){
  if([string]::IsNullOrWhiteSpace($candidate)){$candidate=(Get-Location).Path}
  $candidate=$candidate.Trim().Trim('"').TrimEnd("\")
  $root=(Resolve-Path -LiteralPath $candidate).Path

  if((Test-Path -LiteralPath (Join-Path $root "_PACKAGE_PHASE5\AMS.exe") -PathType Leaf) -and
     (Test-Path -LiteralPath (Join-Path $root "runtime\python312-x86\python.exe") -PathType Leaf)){
    return $root
  }

  $hits=Get-ChildItem -LiteralPath $root -Recurse -Filter AMS.exe -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq "_PACKAGE_PHASE5" }
  $valid=@()
  foreach($h in $hits){
    $r=$h.Directory.Parent.FullName
    if(Test-Path -LiteralPath (Join-Path $r "runtime\python312-x86\python.exe") -PathType Leaf){
      $valid+=$r
    }
  }
  $valid=@($valid|Select-Object -Unique)
  if($valid.Count-eq1){return $valid[0]}
  throw "Could not resolve Campaign project root."
}

$ProjectRoot=Resolve-Root $ProjectRoot
Write-Host ("[ROOT] "+$ProjectRoot)

$base="https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/public-beta-0.1/"
$files=@(
  "tools/rex_build_base.ps1",
  "tools/rex_build_content.py",
  "tools/rex_patch_frontend.py",
  "tools/rex_apply.ps1",
  "tools/rex_test.ps1",
  "prebuilt/rex-campaign/IGPLib_x86.dll",
  "prebuilt/rex-campaign/REPORT.json"
)

foreach($rel in $files){
  $dst=Join-Path $ProjectRoot ($rel-replace"/","\")
  $dir=Split-Path -Parent $dst
  if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}
  Write-Host ("[GET] "+$rel)
  & curl.exe -fL ($base+$rel) -o $dst
  if($LASTEXITCODE-ne0){throw "Download failed: $rel"}
}

$report=Get-Content -LiteralPath (Join-Path $ProjectRoot "prebuilt\rex-campaign\REPORT.json") -Raw | ConvertFrom-Json
$runtime=Join-Path $ProjectRoot "prebuilt\rex-campaign\IGPLib_x86.dll"
$actual=(Get-FileHash -LiteralPath $runtime -Algorithm SHA256).Hash.ToLowerInvariant()
$expected=([string]$report.sha256).ToLowerInvariant()
if($actual-ne$expected){throw "Runtime hash mismatch: $actual expected $expected"}

Write-Host ""
Write-Host "============================================================"
Write-Host " REX CAMPAIGN EDITION - NEW CODE ONLY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Original gameplay code: NONE"
Write-Host "Previous Campaign code: NONE"
Write-Host "Original allowed surface: frontend presentation only"
Write-Host "Network: NONE"
Write-Host "Multiplayer: NONE"
Write-Host ("Runtime SHA256: "+$actual)
Write-Host ""

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "tools\rex_test.ps1") -ProjectRoot $ProjectRoot
if($LASTEXITCODE-ne0){throw "REX Campaign test failed: $LASTEXITCODE"}
