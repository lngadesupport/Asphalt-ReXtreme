param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE44_BUILD_CLEAR_MAP"
$out=Join-Path $outDir "LATEST-PHASE44-BUILD-CLEAR-MAP.txt"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found"}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

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
function Pro([int]$off,[int]$back=0x3000){
  $lo=[Math]::Max(0,$off-$back)
  for($i=$off;$i-ge$lo+2;$i--){
    if($d[$i]-eq0x55 -and $d[$i+1]-eq0x8B -and $d[$i+2]-eq0xEC){return $i}
  };return -1
}
function Ctx([int]$o,[int]$before=48,[int]$after=112){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1)
    $b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|ForEach-Object{$_.ToString("X2")})-join" ")))
  };return ($ls-join[Environment]::NewLine)
}

$exec=@($sections|Where-Object{($_.Chars-band0x20000000)-ne0})
$hits=New-Object Collections.Generic.List[object]

foreach($s in $exec){
  $a=[int]$s.Raw
  $z=[Math]::Min($d.Length-12,[int]([int64]$s.Raw+[int64]$s.RawSize-12))
  for($o=$a;$o-le$z;$o++){
    # C7 8r disp32 imm32  => mov dword ptr [reg+disp32], imm32
    if($d[$o]-eq0xC7){
      $m=$d[$o+1]
      if(($m-band0xC0)-eq0x80 -and (($m-band0x38)-eq0)){
        $disp=[BitConverter]::ToInt32($d,$o+2)
        if($disp-eq0x3AC -or $disp-eq0x3B0){
          $imm=[BitConverter]::ToInt32($d,$o+6)
          $hits.Add([pscustomobject]@{
            Kind="MOV_IMM";Off=$o;Disp=$disp;Imm=$imm;Base=($m-band7);Pro=(Pro $o)
          })
        }
      }
    }
    # 89 8r disp32 => mov [reg+disp32], r32
    if($d[$o]-eq0x89){
      $m=$d[$o+1]
      if(($m-band0xC0)-eq0x80){
        $disp=[BitConverter]::ToInt32($d,$o+2)
        if($disp-eq0x3AC -or $disp-eq0x3B0){
          $hits.Add([pscustomobject]@{
            Kind="MOV_REG";Off=$o;Disp=$disp;Imm=$null;Base=($m-band7);Pro=(Pro $o)
          })
        }
      }
    }
    # 8B 8r disp32 => mov r32,[reg+disp32]
    if($d[$o]-eq0x8B){
      $m=$d[$o+1]
      if(($m-band0xC0)-eq0x80){
        $disp=[BitConverter]::ToInt32($d,$o+2)
        if($disp-eq0x3AC -or $disp-eq0x3B0){
          $hits.Add([pscustomobject]@{
            Kind="MOV_LOAD";Off=$o;Disp=$disp;Imm=$null;Base=($m-band7);Pro=(Pro $o)
          })
        }
      }
    }
  }
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 44 - Exact Build Pending Clear Map"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ExactDecodedHits="+$hits.Count)
W ""

W "===== ZERO WRITES FIRST ====="
foreach($h in $hits|Where-Object{$_.Kind-eq"MOV_IMM" -and $_.Imm-eq0}|Sort-Object Off){
  W ("{0} disp=0x{1:X} file=0x{2:X8} VA=0x{3:X8} baseReg={4} prologue={5}"-f$h.Kind,$h.Disp,$h.Off,(FileToVa $h.Off),$h.Base,$(if($h.Pro-ge0){"0x{0:X8}"-f$h.Pro}else{"N/A"}))
  W (Ctx $h.Off)
  W ""
}

W "===== ALL EXACT +0x3AC/+0x3B0 ACCESSES ====="
foreach($g in ($hits|Group-Object Pro|Sort-Object Count -Descending)){
  $p=[int]$g.Name
  W ("--- Function={0} refs={1} ---"-f($(if($p-ge0){"0x{0:X8}"-f$p}else{"N/A"}),$g.Count))
  foreach($h in $g.Group|Sort-Object Off){
    W (" {0} disp=0x{1:X} file=0x{2:X8} VA=0x{3:X8} baseReg={4} imm={5}"-f$h.Kind,$h.Disp,$h.Off,(FileToVa $h.Off),$h.Base,$(if($null-ne$h.Imm){$h.Imm}else{"-"}))
    W (Ctx $h.Off 24 64)
  }
  W ""
}

W "===== BUILD HANDLER TAIL ====="
W (Ctx 0x00687050 0x20 0x1B0)

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 44 BUILD CLEAR MAP READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
