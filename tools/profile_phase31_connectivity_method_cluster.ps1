param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE31_CONNECTIVITY_METHOD_CLUSTER"
$out=Join-Path $outDir "LATEST-PHASE31-CONNECTIVITY-METHOD-CLUSTER.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$code=@"
using System;
using System.Collections.Generic;
public static class Fast31 {
  public static int[] FindPattern(byte[] d, byte[] p, int[] starts, int[] ends) {
    var r=new List<int>();
    for(int q=0;q<starts.Length;q++){
      int s=Math.Max(0,starts[q]),e=Math.Min(d.Length,ends[q]);
      for(int i=s;i<=e-p.Length;i++){
        if(d[i]!=p[0]) continue;
        bool ok=true;
        for(int j=1;j<p.Length;j++) if(d[i+j]!=p[j]){ok=false;break;}
        if(ok) r.Add(i);
      }
    }
    return r.ToArray();
  }
}
"@
Add-Type -TypeDefinition $code -Language CSharp

$fs=[IO.File]::OpenRead($ams);$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C;$pe=$br.ReadInt32()
  $fs.Position=$pe
  if($br.ReadUInt32()-ne0x4550){throw "Invalid PE"}
  $machine=$br.ReadUInt16();$nsec=$br.ReadUInt16()
  $fs.Position=$pe+20;$opt=$br.ReadUInt16()
  $fs.Position=$pe+24;$magic=$br.ReadUInt16()
  if($machine-ne0x14C -or $magic-ne0x10B){throw "Expected x86 PE32"}
  $fs.Position=$pe+24+28;$imageBase=$br.ReadUInt32()
  $secOff=$pe+24+$opt;$sections=@()
  for($i=0;$i-lt$nsec;$i++){
    $fs.Position=$secOff+40*$i
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vsize=$br.ReadUInt32();$vaddr=$br.ReadUInt32();$rawSize=$br.ReadUInt32();$raw=$br.ReadUInt32()
    $fs.Position=$secOff+40*$i+36;$chars=$br.ReadUInt32()
    $sections += [pscustomobject]@{Name=$name;VSize=$vsize;VA=$vaddr;RawSize=$rawSize;Raw=$raw;Chars=$chars}
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToVa([int]$off){
  foreach($s in $sections){
    $a=[int64]$s.Raw;$b=$a+[int64]$s.RawSize
    if([int64]$off-ge$a -and [int64]$off-lt$b){
      return [int64]$imageBase+[int64]$s.VA+([int64]$off-$a)
    }
  }
  return -1
}
function VaToFile([int64]$va){
  if($va-lt[int64]$imageBase){return -1}
  $rva=$va-[int64]$imageBase
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    $a=[int64]$s.VA
    if($rva-ge$a -and $rva-lt($a+$span)){
      return [int]([int64]$s.Raw+($rva-$a))
    }
  }
  return -1
}
function NearestPrologue([int]$off,[int]$back=0x1000){
  $lo=[Math]::Max(0,$off-$back)
  for($p=$off;$p-ge$lo+2;$p--){
    if($d[$p]-eq0x55 -and $d[$p+1]-eq0x8B -and $d[$p+2]-eq0xEC){return $p}
  }
  return -1
}
function HexCtx([int]$center,[int]$before=48,[int]$after=256){
  $a=[Math]::Max(0,$center-$before);$z=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$z;$o+=16){
    $take=[Math]::Min(16,$z-$o+1)
    $bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}
function DirectCallers([int]$targetOff){
  $tva=FileToVa $targetOff
  $r=New-Object Collections.Generic.List[object]
  foreach($s in $sections){
    if(($s.Chars-band0x20000000)-eq0){continue}
    $start=[int]$s.Raw;$end=[Math]::Min($d.Length,[int]([int64]$s.Raw+[int64]$s.RawSize))
    for($o=$start;$o-le$end-5;$o++){
      if($d[$o]-ne0xE8){continue}
      $sva=FileToVa $o;if($sva-lt0){continue}
      $rel=[BitConverter]::ToInt32($d,$o+1)
      if(([int64]$sva+5+[int64]$rel)-eq$tva){
        $r.Add([pscustomobject]@{Call=$o;Pro=(NearestPrologue $o)})
      }
    }
  }
  return $r.ToArray()
}
function ScanCalls([int]$start,[int]$len=0x180){
  $r=New-Object Collections.Generic.List[object]
  $end=[Math]::Min($d.Length-5,$start+$len)
  for($o=$start;$o-le$end;$o++){
    if($d[$o]-ne0xE8){continue}
    $sva=FileToVa $o;if($sva-lt0){continue}
    $rel=[BitConverter]::ToInt32($d,$o+1)
    $dest=VaToFile ([int64]$sva+5+[int64]$rel)
    if($dest-ge0){$r.Add([pscustomobject]@{Call=$o;Dest=$dest})}
  }
  return $r.ToArray()
}

$exec=@($sections|Where-Object{($_.Chars-band0x20000000)-ne0})
[int[]]$starts=@($exec|ForEach-Object{[int]$_.Raw})
[int[]]$ends=@($exec|ForEach-Object{[int]([Math]::Min($d.Length,[int64]$_.Raw+[int64]$_.RawSize))})

# Exact x86 pattern: mov ecx,[0193A56C] ; call rel32
[byte[]]$prefix=@(0x8B,0x0D,0x6C,0xA5,0x93,0x01,0xE8)
$hits=[Fast31]::FindPattern($d,$prefix,$starts,$ends)

$groups=@{}
foreach($h in $hits){
  $call=$h+6
  $src=FileToVa $call
  $rel=[BitConverter]::ToInt32($d,$call+1)
  $dest=VaToFile ([int64]$src+5+[int64]$rel)
  if($dest-lt0){continue}
  if(-not$groups.ContainsKey($dest)){$groups[$dest]=New-Object Collections.Generic.List[int]}
  $groups[$dest].Add($call)
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 31 - Connectivity Tracker Method Cluster"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ("mov ecx,[singleton]; call hits="+$hits.Count)
W ("Unique tracker method targets="+$groups.Count)
W ""

W "===== TRACKER METHOD TARGETS BY FREQUENCY ====="
foreach($kv in @($groups.GetEnumerator()|Sort-Object {$_.Value.Count} -Descending)){
  W ("TARGET=0x{0:X8} Calls={1}"-f$kv.Key,$kv.Value.Count)
  W ("CallSites="+(($kv.Value|Select-Object -First 40|ForEach-Object{("0x{0:X8}"-f$_)})-join", "))
}
W ""

$focus=@(
  0x008B7D70,0x008B7DB0,0x008B7DF0,
  0x0091A0F0,0x0091A270,0x0091A5E0,0x009192C0,
  0x008B8290,0x0091A350,0x0091A1B0,0x00919250,0x008B8460,
  0x008B7E20,0x0091A410,0x00919EC0,0x00919E50,
  0x008CEC50,0x0091BC10,0x0091BCA0,0x0091B170,
  0x00919FA0,0x0091B1E0,0x00919620,0x008B7AD0,
  0x008B7B10,0x008B83B0,0x0091B040,0x00919D90
)

W "===== METHOD BODIES ====="
foreach($t in $focus){
  if(-not$groups.ContainsKey($t)){continue}
  W ("--- TARGET 0x{0:X8} Calls={1} VA=0x{2:X8} ---"-f$t,$groups[$t].Count,(FileToVa $t))
  W (HexCtx $t 32 224)
  $inner=@(ScanCalls $t 0x180)
  W ("Rel32Calls="+$inner.Count)
  foreach($c in $inner){W (" call@0x{0:X8}->0x{1:X8}"-f$c.Call,$c.Dest)}
  W ""
}

W "===== CALLER CONTEXTS FOR TOP 3 ====="
foreach($t in @(0x008B7D70,0x008B7DB0,0x008B7DF0)){
  W ("--- TARGET 0x{0:X8} ---"-f$t)
  if($groups.ContainsKey($t)){
    foreach($c in $groups[$t]|Select-Object -First 40){
      W ("CALLSITE=0x{0:X8} callerPrologue=0x{1:X8}"-f$c,(NearestPrologue $c))
      W (HexCtx $c 32 48)
    }
  }
  W ""
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 31 CONNECTIVITY METHOD CLUSTER READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
