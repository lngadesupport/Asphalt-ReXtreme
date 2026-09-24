param([string]$ProjectRoot=".")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ExpectedOriginal="3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8"
$OnlineOffset=0x00BACDD0
[byte[]]$OnlineBefore=0x8A,0x81,0xB0,0x04,0x00,0x00,0xC3
[byte[]]$OnlineAfter =0x31,0xC0,0xC3,0x90,0x90,0x90,0x90

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$outDir=Join-Path $ProjectRoot "_AMS_CLEAN_BASE"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null

$candidates=@(Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File -Filter "AMS.exe" -ErrorAction SilentlyContinue |
  Where-Object { -not $_.FullName.StartsWith($outDir,[StringComparison]::OrdinalIgnoreCase) })

$matches=@()
foreach($c in $candidates){
  try{
    $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $c.FullName).Hash.ToLowerInvariant()
    if($h-eq$ExpectedOriginal){$matches+=$c}
  }catch{}
}
if($matches.Count-ne1){
  throw "Expected exactly one pristine AMS.exe ($ExpectedOriginal); found $($matches.Count)."
}

$src=$matches[0].FullName
[byte[]]$data=[IO.File]::ReadAllBytes($src)

for($i=0;$i-lt$OnlineBefore.Length;$i++){
  if($data[$OnlineOffset+$i]-ne$OnlineBefore[$i]){
    throw ("Connectivity boundary mismatch at 0x{0:X8}" -f $OnlineOffset)
  }
}
[Array]::Copy($OnlineAfter,0,$data,$OnlineOffset,$OnlineAfter.Length)

$dst=Join-Path $outDir "AMS.exe"
[IO.File]::WriteAllBytes($dst,$data)
$hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash.ToLowerInvariant()

[ordered]@{
  schema=1
  phase="Clean AMS Base V1"
  source_sha256=$ExpectedOriginal
  output_sha256=$hash
  original_gameplay_patches=0
  premium_reward_trampoline=$false
  race_payout_hooks=$false
  ads_flow_patches=$false
  store_flow_patches=$false
  network_authority=$false
  only_patch="central connectivity hard FALSE"
} | ConvertTo-Json | Set-Content (Join-Path $outDir "CLEAN-BASE-REPORT.json") -Encoding UTF8

Write-Host "[OK] Clean AMS Base V1 built."
Write-Host ("[SOURCE] "+$ExpectedOriginal)
Write-Host ("[OUTPUT] "+$hash)
Write-Host "[OLD GAMEPLAY PATCHES] NONE"
