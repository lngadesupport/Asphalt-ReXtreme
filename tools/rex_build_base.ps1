param([string]$ProjectRoot=".")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$OriginalHash="3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8"
$OnlineOffset=0x00BACDD0
[byte[]]$Expected=0x8A,0x81,0xB0,0x04,0x00,0x00,0xC3
[byte[]]$Offline =0x31,0xC0,0xC3,0x90,0x90,0x90,0x90

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$out=Join-Path $ProjectRoot "_REX_BASE"
New-Item -ItemType Directory -Force -Path $out|Out-Null

$matches=@()
Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Filter AMS.exe -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    if(-not $_.FullName.StartsWith($out,[StringComparison]::OrdinalIgnoreCase)){
      try{
        $h=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if($h-eq$OriginalHash){$matches+=$_.FullName}
      }catch{}
    }
  }

if($matches.Count-ne1){
  throw "Need exactly one pristine AMS.exe ($OriginalHash); found $($matches.Count)."
}

[byte[]]$d=[IO.File]::ReadAllBytes($matches[0])
for($i=0;$i-lt$Expected.Length;$i++){
  if($d[$OnlineOffset+$i]-ne$Expected[$i]){
    throw ("Pristine connectivity bytes differ at 0x{0:X8}" -f $OnlineOffset)
  }
}
[Array]::Copy($Offline,0,$d,$OnlineOffset,$Offline.Length)

$dst=Join-Path $out "AMS.exe"
[IO.File]::WriteAllBytes($dst,$d)
$hash=(Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()

[ordered]@{
  schema=1
  product="Asphalt ReXtreme Campaign Edition"
  source="pristine AMS.exe"
  source_sha256=$OriginalHash
  output_sha256=$hash
  changes=@("IsOnline hard FALSE")
  gameplay_patches=0
  old_adapter_patches=0
}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $out "REPORT.json") -Encoding UTF8

Write-Host "[OK] REX base built from pristine AMS."
Write-Host ("[HASH] "+$hash)
