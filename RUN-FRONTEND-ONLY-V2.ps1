param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($ProjectRoot)){
  $ProjectRoot=(Get-Location).Path
}else{
  $ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
}

$raw="https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme"
$files=@(
  @{Commit="f87c87f03fb493e232ab0d196887323522ba7f74"; Path="tools/campaign_frontend_boot_v1.py"},
  @{Commit="47639fcc57ded4c234c300e847b5d5b8aa27f824"; Path="tools/campaign_frontend_garage_v2.py"},
  @{Commit="d9ad618f0255ebd8f90a213f914f9e185103f7c1"; Path="tools/test_frontend_only_v2.ps1"},
  @{Commit="4cd77ca30e43796c925eff48df961d166ad63457"; Path="tools/campaign_career_adapter_v3.py"},
  @{Commit="e20ac2b853e71220e4eb2ef66bd3c77872cc0ff6"; Path="tools/campaign_career_adapter_v2.py"},
  @{Commit="3119bf76252cc9a011f73e15f331156df2945c8a"; Path="prebuilt/campaign-core/IGPLib_x86.dll"}
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
$expected="35ee95c2d63143e62a30abc4ddea57ec2a5fa9288a456523d9d3fc273ec102a7"
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
Write-Host ""

& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "tools\test_frontend_only_v2.ps1") -ProjectRoot $ProjectRoot
exit $LASTEXITCODE
