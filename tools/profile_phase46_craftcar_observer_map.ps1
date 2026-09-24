param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE46_BUILD_OBSERVER_MAP"
$out=Join-Path $outDir "LATEST-PHASE46-BUILD-OBSERVER-MAP.txt"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedHash="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
if($hash-ne$expectedHash){throw ("Expected Phase36-only AMS hash "+$expectedHash+", got "+$hash)}

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

function VaToFile([uint32]$va){
  $rva=[int64]$va-[int64]$imageBase
  if($rva-lt0){return -1}
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    if($rva-ge[int64]$s.VA -and $rva-lt([int64]$s.VA+$span)){
      return [int]([int64]$s.Raw+($rva-[int64]$s.VA))
    }
  };return -1
}
function FileToVa([int]$off){
  foreach($s in $sections){
    if($off-ge[int]$s.Raw -and $off-lt([int64]$s.Raw+[int64]$s.RawSize)){
      return [uint32]([int64]$imageBase+[int64]$s.VA+($off-[int64]$s.Raw))
    }
  };return 0
}
function IsExecVa([uint32]$va){
  $rva=[int64]$va-[int64]$imageBase
  foreach($s in $sections){
    $span=[Math]::Max([int64]$s.VSize,[int64]$s.RawSize)
    if($rva-ge[int64]$s.VA -and $rva-lt([int64]$s.VA+$span)){
      return (($s.Chars-band0x20000000)-ne0)
    }
  };return $false
}
function Ctx([int]$o,[int]$before=32,[int]$after=128){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1)
    $b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|ForEach-Object{$_.ToString("X2")})-join" ")))
  };return ($ls-join[Environment]::NewLine)
}
function DirectCallers([uint32]$targetVa){
  $r=New-Object Collections.Generic.List[int]
  foreach($s in $sections){
    if(($s.Chars-band0x20000000)-eq0){continue}
    $a=[int]$s.Raw;$z=[Math]::Min($d.Length-5,[int]([int64]$s.Raw+[int64]$s.RawSize-5))
    for($o=$a;$o-le$z;$o++){
      if($d[$o]-ne0xE8){continue}
      $src=FileToVa $o
      $rel=[BitConverter]::ToInt32($d,$o+1)
      $dst=[int64]$src+5+[int64]$rel
      if($dst-eq[int64]$targetVa){$r.Add($o)}
    }
  };return $r.ToArray()
}
function FindDwordRefs([uint32]$value){
  [byte[]]$p=[BitConverter]::GetBytes($value)
  $r=New-Object Collections.Generic.List[int]
  for($i=0;$i-le$d.Length-4;$i++){
    if($d[$i]-eq$p[0]-and$d[$i+1]-eq$p[1]-and$d[$i+2]-eq$p[2]-and$d[$i+3]-eq$p[3]){$r.Add($i)}
  };return $r.ToArray()
}

$observerVtable=[uint32]0x0184F6C0
$tempVtable=[uint32]0x0184F41C
$observerOff=VaToFile $observerVtable
$tempOff=VaToFile $tempVtable
if($observerOff-lt0){throw "Observer vtable VA did not map to file"}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 46 - CraftCar Observer VTable Map"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ("ObserverVTableVA=0x{0:X8} File=0x{1:X8}"-f$observerVtable,$observerOff)
W ("CtorTempVTableVA=0x{0:X8} File=0x{1:X8}"-f$tempVtable,$tempOff)
W ""

foreach($label in @(
  [pscustomobject]@{Name="FINAL_OBSERVER_VTABLE";VA=$observerVtable;Off=$observerOff},
  [pscustomobject]@{Name="CTOR_TEMP_VTABLE";VA=$tempVtable;Off=$tempOff}
)){
  W ("===== "+$label.Name+" =====")
  for($i=0;$i-lt24;$i++){
    $slotOff=$label.Off+4*$i
    if($slotOff+3-ge$d.Length){break}
    $fn=[BitConverter]::ToUInt32($d,$slotOff)
    $fnOff=VaToFile $fn
    $exec=IsExecVa $fn
    W ("slot={0,2} entryFile=0x{1:X8} fnVA=0x{2:X8} fnFile={3} Exec={4}"-f$i,$slotOff,$fn,$(if($fnOff-ge0){"0x{0:X8}"-f$fnOff}else{"N/A"}),$exec)
    if($exec-and$fnOff-ge0){
      W (Ctx $fnOff 0 112)
      $calls=@(DirectCallers $fn)
      W ("DirectCallers="+$calls.Count)
      foreach($c in $calls|Select-Object -First 16){
        W (" callerFile=0x{0:X8} callerVA=0x{1:X8}"-f$c,(FileToVa $c))
        W (Ctx $c 24 48)
      }
      # Look in method prefix for parent-adjust patterns involving -0x298.
      $end=[Math]::Min($d.Length-6,$fnOff+128)
      for($o=$fnOff;$o-le$end;$o++){
        if($o+5-lt$d.Length){
          $v=[BitConverter]::ToInt32($d,$o+2)
          if($v-eq-0x298 -or $v-eq0x298){
            W ("  ** +/-0x298 immediate near method @ file=0x{0:X8}"-f$o)
          }
        }
      }
    }
    W ""
  }
}

W "===== EXECUTABLE REFS TO FINAL OBSERVER VTABLE ====="
foreach($r in FindDwordRefs $observerVtable){
  # check section executable
  $isExec=$false
  foreach($s in $sections){
    if($r-ge[int]$s.Raw-and$r-lt([int64]$s.Raw+[int64]$s.RawSize)){$isExec=(($s.Chars-band0x20000000)-ne0);break}
  }
  if($isExec){
    W ("refFile=0x{0:X8} refVA=0x{1:X8}"-f$r,(FileToVa $r))
    W (Ctx $r 48 96)
  }
}

W "===== BUILD HANDLER REGISTRATION WINDOW ====="
W (Ctx 0x006870D0 32 160)

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 46 CRAFTCAR OBSERVER MAP READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
