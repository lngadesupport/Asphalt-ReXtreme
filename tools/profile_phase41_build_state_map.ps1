param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE41_BUILD_STATE_MAP"
$out=Join-Path $outDir "LATEST-PHASE41-BUILD-STATE-MAP.txt"
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
function VaToFile([int64]$va){
  $rva=$va-[int64]$imageBase;if($rva-lt0){return -1}
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    if($rva-ge[int64]$s.VA -and $rva-lt([int64]$s.VA+$span)){
      return [int]([int64]$s.Raw+($rva-[int64]$s.VA))
    }
  };return -1
}
function Pro([int]$off,[int]$back=0x2000){
  $lo=[Math]::Max(0,$off-$back)
  for($i=$off;$i-ge$lo+2;$i--){
    if($d[$i]-eq0x55 -and $d[$i+1]-eq0x8B -and $d[$i+2]-eq0xEC){return $i}
  };return -1
}
function Ctx([int]$o,[int]$before=64,[int]$after=256){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1)
    $b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|ForEach-Object{$_.ToString("X2")})-join" ")))
  };return ($ls-join[Environment]::NewLine)
}
function ScanRel([int]$start,[int]$len){
  $r=New-Object Collections.Generic.List[string]
  $end=[Math]::Min($d.Length-6,$start+$len)
  for($o=$start;$o-le$end;$o++){
    $op=$d[$o]
    if($op-eq0xE8 -or $op-eq0xE9){
      $src=FileToVa $o;$rel=[BitConverter]::ToInt32($d,$o+1)
      $dstVa=[int64]$src+5+[int64]$rel;$dst=VaToFile $dstVa
      $kind=$(if($op-eq0xE8){"CALL"}else{"JMP"})
      $r.Add(("{0} file=0x{1:X8} -> file={2} VA=0x{3:X8}"-f$kind,$o,$(if($dst-ge0){"0x{0:X8}"-f$dst}else{"N/A"}),$dstVa))
    }elseif($op-eq0x0F -and $o+5-lt$d.Length -and $d[$o+1]-ge0x80 -and $d[$o+1]-le0x8F){
      $src=FileToVa $o;$rel=[BitConverter]::ToInt32($d,$o+2)
      $dstVa=[int64]$src+6+[int64]$rel;$dst=VaToFile $dstVa
      $r.Add(("JCC{0:X2} file=0x{1:X8} -> file={2} VA=0x{3:X8}"-f$d[$o+1],$o,$(if($dst-ge0){"0x{0:X8}"-f$dst}else{"N/A"}),$dstVa))
    }elseif($op-ge0x70 -and $op-le0x7F){
      $src=FileToVa $o
      # Windows PowerShell throws when casting Byte 128..255 directly to SByte.
      # Decode rel8 manually as signed two's-complement.
      $rel8=[int]$d[$o+1]
      if($rel8-ge128){$rel8-=256}
      $dstVa=[int64]$src+2+[int64]$rel8;$dst=VaToFile $dstVa
      $r.Add(("JCC{0:X2} file=0x{1:X8} -> file={2} VA=0x{3:X8}"-f$op,$o,$(if($dst-ge0){"0x{0:X8}"-f$dst}else{"N/A"}),$dstVa))
    }
  };return $r.ToArray()
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
        $r.Add([pscustomobject]@{Call=$o;Pro=(Pro $o)})
      }
    }
  };return $r.ToArray()
}
function AsciiAround([int]$start,[int]$len){
  $z=[Math]::Min($d.Length,$start+$len)
  $sb=New-Object Text.StringBuilder
  for($i=$start;$i-lt$z;$i++){
    $c=$d[$i]
    if($c-ge0x20 -and $c-le0x7E){[void]$sb.Append([char]$c)}
    else{[void]$sb.Append(".")}
  }
  return $sb.ToString()
}
function ScanLikelyWrites([int]$start,[int]$len){
  $r=New-Object Collections.Generic.List[string]
  $end=[Math]::Min($d.Length-8,$start+$len)
  for($o=$start;$o-le$end;$o++){
    # C6 /0 byte ptr [reg+disp], imm8
    if($d[$o]-eq0xC6){
      $r.Add(("C6 write-like @0x{0:X8}: {1}"-f$o,(($d[$o..([Math]::Min($o+7,$d.Length-1))]|%{$_.ToString("X2")})-join" ")))
    }
    # C7 /0 dword ptr [reg+disp], imm32
    if($d[$o]-eq0xC7){
      $r.Add(("C7 write-like @0x{0:X8}: {1}"-f$o,(($d[$o..([Math]::Min($o+11,$d.Length-1))]|%{$_.ToString("X2")})-join" ")))
    }
    # 88/89 stores are useful candidates.
    if($d[$o]-eq0x88 -or $d[$o]-eq0x89){
      $r.Add(("{0:X2} store-like @0x{1:X8}: {2}"-f$d[$o],$o,(($d[$o..([Math]::Min($o+7,$d.Length-1))]|%{$_.ToString("X2")})-join" ")))
    }
  };return $r.ToArray()
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 41 - Build State Focus Map v2"
W "============================================================"
W ("AMS_SHA256="+$hash)
W "Expected stable Phase36-only hash=22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
W ""

$targets=@(
 [pscustomobject]@{Name="READY_TO_BUILD UI/state function";Off=0x00573880;Len=0x500},
 [pscustomobject]@{Name="CraftCar unique caller";Off=0x0059F350;Len=0x500},
 [pscustomobject]@{Name="CraftCar start";Off=0x005A3FA0;Len=0x260},
 [pscustomobject]@{Name="CraftCar result handler";Off=0x005A3CA0;Len=0x300}
)
foreach($t in $targets){
  W ("===== {0} file=0x{1:X8} VA=0x{2:X8} ====="-f$t.Name,$t.Off,(FileToVa $t.Off))
  W (Ctx $t.Off 32 ($t.Len+32))
  W "--- CONTROL FLOW ---"
  foreach($x in ScanRel $t.Off $t.Len){W $x}
  W "--- WRITE CANDIDATES ---"
  foreach($x in ScanLikelyWrites $t.Off $t.Len){W $x}
  W ""
}

# Also inspect direct callers of READY_TO_BUILD function and unique-caller function.
foreach($target in @(0x00573880,0x0059F350)){
  W ("===== DIRECT CALLERS OF 0x{0:X8} ====="-f$target)
  $cs=@(DirectCallers $target)
  W ("Count="+$cs.Count)
  foreach($c in $cs){
    W ("CALL=0x{0:X8} callerPrologue={1}"-f$c.Call,$(if($c.Pro-ge0){"0x{0:X8}"-f$c.Pro}else{"N/A"}))
    W (Ctx $c.Call 64 128)
  }
  W ""
}

# Adjacent blueprint UI keys in the same string-table neighborhood.
W "===== ASCII STRING TABLE AROUND STR_BP_READY_TO_BUILD ====="
W (AsciiAround 0x0113DEA0 0x280)

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 41 BUILD STATE MAP READY (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
