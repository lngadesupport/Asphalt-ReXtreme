param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE43_BUILD_PENDING_MAP"
$out=Join-Path $outDir "LATEST-PHASE43-BUILD-PENDING-MAP.txt"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

# PE32 map
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
function Pro([int]$off,[int]$back=0x3000){
  $lo=[Math]::Max(0,$off-$back)
  for($i=$off;$i-ge$lo+2;$i--){
    if($d[$i]-eq0x55 -and $d[$i+1]-eq0x8B -and $d[$i+2]-eq0xEC){return $i}
  };return -1
}
function Ctx([int]$o,[int]$before=64,[int]$after=160){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1)
    $b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}

$cs=@"
using System;
using System.Collections.Generic;
public static class P43 {
  public static int[] Find4(byte[] d, byte a, byte b, byte c, byte e, int[] starts, int[] ends) {
    var r=new List<int>();
    for(int q=0;q<starts.Length;q++){
      int s=Math.Max(0,starts[q]), z=Math.Min(d.Length-4,ends[q]-4);
      for(int i=s;i<=z;i++){
        if(d[i]==a && d[i+1]==b && d[i+2]==c && d[i+3]==e) r.Add(i);
      }
    }
    return r.ToArray();
  }
}
"@
Add-Type -TypeDefinition $cs -Language CSharp

$exec=@($sections|Where-Object{($_.Chars-band0x20000000)-ne0})
[int[]]$starts=@($exec|ForEach-Object{[int]$_.Raw})
[int[]]$ends=@($exec|ForEach-Object{[int]([Math]::Min($d.Length,[int64]$_.Raw+[int64]$_.RawSize))})

# We search the little-endian displacement bytes for +0x3AC and +0x3B0.
$hitsAC=[P43]::Find4($d,0xAC,0x03,0x00,0x00,$starts,$ends)
$hitsB0=[P43]::Find4($d,0xB0,0x03,0x00,0x00,$starts,$ends)

$all=New-Object Collections.Generic.List[object]
foreach($h in $hitsAC){$all.Add([pscustomobject]@{Disp="0x3AC";Hit=$h;Pro=(Pro $h)})}
foreach($h in $hitsB0){$all.Add([pscustomobject]@{Disp="0x3B0";Hit=$h;Pro=(Pro $h)})}

$groups=$all|Group-Object Pro|Sort-Object Count -Descending

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 43 - Build Pending/Spinner State Map"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ("Hits_3AC="+$hitsAC.Count)
W ("Hits_3B0="+$hitsB0.Count)
W ""

W "===== EXACT BUILD HANDLER WINDOW ====="
W "Handler file=0x00686D60"
W (Ctx 0x00686D60 32 0x420)
W ""

W "===== GROUPED +0x3AC/+0x3B0 REFERENCES ====="
foreach($g in $groups){
  $p=[int]$g.Name
  W ("--- Function={0} refs={1} ---"-f($(if($p-ge0){"0x{0:X8}"-f$p}else{"N/A"}),$g.Count))
  foreach($item in $g.Group|Sort-Object Hit){
    $h=[int]$item.Hit
    W (" {0} displacement hit=0x{1:X8} VA=0x{2:X8}"-f$item.Disp,$h,(FileToVa $h))
    W (Ctx $h 32 64)
  }
  W ""
}

# Explicitly flag byte patterns that are likely zero/clear or stores around these fields.
W "===== LIKELY CLEAR/WRITE SITES ====="
foreach($item in $all|Sort-Object Hit){
  $h=[int]$item.Hit
  $a=[Math]::Max(0,$h-4);$z=[Math]::Min($d.Length-1,$h+12)
  $hex=(($d[$a..$z]|ForEach-Object{$_.ToString("X2")})-join" ")
  if($hex -match "C7" -or $hex -match "89" -or $hex -match "8B"){
    W ("{0} hit=0x{1:X8} prologue={2} bytes={3}"-f$item.Disp,$h,$(if($item.Pro-ge0){"0x{0:X8}"-f$item.Pro}else{"N/A"}),$hex)
  }
}

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 43 BUILD PENDING MAP READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
