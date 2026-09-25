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

$downloads=@(
  @{Commit="7238b98c42057bd6198a30ae22e656d43bac4e52"; Path="tools/rex_build_base.ps1"},
  @{Commit="b156c5ffecba2d15446d8484469e6965d563c12f"; Path="tools/rex_build_content.py"},
  @{Commit="35f33d2fc9e7ff1508469452d8de04b817878fc2"; Path="tools/rex_patch_frontend.py"},
  @{Commit="cdef500f4455c7e528697c131376c77879c35fc0"; Path="tools/rex_apply.ps1"},
  @{Commit="303a54870257f1dbe2b927ff2f3aa5a92788eb61"; Path="tools/rex_test.ps1"},
  @{Commit="86fcde70d0f409eeab8ba89939abce3eee9ce637"; Path="prebuilt/rex-campaign/IGPLib_x86.dll"},
  @{Commit="86fcde70d0f409eeab8ba89939abce3eee9ce637"; Path="prebuilt/rex-campaign/REPORT.json"}
)

foreach($x in $downloads){
  $dst=Join-Path $ProjectRoot ($x.Path-replace"/","\")
  $dir=Split-Path -Parent $dst
  if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}
  $url="https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/"+$x.Commit+"/"+$x.Path
  Write-Host ("[GET] "+$x.Path)
  & curl.exe -fL $url -o $dst
  if($LASTEXITCODE-ne0){throw "Download failed: $($x.Path)"}
}

$report=Get-Content -LiteralPath (Join-Path $ProjectRoot "prebuilt\rex-campaign\REPORT.json") -Raw | ConvertFrom-Json
$runtime=Join-Path $ProjectRoot "prebuilt\rex-campaign\IGPLib_x86.dll"
$actual=(Get-FileHash -LiteralPath $runtime -Algorithm SHA256).Hash.ToLowerInvariant()
$expected="47e800919eb462be2c12df77e536293c3f36358bd0d7a9ff40e4882d343bbf3b"
if(([string]$report.sha256).ToLowerInvariant()-ne$expected){
  throw "Published report hash mismatch"
}
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
