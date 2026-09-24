param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

function Resolve-ProjectRoot([string]$candidate){
  if([string]::IsNullOrWhiteSpace($candidate)){
    $candidate=(Get-Location).Path
  }
  $candidate=$candidate.Trim().Trim('"').TrimEnd("\")
  $root=(Resolve-Path -LiteralPath $candidate).Path

  if(Test-Path -LiteralPath (Join-Path $root "_PACKAGE_PHASE5\AMS.exe") -PathType Leaf){
    return $root
  }

  $hits=Get-ChildItem -LiteralPath $root -Recurse -Filter AMS.exe -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq "_PACKAGE_PHASE5" }

  $valid=@()
  foreach($h in $hits){
    $r=$h.Directory.Parent.FullName
    if((Test-Path -LiteralPath (Join-Path $r "_AMS_PHASE2\AMS.exe") -PathType Leaf) -and
       (Test-Path -LiteralPath (Join-Path $r "_PACKAGE_PHASE5\AppxManifest.xml") -PathType Leaf)){
      $valid += $r
    }
  }

  $valid=@($valid | Select-Object -Unique)
  if($valid.Count-eq1){return $valid[0]}
  if($valid.Count-gt1){throw "Multiple project roots found: $($valid -join '; ')"}
  throw "Project root invalid: could not find _PACKAGE_PHASE5\AMS.exe and _AMS_PHASE2\AMS.exe"
}

$ProjectRoot=Resolve-ProjectRoot $ProjectRoot
Write-Host ("[ROOT] "+$ProjectRoot)

$downloads=@(
  @{Commit="d9af0f8d60b0c75e973d3e5a2682b5ee05ea1a90"; Path="tools/campaign_frontend_shell_v1.py"},
  @{Commit="b5dc2cf5d2415e8a153905d70b6437aa71bfb329"; Path="tools/test_clean_runtime_v1.ps1"},
  @{Commit="2b87ade3bc712196ad7e419ce7fcffe608a948da"; Path="prebuilt/campaign-runtime/IGPLib_x86.dll"}
)

foreach($x in $downloads){
  $dst=Join-Path $ProjectRoot ($x.Path -replace "/","\")
  $dir=Split-Path -Parent $dst
  if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}

  $url="https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/"+$x.Commit+"/"+$x.Path
  Write-Host ("[GET] "+$x.Path)
  & curl.exe -fL $url -o $dst
  if($LASTEXITCODE-ne0){throw "Download failed: $($x.Path)"}
}

$runtime=Join-Path $ProjectRoot "prebuilt\campaign-runtime\IGPLib_x86.dll"
$expected="c5dd3133ae5856fc9fec58fcd94182deca2a83ce690eea3a1849cd1cc3d15a44"
$actual=(Get-FileHash -LiteralPath $runtime -Algorithm SHA256).Hash.ToLowerInvariant()
if($actual-ne$expected){
  throw "Campaign Runtime hash mismatch: $actual expected $expected"
}

Write-Host ""
Write-Host "============================================================"
Write-Host " CLEAN CAMPAIGN RUNTIME V1 READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Runtime SHA256: "+$actual)
Write-Host "Original gameplay structures: NONE"
Write-Host "Original allowed surface: frontend only"
Write-Host "Network: NONE"
Write-Host "Multiplayer: NONE"
Write-Host "Legacy adapters: NOT USED"
Write-Host ""

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "tools\test_clean_runtime_v1.ps1") -ProjectRoot $ProjectRoot
if($LASTEXITCODE-ne0){throw "Clean Runtime V1 test failed: $LASTEXITCODE"}
