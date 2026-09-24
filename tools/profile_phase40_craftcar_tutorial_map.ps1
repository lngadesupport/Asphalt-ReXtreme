param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE40_CRAFTCAR_TUTORIAL_MAP"
$out=Join-Path $outDir "LATEST-PHASE40-CRAFTCAR-TUTORIAL-MAP.txt"
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
function WriteBytes([int]$Offset,[byte[]]$Bytes){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{
    $fs.Position=$Offset;$fs.Write($Bytes,0,$Bytes.Length);$fs.Flush($true)
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# ---- Normalize failed experiments, preserve Phase36 ----
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline must remain FALSE."}

$popupOff=0x009168B0
[byte[]]$popupOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$popupSafe=@(0x31,0xC0,0xC2,0x18,0x00)
$p=ReadBytes $popupOff 5
if(Same $p $popupOrig){WriteBytes $popupOff $popupSafe}
elseif(-not(Same $p $popupSafe)){throw ("Unexpected Phase36 site: "+(Hex $p))}

# Phase37 normalize
$p37Off=0x008D3A02
[byte[]]$p37Orig=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,0x8B,0x0D,0xD0,0xA1,0x93,0x01,
  0xE8,0x1C,0x5F,0xAB,0xFF,0x8B,0xF0,0x8D,0x45,0xEC
)
[byte[]]$p37Patch=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,0x6A,0x00,0x6A,0x00,0x8B,0xCF,
  0xE8,0x4C,0x7F,0x00,0x00,0xE9,0x6A,0x00,0x00,0x00
)
$x=ReadBytes $p37Off $p37Orig.Length
if(Same $x $p37Patch){WriteBytes $p37Off $p37Orig}
elseif(-not(Same $x $p37Orig)){throw "Unexpected Phase37 site."}

# Phase38 normalize
$p38ControllerOff=0x005FC518
[byte[]]$p38ControllerOrig=@(0x8B,0x4E,0x08,0x83,0xEC)
[byte[]]$p38ControllerPatch=@(0xE9,0xD3,0x50,0x05,0x00)
$p38StubOff=0x006515F0
[byte[]]$p38StubOrig=@(
  0x55,0x8B,0xEC,0x6A,0xFF,0x68,0x00,0xCD,0x3E,0x01,0x64,0xA1,0x00,0x00,0x00,0x00,
  0x50,0x81,0xEC,0xBC,0x00,0x00,0x00,0xA1,0x00,0x7A,0x89,0x01,0x33,0xC5,0x89,0x45,
  0xF0,0x53,0x56,0x57,0x50,0x8D,0x45,0xF4,0x64,0xA3,0x00,0x00,0x00,0x00,0x8B,0xC1,
  0x89,0x45,0xE8,0x8B,0x0D,0x90,0x89,0x94,0x01,0xC7,0x45,0xFC,0x00,0x00,0x00,0x00,
  0xC7,0x85,0x58,0xFF,0xFF,0xFF,0x90,0xCE,0xA5,0x00,0x89,0x85,0x54,0xFF,0xFF,0xFF
)
[byte[]]$p38StubPatch=@(
  0x8B,0x56,0x08,0x85,0xD2,0x74,0x44,0x83,0xEC,0x14,0x31,0xC0,0x89,0x04,0x24,0x8B,
  0x42,0x50,0x89,0x44,0x24,0x04,0x8B,0x42,0x54,0x89,0x44,0x24,0x08,0x85,0xC0,0x74,
  0x04,0xF0,0xFF,0x40,0x04,0xC7,0x44,0x24,0x0C,0x00,0x00,0x00,0x00,0xC7,0x44,0x24,
  0x10,0x00,0x00,0x00,0x00,0x8D,0x04,0x24,0x50,0x89,0xF1,0xE8,0x60,0x48,0xFC,0xFF,
  0x8D,0x0C,0x24,0xE8,0x68,0xFE,0xF9,0xFF,0x83,0xC4,0x14,0xE9,0x0B,0xAF,0xFA,0xFF
)
$c38=ReadBytes $p38ControllerOff 5;$s38=ReadBytes $p38StubOff 80
if((Same $c38 $p38ControllerPatch)-and(Same $s38 $p38StubPatch)){
  WriteBytes $p38ControllerOff $p38ControllerOrig;WriteBytes $p38StubOff $p38StubOrig
}elseif((-not(Same $c38 $p38ControllerOrig))-or(-not(Same $s38 $p38StubOrig))){
  throw "Unexpected Phase38 state."
}

# Phase39 normalize
$craftStartOff=0x005A3FA0
[byte[]]$craftStartOrig=@(0xFF,0x71,0x68,0xE8,0x08,0x00,0x00,0x00,0xC3,0xCC)
[byte[]]$craftStartPatch=@(0x6A,0x00,0x6A,0x00,0xE8,0xF7,0xFC,0xFF,0xFF,0xC3)
$craftHandlerPatchOff=0x005A3CB6
[byte[]]$craftHandlerOrig=@(0x56,0xFF,0x75,0x08,0x8B,0xF9,0xE8,0x2F,0xFF,0x3F,0x00)
[byte[]]$craftHandlerPatch=@(0x8B,0xF9,0x31,0xC0,0xE9,0x89,0x01,0x00,0x00,0x90,0x90)

$s39=ReadBytes $craftStartOff 10;$h39=ReadBytes $craftHandlerPatchOff 11
$phase39Normalized=$false
if((Same $s39 $craftStartPatch)-and(Same $h39 $craftHandlerPatch)){
  WriteBytes $craftStartOff $craftStartOrig
  WriteBytes $craftHandlerPatchOff $craftHandlerOrig
  $phase39Normalized=$true
}elseif((-not(Same $s39 $craftStartOrig))-or(-not(Same $h39 $craftHandlerOrig))){
  throw ("Unexpected Phase39 state. Start="+(Hex $s39)+" Handler="+(Hex $h39))
}

# ---- Static focused mapper ----
[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$cs=@"
using System;
using System.Collections.Generic;
using System.Text;
public static class P40Scan {
  public static int[] Find(byte[] d, byte[] p) {
    var r=new List<int>(); if(p==null||p.Length==0) return r.ToArray();
    for(int i=0;i<=d.Length-p.Length;i++){
      if(d[i]!=p[0]) continue; bool ok=true;
      for(int j=1;j<p.Length;j++) if(d[i+j]!=p[j]){ok=false;break;}
      if(ok) r.Add(i);
    } return r.ToArray();
  }
  public static int[] FindDword(byte[] d,uint v) {
    return Find(d,new byte[]{(byte)v,(byte)(v>>8),(byte)(v>>16),(byte)(v>>24)});
  }
}
"@
Add-Type -TypeDefinition $cs -Language CSharp

# PE32
$fs=[IO.File]::OpenRead($ams);$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C;$pe=$br.ReadInt32();$fs.Position=$pe
  if($br.ReadUInt32()-ne0x4550){throw "Invalid PE"}
  $machine=$br.ReadUInt16();$nsec=$br.ReadUInt16()
  $fs.Position=$pe+20;$optSize=$br.ReadUInt16()
  $fs.Position=$pe+24;$magic=$br.ReadUInt16()
  if($machine-ne0x14C -or $magic-ne0x10B){throw "Expected x86 PE32"}
  $fs.Position=$pe+24+28;$imageBase=$br.ReadUInt32()
  $secOff=$pe+24+$optSize;$sections=@()
  for($i=0;$i-lt$nsec;$i++){
    $fs.Position=$secOff+40*$i
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vs=$br.ReadUInt32();$va=$br.ReadUInt32();$rs=$br.ReadUInt32();$raw=$br.ReadUInt32()
    $fs.Position=$secOff+40*$i+36;$ch=$br.ReadUInt32()
    $sections += [pscustomobject]@{Name=$name;VSize=$vs;VA=$va;RawSize=$rs;Raw=$raw;Chars=$ch}
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToVa([int]$off){
  foreach($s in $sections){
    if($off-ge[int]$s.Raw -and $off-lt([int64]$s.Raw+[int64]$s.RawSize)){
      return [int64]$imageBase+[int64]$s.VA+($off-[int64]$s.Raw)
    }
  };return -1
}
function VaToFile([int64]$va){
  $rva=$va-[int64]$imageBase;if($rva-lt0){return -1}
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    if($rva-ge[int64]$s.VA -and $rva-lt([int64]$s.VA+$span)){
      return [int]([int64]$s.Raw+($rva-[int64]$s.VA))
    }
  };return -1
}
function IsExec([int]$off){
  foreach($s in $sections){
    if($off-ge[int]$s.Raw -and $off-lt([int64]$s.Raw+[int64]$s.RawSize)){
      return (($s.Chars-band0x20000000)-ne0)
    }
  };return $false
}
function Pro([int]$off,[int]$back=0x1800){
  $lo=[Math]::Max(0,$off-$back)
  for($i=$off;$i-ge$lo+2;$i--){
    if($d[$i]-eq0x55-and$d[$i+1]-eq0x8B-and$d[$i+2]-eq0xEC){return $i}
  };return -1
}
function Ctx([int]$o,[int]$before=64,[int]$after=160){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1)
    $b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|%{$_.ToString("X2")})-join" ")))
  };return ($ls-join[Environment]::NewLine)
}
function DirectCallers([int]$targetOff){
  $tva=FileToVa $targetOff
  $r=New-Object Collections.Generic.List[object]
  foreach($s in $sections){
    if(($s.Chars-band0x20000000)-eq0){continue}
    $a=[int]$s.Raw;$z=[Math]::Min($d.Length-5,[int]([int64]$s.Raw+[int64]$s.RawSize-5))
    for($o=$a;$o-le$z;$o++){
      if($d[$o]-ne0xE8){continue}
      $src=FileToVa $o;$rel=[BitConverter]::ToInt32($d,$o+1)
      if(([int64]$src+5+[int64]$rel)-eq$tva){
        $r.Add([pscustomobject]@{Call=$o;Prologue=(Pro $o)})
      }
    }
  };return $r.ToArray()
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 40 - CraftCar / Tutorial Build Map"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("Phase39Normalized="+$phase39Normalized)
W "Phase38=original"
W "Phase37=original"
W "Phase36PopupBypass=ACTIVE"
W "GlobalIsOnline=FALSE"
W ""

$targets=@(
  [pscustomobject]@{Name="CraftCar start";Off=0x005A3FA0},
  [pscustomobject]@{Name="CraftCar result handler";Off=0x005A3CA0}
)
foreach($t in $targets){
  W ("===== {0} file=0x{1:X8} VA=0x{2:X8} ====="-f$t.Name,$t.Off,(FileToVa $t.Off))
  W (Ctx $t.Off 64 320)
  $calls=@(DirectCallers $t.Off)
  W ("DirectCallers="+$calls.Count)
  foreach($c in $calls){
    W (" CALL=0x{0:X8} callerPrologue={1}"-f$c.Call,($(if($c.Prologue-ge0){"0x{0:X8}"-f$c.Prologue}else{"N/A"})))
    W (Ctx $c.Call 64 128)
  }
  W ""
}

# Search exact/likely build-related strings and dump executable immediate refs.
$terms=@(
 "scripts/cars/craft_car.php",
 "CraftCarRequestImpl",
 "STR_BP_READY_TO_BUILD",
 "READY_TO_BUILD",
 "BLUEPRINT",
 "BUILD",
 "CRAFT",
 "CAREER"
)
W "===== BUILD/TUTORIAL STRING XREFS ====="
foreach($term in $terms){
  [byte[]]$pat=[Text.Encoding]::ASCII.GetBytes($term)
  $hits=[P40Scan]::Find($d,$pat)
  W ("TERM="+$term+" StringHits="+$hits.Length)
  foreach($h in $hits|Select-Object -First 40){
    $va=FileToVa $h
    W (" STRING file=0x{0:X8} VA=0x{1:X8}"-f$h,$va)
    if($va-ge0){
      $refs=[P40Scan]::FindDword($d,[uint32]$va)
      foreach($r in $refs){
        if(IsExec $r){
          $pr=Pro $r
          W ("  XREF file=0x{0:X8} prologue={1}"-f$r,($(if($pr-ge0){"0x{0:X8}"-f$pr}else{"N/A"})))
          W (Ctx $r 48 96)
        }
      }
    }
  }
  W ""
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 40 RESTORE + CRAFTCAR TUTORIAL MAP READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Phase39 reverted. Phase36 kept active."
Write-Host ("Report: "+$out)
