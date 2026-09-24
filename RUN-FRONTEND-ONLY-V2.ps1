param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($ProjectRoot)){
  $ProjectRoot=(Get-Location).Path

  if(-not(Test-Path -LiteralPath (Join-Path $ProjectRoot "_PACKAGE_PHASE5\AMS.exe") -PathType Leaf)){
    $leaf=Split-Path -Leaf $ProjectRoot
    $nested=Join-Path $ProjectRoot $leaf
    if(Test-Path -LiteralPath (Join-Path $nested "_PACKAGE_PHASE5\AMS.exe") -PathType Leaf){
      $ProjectRoot=(Resolve-Path -LiteralPath $nested).Path
      Write-Host ("[AUTO] Project root detected: "+$ProjectRoot) -ForegroundColor Yellow
    }
  }
}else{
  $ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
}

if(-not(Test-Path -LiteralPath (Join-Path $ProjectRoot "_PACKAGE_PHASE5\AMS.exe") -PathType Leaf)){
  throw "Project root invalid: _PACKAGE_PHASE5\AMS.exe not found under $ProjectRoot"
}

$raw="https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme"
$files=@(
  @{Commit="f87c87f03fb493e232ab0d196887323522ba7f74"; Path="tools/campaign_frontend_boot_v1.py"},
  @{Commit="47639fcc57ded4c234c300e847b5d5b8aa27f824"; Path="tools/campaign_frontend_garage_v2.py"},
  @{Commit="ce29e56bf81f0d185a08bb922f01aa19101c5424"; Path="tools/test_frontend_only_v2.ps1"},
  @{Commit="4cd77ca30e43796c925eff48df961d166ad63457"; Path="tools/campaign_career_adapter_v3.py"},
  @{Commit="e20ac2b853e71220e4eb2ef66bd3c77872cc0ff6"; Path="tools/campaign_career_adapter_v2.py"},
  @{Commit="e9b74d4acfb10b61031032603b441d3348a00618"; Path="tools/read_garage_trace.ps1"},
  @{Commit="8af8ad7e3dc124536159bb9bebf1550e1768581a"; Path="prebuilt/campaign-core/IGPLib_x86.dll"},
  @{Commit="9a912f2335ed1eb6cc61f568916862a602865fa8"; Path="config/OFFLINE-AUTHORITY.json"},
  @{Commit="ae1e424688ee2040b0da19f6af75f78adb57b5fb"; Path="tools/audit_offline_authority.py"},
  @{Commit="ac1d30cc3e0e347d482b1d33ed2968d2d48aedbd"; Path="tools/map_online_surface.py"}
)

foreach($f in $files){
  $dst=Join-Path $ProjectRoot ($f.Path -replace '/','\')
  $dir=Split-Path -Parent $dst
  New-Item -ItemType Directory -Force -Path $dir|Out-Null
  $tmp=$dst+".download"
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  $url=$raw+"/"+$f.Commit+"/"+$f.Path
  Write-Host ("[GET] "+$f.Path)
  & curl.exe -fL --retry 3 -H "Cache-Control: no-cache" $url -o $tmp
  if($LASTEXITCODE-ne0){throw "Download failed: $($f.Path)"}
  Move-Item -LiteralPath $tmp -Destination $dst -Force
}

$core=Join-Path $ProjectRoot "prebuilt\campaign-core\IGPLib_x86.dll"
$expected="e59505ff5be8990a77457e1e18a0f6cb7920d7e973ba990a55e21a3244df4cfd"
$got=(Get-FileHash -LiteralPath $core -Algorithm SHA256).Hash.ToLowerInvariant()
if($got-ne$expected){
  throw "Campaign Core SHA256 mismatch. Expected $expected got $got"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " CAMPAIGN FRONTEND-ONLY V2 PAYLOAD READY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ("Campaign Core SHA256: "+$got)
Write-Host "Generic ownership primitive: untouched"
Write-Host "Startup authority: CampaignStartupService"
Write-Host "Garage authority: CampaignGarageService"
Write-Host "Career authority: Campaign Career v3"
Write-Host "Network authority: hard denied"
Write-Host "Multiplayer: not allowed in Campaign Edition"
Write-Host "Feature policy: local-only"
Write-Host ""

$python=Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
if(Test-Path -LiteralPath $python -PathType Leaf){
  & $python (Join-Path $ProjectRoot "tools\audit_offline_authority.py") --project-root $ProjectRoot
  if($LASTEXITCODE-ne0){throw "Offline authority audit failed: $LASTEXITCODE"}

  & $python (Join-Path $ProjectRoot "tools\map_online_surface.py") --project-root $ProjectRoot
  if($LASTEXITCODE-ne0){throw "Online surface map failed: $LASTEXITCODE"}
}

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "tools\test_frontend_only_v2.ps1") -ProjectRoot $ProjectRoot
exit $LASTEXITCODE
