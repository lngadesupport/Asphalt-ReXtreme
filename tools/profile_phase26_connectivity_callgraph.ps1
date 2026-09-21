param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE26_CONNECTIVITY_CALLGRAPH"
$out=Join-Path $outDir "LATEST-PHASE26-CONNECTIVITY-CALLGRAPH.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$fs=[IO.File]::OpenRead($ams);$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C;$pe=$br.ReadInt32()
  $fs.Position=$pe
  if($br.ReadUInt32()-ne 0x00004550){throw "Invalid PE signature"}
  $machine=$br.ReadUInt16();$nsec=$br.ReadUInt16()
  $fs.Position=$pe+20;$opt=$br.ReadUInt16()
  $fs.Position=$pe+24;$magic=$br.ReadUInt16()
  if($machine-ne 0x014C -or $magic-ne 0x10B){throw "Expected x86 PE32"}
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
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return [uint32]($s.VA+($off-$s.Raw))}}
  return [uint32]0
}
function RvaToFile([uint32]$rva){
  foreach($s in $sections){
    $span=[Math]::Max([uint32]$s.VSize,[uint32]$s.RawSize)
    if($rva-ge$s.VA -and $rva-lt($s.VA+$span)){return [int]($s.Raw+($rva-$s.VA))}
  }
  return -1
}
function FileToVa([int]$off){$r=FileToRva $off;if($r-eq0){return [uint32]0};return [uint32]($imageBase+$r)}
function IsExec([int]$off){
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return (($s.Chars-band0x20000000)-ne0)}}
  return $false
}
function SectionName([int]$off){
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return $s.Name}}
  return "?"
}
function NearestPrologue([int]$off,[int]$back=0x800){
  $min=[Math]::Max(0,$off-$back)
  for($p=$off;$p-ge$min+2;$p--){
    if($d[$p]-eq0x55 -and $d[$p+1]-eq0x8B -and $d[$p+2]-eq0xEC){return $p}
  }
  return -1
}
function Fmt([int]$x){if($x-ge0){return ("0x{0:X8}"-f$x)};return "N/A"}
function HexCtx([int]$center,[int]$before=64,[int]$after=96){
  $a=[Math]::Max(0,$center-$before);$b=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$b;$o+=16){
    $take=[Math]::Min(16,$b-$o+1);$bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|%{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}
function DirectCallsToFile([int]$targetOff){
  $targetVA=[int64](FileToVa $targetOff)
  $res=New-Object Collections.Generic.List[object]
  if($targetVA-eq0){return $res.ToArray()}
  foreach($s in $sections){
    if(($s.Chars-band0x20000000)-eq0){continue}
    $start=[int]$s.Raw;$end=[Math]::Min($d.Length,[int]($s.Raw+$s.RawSize))
    for($o=$start;$o-le$end-5;$o++){
      if($d[$o]-ne0xE8){continue}
      $srcVA=[int64](FileToVa $o);if($srcVA-eq0){continue}
      $rel=[BitConverter]::ToInt32($d,$o+1)
      if(($srcVA+5+$rel)-eq$targetVA){
        $res.Add([pscustomobject]@{Call=$o;Prologue=(NearestPrologue $o);Section=(SectionName $o)})
      }
    }
  }
  return $res.ToArray()
}
function FindBytes([byte[]]$needle){
  $res=New-Object Collections.Generic.List[int]
  for($i=0;$i-le$d.Length-$needle.Length;$i++){
    $ok=$true
    for($j=0;$j-lt$needle.Length;$j++){if($d[$i+$j]-ne$needle[$j]){$ok=$false;break}}
    if($ok){$res.Add($i);$i+=$needle.Length-1}
  }
  return $res.ToArray()
}
function FindDword([uint32]$value){
  [byte[]]$p=[BitConverter]::GetBytes($value)
  $res=New-Object Collections.Generic.List[int]
  for($i=0;$i-le$d.Length-4;$i++){
    if($d[$i]-eq$p[0]-and$d[$i+1]-eq$p[1]-and$d[$i+2]-eq$p[2]-and$d[$i+3]-eq$p[3]){$res.Add($i)}
  }
  return $res.ToArray()
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 26 - Connectivity Callgraph + RTTI"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ""

# Phase25-proven WinRT wrapper entry points (file offsets).
$wrappers=@(
  [pscustomobject]@{Name="WinRT-Connectivity-Wrapper-A";Off=0x00B989D0},
  [pscustomobject]@{Name="WinRT-Connectivity-Wrapper-B";Off=0x00B9A100},
  [pscustomobject]@{Name="WinRT-Connectivity-Wrapper-C";Off=0x00D2DEA0},
  [pscustomobject]@{Name="WinRT-Connectivity-Wrapper-D";Off=0x00E07C40}
)

$level1=New-Object Collections.Generic.List[object]
W "===== WINRT WRAPPER CALLERS ====="
foreach($w in $wrappers){
  $va=FileToVa $w.Off
  W ("--- {0} file={1} VA=0x{2:X8} ---"-f$w.Name,(Fmt $w.Off),$va)
  W (HexCtx $w.Off 32 96)
  $calls=@(DirectCallsToFile $w.Off)
  W ("DirectCallers="+$calls.Count)
  foreach($c in $calls){
    W ("CALL={0} callerPrologue={1} section={2}"-f(Fmt $c.Call),(Fmt $c.Prologue),$c.Section)
    if($c.Prologue-ge0){$level1.Add([pscustomobject]@{Wrapper=$w.Name;Call=$c.Call;Func=$c.Prologue})}
  }
  W ""
}

# Level 2 callers of each unique level-1 function.
W "===== LEVEL-2 CALLERS ====="
$funcs=@($level1|Select-Object -ExpandProperty Func -Unique|Sort-Object)
$level2=New-Object Collections.Generic.List[object]
foreach($fn in $funcs){
  W ("--- function {0} ---"-f(Fmt $fn))
  W (HexCtx $fn 16 112)
  $calls=@(DirectCallsToFile $fn)
  W ("Callers="+$calls.Count)
  foreach($c in $calls){
    W ("CALL={0} parentPrologue={1}"-f(Fmt $c.Call),(Fmt $c.Prologue))
    if($c.Prologue-ge0){$level2.Add([pscustomobject]@{Child=$fn;Call=$c.Call;Parent=$c.Prologue})}
  }
  W ""
}

# Map all direct callers of the known global IsOnline getter and intersect with callgraph funcs.
$isoOff=0x00BACDD0
$isoCalls=@(DirectCallsToFile $isoOff)
$isoFuncs=@($isoCalls|Where-Object{$_.Prologue-ge0}|Select-Object -ExpandProperty Prologue -Unique)
W "===== INTERSECTION WITH ISONLINE FUNCTIONS ====="
W ("IsOnlineDirectCalls="+$isoCalls.Count)
$matches=0
foreach($x in $level1){
  if($isoFuncs -contains $x.Func){
    W ("LEVEL1 MATCH func={0} wrapper={1} wrapperCall={2}"-f(Fmt $x.Func),$x.Wrapper,(Fmt $x.Call))
    W (HexCtx $x.Func 16 192);W "";$matches++
  }
}
foreach($x in $level2){
  if($isoFuncs -contains $x.Parent){
    W ("LEVEL2 MATCH parent={0} child={1} call={2}"-f(Fmt $x.Parent),(Fmt $x.Child),(Fmt $x.Call))
    W (HexCtx $x.Parent 16 192);W "";$matches++
  }
}
W ("CallgraphIsOnlineMatches="+$matches)
W ""

# RTTI/pointer-chain analysis for AVAsphaltConnectivityTracker.
W "===== AVAsphaltConnectivityTracker POINTER CHAIN ====="
$tracker=[Text.Encoding]::ASCII.GetBytes("AVAsphaltConnectivityTracker")
$hits=@(FindBytes $tracker)
W ("StringHits="+$hits.Count)
foreach($off in $hits){
  $va=FileToVa $off
  W ("STRING file={0} RVA=0x{1:X8} VA=0x{2:X8} section={3}"-f(Fmt $off),(FileToRva $off),$va,(SectionName $off))
  W (HexCtx $off 48 96)
  $p1=@(FindDword $va)
  W ("PointerLevel1="+$p1.Count)
  foreach($a in $p1){
    $aVA=FileToVa $a
    W (" P1 file={0} VA=0x{1:X8} section={2} exec={3}"-f(Fmt $a),$aVA,(SectionName $a),(IsExec $a))
    if($aVA-ne0){
      $p2=@(FindDword $aVA)
      W ("   PointerLevel2="+$p2.Count)
      foreach($b in $p2|Select-Object -First 64){
        $bVA=FileToVa $b
        $pro=if(IsExec $b){NearestPrologue $b}else{-1}
        W ("   P2 file={0} VA=0x{1:X8} section={2} exec={3} prologue={4}"-f(Fmt $b),$bVA,(SectionName $b),(IsExec $b),(Fmt $pro))
        if(IsExec $b){W (HexCtx $b 32 64)}
      }
    }
  }
  W ""
}

# Search for MSVC-decorated tracker names too.
foreach($name in @(".?AVAVAsphaltConnectivityTracker@@",".?AUAVAsphaltConnectivityTracker@@")){
  $hh=@(FindBytes ([Text.Encoding]::ASCII.GetBytes($name)))
  W ("DecoratedName {0} hits={1}"-f$name,$hh.Count)
  foreach($h in $hh){W (" file={0} VA=0x{1:X8}"-f(Fmt $h),(FileToVa $h))}
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 26 CONNECTIVITY CALLGRAPH READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
