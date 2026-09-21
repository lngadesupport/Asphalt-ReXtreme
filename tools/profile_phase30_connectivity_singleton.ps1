param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE30_CONNECTIVITY_SINGLETON"
$out=Join-Path $outDir "LATEST-PHASE30-CONNECTIVITY-SINGLETON.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$code=@"
using System;
using System.Collections.Generic;

public static class FastScan30V3 {
  public static int[] FindDword(byte[] d, uint v) {
    var r=new List<int>();
    byte a=(byte)v,b=(byte)(v>>8),c=(byte)(v>>16),e=(byte)(v>>24);
    for(int i=0;i<=d.Length-4;i++)
      if(d[i]==a && d[i+1]==b && d[i+2]==c && d[i+3]==e) r.Add(i);
    return r.ToArray();
  }

  public static int[] FindPatternInRanges(byte[] d, byte[] p, int[] starts, int[] ends) {
    var r=new List<int>();
    if(p==null || p.Length==0) return r.ToArray();
    for(int q=0;q<starts.Length;q++) {
      int s=Math.Max(0,starts[q]), e=Math.Min(d.Length,ends[q]);
      int last=e-p.Length;
      for(int i=s;i<=last;i++) {
        if(d[i]!=p[0]) continue;
        bool ok=true;
        for(int j=1;j<p.Length;j++) if(d[i+j]!=p[j]) {ok=false;break;}
        if(ok) r.Add(i);
      }
    }
    return r.ToArray();
  }

  // Output flattened triples: callFileOffset, targetIndex, reserved.
  public static int[] FindCallsToTargets(
      byte[] d, int[] starts, int[] ends, long[] startVAs, long[] targets) {
    var r=new List<int>();
    var map=new Dictionary<long,int>();
    for(int i=0;i<targets.Length;i++) map[targets[i]]=i;

    for(int q=0;q<starts.Length;q++) {
      int s=Math.Max(0,starts[q]), e=Math.Min(d.Length,ends[q]);
      long baseVA=startVAs[q];
      for(int o=s;o<=e-5;o++) {
        if(d[o]!=0xE8) continue;
        int rel=BitConverter.ToInt32(d,o+1);
        long src=baseVA+(o-s);
        long dest=src+5L+rel;
        int idx;
        if(map.TryGetValue(dest,out idx)) {
          r.Add(o); r.Add(idx); r.Add(0);
        }
      }
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
  $secOff=$pe+24+$opt;$sections=@()
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
    $a=[int64]$s.Raw;$b=$a+[int64]$s.RawSize
    if([int64]$off-ge$a -and [int64]$off-lt$b){return [int64]$s.VA+([int64]$off-$a)}
  }
  return -1
}
function FileToVa([int]$off){
  $r=FileToRva $off
  if($r-lt0){return -1}
  return [int64]$imageBase+$r
}
function NearestPrologue([int]$off,[int]$back=0x1200){
  $lo=[Math]::Max(0,$off-$back)
  for($p=$off;$p-ge$lo+2;$p--){
    if($d[$p]-eq0x55 -and $d[$p+1]-eq0x8B -and $d[$p+2]-eq0xEC){return $p}
  }
  return -1
}
function HexCtx([int]$center,[int]$before=64,[int]$after=160){
  $a=[Math]::Max(0,$center-$before);$z=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$z;$o+=16){
    $take=[Math]::Min(16,$z-$o+1)
    $bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}
function Fmt([int]$x){
  if($x-ge0){return ("0x{0:X8}"-f$x)}
  return "N/A"
}

# Build executable ranges once.
$exec=@($sections|Where-Object{($_.Chars-band0x20000000)-ne0})
[int[]]$execStarts=@($exec|ForEach-Object{[int]$_.Raw})
[int[]]$execEnds=@($exec|ForEach-Object{[int]([Math]::Min($d.Length,[int64]$_.Raw+[int64]$_.RawSize))})
[long[]]$execStartVAs=@($exec|ForEach-Object{[int64]$imageBase+[int64]$_.VA})

$singleton=[uint32]0x0193A56C
$allSingletonRefs=[FastScan30V3]::FindDword($d,$singleton)
$refs=New-Object Collections.Generic.List[int]
foreach($r in $allSingletonRefs){
  for($q=0;$q-lt$execStarts.Length;$q++){
    if($r-ge$execStarts[$q] -and $r-lt$execEnds[$q]){$refs.Add($r);break}
  }
}

$funcMap=@{}
foreach($r in $refs){
  $p=NearestPrologue $r
  if(-not$funcMap.ContainsKey($p)){$funcMap[$p]=New-Object Collections.Generic.List[int]}
  $funcMap[$p].Add($r)
}

# Build one target set: all singleton-ref functions + creation owner.
$creator=0x00BA6FB0
$targetFuncs=New-Object Collections.Generic.List[int]
foreach($p in @($funcMap.Keys|Sort-Object)){if([int]$p-ge0){$targetFuncs.Add([int]$p)}}
if(-not($targetFuncs.Contains($creator))){$targetFuncs.Add($creator)}

[long[]]$targetVAs=@($targetFuncs|ForEach-Object{[int64](FileToVa $_)})
$callFlat=[FastScan30V3]::FindCallsToTargets($d,$execStarts,$execEnds,$execStartVAs,$targetVAs)
$callers=@{}
for($i=0;$i-lt$targetFuncs.Count;$i++){$callers[$targetFuncs[$i]]=New-Object Collections.Generic.List[object]}
for($i=0;$i-lt$callFlat.Length;$i+=3){
  $call=[int]$callFlat[$i];$idx=[int]$callFlat[$i+1];$target=$targetFuncs[$idx]
  $callers[$target].Add([pscustomobject]@{Call=$call;Prologue=(NearestPrologue $call)})
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 30 - AVAsphaltConnectivityTracker Singleton v3 FAST"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ("SingletonVA=0x{0:X8}"-f$singleton)
W ("ExecutableImmediateRefs="+$refs.Count)
W ("UniqueFunctions="+$funcMap.Count)
W ""

W "===== SINGLETON REFERENCES ====="
foreach($p in @($funcMap.Keys|Sort-Object)){
  $rs=$funcMap[$p]
  W ("--- function={0} refs={1} ---"-f(Fmt ([int]$p)),$rs.Count)
  foreach($r in $rs){
    $b0=0;$b1=0
    if($r-ge2){$b0=$d[$r-2];$b1=$d[$r-1]}
    W ("REF file=0x{0:X8} prev2={1:X2} {2:X2}"-f$r,$b0,$b1)
    W (HexCtx $r 48 112)
  }
  if([int]$p-ge0){
    $cs=$callers[[int]$p]
    W ("DirectCallersToFunction="+$cs.Count)
    foreach($c in $cs){W (" CALL=0x{0:X8} callerPrologue={1}"-f$c.Call,(Fmt $c.Prologue))}
  }
  W ""
}

$getter=0x0098CF80
W "===== TRACKER +0x5C BOOLEAN VIRTUAL GETTER ====="
W ("GetterFile=0x{0:X8} GetterVA=0x{1:X8}"-f$getter,(FileToVa $getter))
W (HexCtx $getter 32 64)
W ""

$patterns=@(
  [pscustomobject]@{Name="cmp dword [ecx+5C],0";Bytes=[byte[]](0x83,0x79,0x5C,0x00)},
  [pscustomobject]@{Name="cmp dword [esi+5C],0";Bytes=[byte[]](0x83,0x7E,0x5C,0x00)},
  [pscustomobject]@{Name="cmp dword [edi+5C],0";Bytes=[byte[]](0x83,0x7F,0x5C,0x00)},
  [pscustomobject]@{Name="mov eax,[ecx+5C]";Bytes=[byte[]](0x8B,0x41,0x5C)},
  [pscustomobject]@{Name="mov ecx,[ecx+5C]";Bytes=[byte[]](0x8B,0x49,0x5C)},
  [pscustomobject]@{Name="mov eax,[esi+5C]";Bytes=[byte[]](0x8B,0x46,0x5C)},
  [pscustomobject]@{Name="mov eax,[edi+5C]";Bytes=[byte[]](0x8B,0x47,0x5C)}
)
W "===== EXACT +0x5C ACCESS PATTERNS ====="
foreach($pat in $patterns){
  $hits=[FastScan30V3]::FindPatternInRanges($d,$pat.Bytes,$execStarts,$execEnds)
  W ("{0}: hits={1}"-f$pat.Name,$hits.Count)
  foreach($h in $hits|Select-Object -First 80){
    W (" hit=0x{0:X8} prologue={1}"-f$h,(Fmt (NearestPrologue $h)))
  }
  W ""
}

W "===== SINGLETON CREATION OWNER ====="
W ("Function=0x{0:X8}"-f$creator)
W (HexCtx $creator 32 256)
$creatorCalls=$callers[$creator]
W ("DirectCallers="+$creatorCalls.Count)
foreach($c in $creatorCalls){W (" CALL=0x{0:X8} callerPrologue={1}"-f$c.Call,(Fmt $c.Prologue))}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 30 CONNECTIVITY SINGLETON READY (v3 FAST)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
