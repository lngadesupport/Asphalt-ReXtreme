param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE33_CONNECTIVITY_STATE_MACHINE"
$out=Join-Path $outDir "LATEST-PHASE33-CONNECTIVITY-STATE-MACHINE.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

function ReadBytes([int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{
    $fs.Position=$Offset
    [byte[]]$b=New-Object byte[] $Count
    if($fs.Read($b,0,$Count)-ne$Count){throw ("Short read at 0x{0:X8}"-f$Offset)}
    return $b
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# Normalize Phase32 experiment back to original.
$phase32Off=0x0098CF80
[byte[]]$phase32Orig=@(0x33,0xC0,0x39,0x41,0x5C,0x0F,0x95,0xC0,0xC3)
[byte[]]$phase32Patch=@(0xB0,0x01,0xC3,0x90,0x90,0x90,0x90,0x90,0x90)
$cur=ReadBytes $phase32Off 9
$normalized=$false
if(Same $cur $phase32Patch){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{
    $fs.Position=$phase32Off
    $fs.Write($phase32Orig,0,$phase32Orig.Length)
    $fs.Flush($true)
  }finally{$fs.Dispose()}
  $normalized=$true
}elseif(-not(Same $cur $phase32Orig)){
  throw ("Unexpected Phase32 site bytes: "+(Hex $cur))
}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

function HexCtx([int]$center,[int]$before=64,[int]$after=256){
  $a=[Math]::Max(0,$center-$before);$z=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$z;$o+=16){
    $take=[Math]::Min(16,$z-$o+1)
    $bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 33 - Connectivity State Machine Focus"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("Phase32Normalized="+$normalized)
W ""

$regions=@(
  [pscustomobject]@{Name="state-machine-A";Start=0x00641580;Len=0x700},
  [pscustomobject]@{Name="tracker-byte-status-family";Start=0x008CEC20;Len=0x140},
  [pscustomobject]@{Name="tracker-event-family-1";Start=0x00919E20;Len=0x1E0},
  [pscustomobject]@{Name="tracker-event-family-2";Start=0x0091A0D0;Len=0x450},
  [pscustomobject]@{Name="tracker-dispatch-helpers";Start=0x008B7D40;Len=0x900}
)

foreach($r in $regions){
  W ("===== {0} start=0x{1:X8} len=0x{2:X} ====="-f$r.Name,$r.Start,$r.Len)
  W (HexCtx ($r.Start+64) 64 ($r.Len-64))
  W ""
}

# Highlight the exact known singleton callsites and the bytes immediately after them.
$callsites=@(
  0x006416E6,0x006416F1,0x00641766,0x00641A71,
  0x00646E4D,0x006470F2,0x00647331,
  0x0092B868
)
W "===== EXACT CALLSITE WINDOWS ====="
foreach($c in $callsites){
  W ("--- callsite=0x{0:X8} ---"-f$c)
  W (HexCtx $c 48 96)
  W ""
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 33 CONNECTIVITY STATE MACHINE READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
