param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE29_CONNECTIVITY_METHODS"
$out=Join-Path $outDir "LATEST-PHASE29-CONNECTIVITY-METHODS.txt"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$code=@"
using System;
using System.Collections.Generic;
public static class FastScan {
  public static int[] Find(byte[] data, byte[] needle) {
    var r=new List<int>();
    if (needle==null || needle.Length==0 || data.Length<needle.Length) return r.ToArray();
    byte first=needle[0];
    for(int i=0;i<=data.Length-needle.Length;i++){
      if(data[i]!=first) continue;
      bool ok=true;
      for(int j=1;j<needle.Length;j++){ if(data[i+j]!=needle[j]){ok=false;break;} }
      if(ok){ r.Add(i); i+=needle.Length-1; }
    }
    return r.ToArray();
  }
  public static int[] FindDword(byte[] data, uint value) {
    var r=new List<int>();
    byte b0=(byte)(value & 0xff), b1=(byte)((value>>8)&0xff), b2=(byte)((value>>16)&0xff), b3=(byte)((value>>24)&0xff);
    for(int i=0;i<=data.Length-4;i++){
      if(data[i]==b0 && data[i+1]==b1 && data[i+2]==b2 && data[i+3]==b3) r.Add(i);
    }
    return r.ToArray();
  }
}
"@
Add-Type -TypeDefinition $code -Language CSharp

# Parse PE32.
$fs=[IO.File]::OpenRead($ams);$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C;$pe=$br.ReadInt32()
  $fs.Position=$pe
  if($br.ReadUInt32()-ne0x00004550){throw "Invalid PE signature"}
  $machine=$br.ReadUInt16();$nsec=$br.ReadUInt16()
  $fs.Position=$pe+20;$opt=$br.ReadUInt16()
  $fs.Position=$pe+24;$magic=$br.ReadUInt16()
  if($machine-ne0x014C -or $magic-ne0x10B){throw "Expected x86 PE32"}
  $fs.Position=$pe+24+28;$imageBase=$br.ReadUInt32()
  $secOff=$pe+24+$opt
  $sections=@()
  for($i=0;$i-lt$nsec;$i++){
    $fs.Position=$secOff+40*$i
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vsize=$br.ReadUInt32();$vaddr=$br.ReadUInt32();$rawSize=$br.ReadUInt32();$raw=$br.ReadUInt32()
    $fs.Position=$secOff+40*$i+36;$chars=$br.ReadUInt32()
    $sections += [pscustomobject]@{Name=$name;VSize=$vsize;VA=$vaddr;RawSize=$rawSize;Raw=$raw;Chars=$chars}
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToRva([int]$off){
  foreach($s in $sections){
    $raw=[int64]$s.Raw;$end=$raw+[int64]$s.RawSize
    if([int64]$off-ge$raw -and [int64]$off-lt$end){return [int64]$s.VA+([int64]$off-$raw)}
  }
  return -1
}
function FileToVa([int]$off){
  $r=FileToRva $off
  if($r-lt0){return -1}
  return [int64]$imageBase+$r
}
function VaToFile([int64]$va){
  if($va-lt[int64]$imageBase){return -1}
  $rva=$va-[int64]$imageBase
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    $start=[int64]$s.VA
    if($rva-ge$start -and $rva-lt($start+$span)){return [int]([int64]$s.Raw+($rva-$start))}
  }
  return -1
}
function IsExec([int]$off){
  foreach($s in $sections){
    $raw=[int64]$s.Raw;$end=$raw+[int64]$s.RawSize
    if([int64]$off-ge$raw -and [int64]$off-lt$end){return (($s.Chars-band0x20000000)-ne0)}
  }
  return $false
}
function NearestPrologue([int]$off,[int]$back=0x1000){
  $lo=[Math]::Max(0,$off-$back)
  for($p=$off;$p-ge$lo+2;$p--){
    if($d[$p]-eq0x55 -and $d[$p+1]-eq0x8B -and $d[$p+2]-eq0xEC){return $p}
  }
  return -1
}
function HexCtx([int]$center,[int]$before=48,[int]$after=320){
  $a=[Math]::Max(0,$center-$before);$z=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$z;$o+=16){
    $take=[Math]::Min(16,$z-$o+1)
    $bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}
function DirectCallsTo([int]$targetOff){
  $tva=FileToVa $targetOff
  if($tva-lt0){return @()}
  $res=New-Object Collections.Generic.List[object]
  foreach($s in $sections){
    if(($s.Chars-band0x20000000)-eq0){continue}
    $start=[int]$s.Raw;$end=[Math]::Min($d.Length,[int]($s.Raw+$s.RawSize))
    for($o=$start;$o-le$end-5;$o++){
      if($d[$o]-ne0xE8){continue}
      $sva=FileToVa $o
      if($sva-lt0){continue}
      $rel=[BitConverter]::ToInt32($d,$o+1)
      $dest=[int64]$sva+5+[int64]$rel
      if($dest-eq$tva){
        $res.Add([pscustomobject]@{Call=$o;Prologue=(NearestPrologue $o)})
      }
    }
  }
  return $res.ToArray()
}
function ScanFuncCalls([int]$start,[int]$maxLen=0x500){
  $res=New-Object Collections.Generic.List[object]
  $end=[Math]::Min($d.Length-5,$start+$maxLen)
  for($o=$start;$o-le$end;$o++){
    if($d[$o]-ne0xE8){continue}
    $sva=FileToVa $o
    if($sva-lt0){continue}
    $rel=[BitConverter]::ToInt32($d,$o+1)
    $dest=[int64]$sva+5+[int64]$rel
    $fo=VaToFile $dest
    if($fo-ge0){$res.Add([pscustomobject]@{Call=$o;Dest=$fo})}
  }
  return $res.ToArray()
}
function Fmt([int]$x){
  if($x-ge0){return ("0x{0:X8}"-f$x)}
  return "N/A"
}

$known=@{
  0x00B989D0="WinRT wrapper A"
  0x00B9A100="WinRT wrapper B"
  0x00D2DEA0="WinRT wrapper C"
  0x00D2E320="WinRT InternetAccess predicate"
  0x00E07C40="WinRT wrapper D"
  0x00E0E490="WinRT parent"
  0x00BACDD0="global IsOnline"
}

$ctorRef=0x00874418
$ctor=NearestPrologue $ctorRef 0x800
if($ctor-lt0){$ctor=0x008743E0}
$targets=@(
  [pscustomobject]@{Name="AVAsphaltConnectivityTracker-constructor";Off=$ctor},
  [pscustomobject]@{Name="vmethod-primary-0";Off=0x008962B0},
  [pscustomobject]@{Name="vmethod-secondary-0";Off=0x009C9240},
  [pscustomobject]@{Name="vmethod-secondary-1";Off=0x0098CF80}
)

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 29 - Connectivity Tracker Methods v2"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ""

foreach($t in $targets){
  $va=FileToVa $t.Off
  W ("===== {0} file=0x{1:X8} VA=0x{2:X8} ====="-f$t.Name,$t.Off,$va)
  W (HexCtx $t.Off 48 320)
  W ""
  $calls=@(DirectCallsTo $t.Off)
  W ("DirectCallers="+$calls.Count)
  foreach($c in $calls){
    W ("CALL file=0x{0:X8} callerPrologue={1}"-f$c.Call,(Fmt $c.Prologue))
  }
  W ""
  $sub=@(ScanFuncCalls $t.Off 0x500)
  W ("Rel32CallsWithin500="+$sub.Count)
  foreach($c in $sub){
    $tag=""
    if($known.ContainsKey($c.Dest)){$tag=" *** "+$known[$c.Dest]}
    W (" call@0x{0:X8} -> file=0x{1:X8}{2}"-f$c.Call,$c.Dest,$tag)
  }
  W ""
}

W "===== VFTABLE IMMEDIATE REFERENCES ====="
foreach($vf in @(
  [pscustomobject]@{VA=[uint32]0x0185FF40;Name="primary"},
  [pscustomobject]@{VA=[uint32]0x0185FF48;Name="secondary"}
)){
  $refs=@([FastScan]::FindDword($d,$vf.VA)|Where-Object{IsExec $_})
  W ("{0} vftable VA=0x{1:X8} executable immediate refs={2}"-f$vf.Name,$vf.VA,$refs.Count)
  foreach($r in $refs){
    W (" ref=0x{0:X8} prologue={1}"-f$r,(Fmt (NearestPrologue $r)))
  }
  W ""
}

W "===== CONNECTIVITY STATE OFFSET CANDIDATES ====="
foreach($disp in @(0xB8,0xC0,0xC4,0xC8,0xD0,0xD4,0xD8,0xDC)){
  [byte[]]$pat=[BitConverter]::GetBytes([uint32]$disp)
  $all=[FastScan]::Find($d,$pat)
  $groups=@{}
  foreach($r in $all){
    if(-not(IsExec $r)){continue}
    $p=NearestPrologue $r 0x500
    if($p-lt0){continue}
    if(-not$groups.ContainsKey($p)){$groups[$p]=New-Object Collections.Generic.List[int]}
    $groups[$p].Add($r)
  }
  W ("+0x{0:X2}: functions={1}"-f$disp,$groups.Count)

  $rows=New-Object Collections.Generic.List[object]
  foreach($p in $groups.Keys){
    $tags=New-Object Collections.Generic.List[string]
    foreach($c in (ScanFuncCalls ([int]$p) 0x400)){
      if($known.ContainsKey($c.Dest)){$tags.Add($known[$c.Dest])}
    }
    $near=0
    foreach($t in $targets){
      if([Math]::Abs([int64]$p-[int64]$t.Off)-lt0x20000){$near=1;break}
    }
    $score=0
    if($tags.Count-gt0){$score+=10}
    if($near){$score+=5}
    if($score-gt0){
      $rows.Add([pscustomobject]@{Score=$score;Prologue=[int]$p;Refs=$groups[$p];Tags=$tags})
    }
  }
  foreach($row in @($rows|Sort-Object Score -Descending|Select-Object -First 24)){
    $refs=($row.Refs|Select-Object -First 8|ForEach-Object{("0x{0:X8}"-f$_)})-join","
    $tags="-"
    if($row.Tags.Count-gt0){$tags=($row.Tags-join";")}
    W ("  func=0x{0:X8} refs={1} tags={2}"-f$row.Prologue,$refs,$tags)
  }
  W ""
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 29 CONNECTIVITY METHODS READY (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
