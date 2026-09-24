param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$p24=Join-Path $game "_PHASE24_POPUP_CALL_TRACE"
$p24backup=Join-Path $p24 "AMS.PRE-CALL-TRAPS.exe"
$p24map=Join-Path $p24 "TRAPS.json"
$outDir=Join-Path $game "_PHASE25_CONNECTIVITY_MAP"
$out=Join-Path $outDir "LATEST-PHASE25-CONNECTIVITY-MAP.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null

if(-not(Test-Path -LiteralPath $ams)){throw "AMS.exe not found."}

# Robustly restore the exact pre-Phase24 executable if that backup exists.
if(Test-Path -LiteralPath $p24backup){
  $expected=$null
  if(Test-Path -LiteralPath $p24map){
    try{$expected=((Get-Content -LiteralPath $p24map -Raw|ConvertFrom-Json).BeforeSHA256).ToLowerInvariant()}catch{}
  }
  $deadline=(Get-Date).AddSeconds(30)
  $restored=$false
  do{
    try{
      Copy-Item -LiteralPath $p24backup -Destination $ams -Force
      $restored=$true
      break
    }catch{
      Start-Sleep -Milliseconds 500
    }
  }while((Get-Date)-lt $deadline)
  if(-not $restored){throw "Could not restore AMS.exe from Phase24 backup after 30 seconds."}
  if($expected){
    $actual=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual -ne $expected){throw ("Phase24 restore hash mismatch. expected="+$expected+" actual="+$actual)}
  }
}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

# Parse PE32 sections.
$fs=[IO.File]::OpenRead($ams); $br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C; $pe=$br.ReadInt32()
  $fs.Position=$pe
  if($br.ReadUInt32() -ne 0x00004550){throw "Invalid PE signature"}
  $machine=$br.ReadUInt16(); $nsec=$br.ReadUInt16()
  $fs.Position=$pe+20; $opt=$br.ReadUInt16()
  $fs.Position=$pe+24; $magic=$br.ReadUInt16()
  if($machine -ne 0x014C -or $magic -ne 0x10B){throw "Expected x86 PE32"}
  $fs.Position=$pe+24+28; $imageBase=$br.ReadUInt32()
  $secOff=$pe+24+$opt
  $sections=@()
  for($i=0;$i -lt $nsec;$i++){
    $fs.Position=$secOff+40*$i
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vsize=$br.ReadUInt32(); $vaddr=$br.ReadUInt32()
    $rawSize=$br.ReadUInt32(); $rawPtr=$br.ReadUInt32()
    $fs.Position=$secOff+40*$i+36; $chars=$br.ReadUInt32()
    $sections += [pscustomobject]@{Name=$name;VSize=$vsize;VA=$vaddr;RawSize=$rawSize;Raw=$rawPtr;Chars=$chars}
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToRva([int]$off){
  foreach($s in $sections){
    if($off -ge $s.Raw -and $off -lt ($s.Raw+$s.RawSize)){return [uint32]($s.VA+($off-$s.Raw))}
  }
  return [uint32]0
}
function RvaToFile([uint32]$rva){
  foreach($s in $sections){
    $span=[Math]::Max([uint32]$s.VSize,[uint32]$s.RawSize)
    if($rva -ge $s.VA -and $rva -lt ($s.VA+$span)){return [int]($s.Raw+($rva-$s.VA))}
  }
  return -1
}
function IsExec([int]$off){
  foreach($s in $sections){
    if($off -ge $s.Raw -and $off -lt ($s.Raw+$s.RawSize)){return (($s.Chars -band 0x20000000)-ne 0)}
  }
  return $false
}
function FindAll([byte[]]$needle){
  $res=New-Object System.Collections.Generic.List[int]
  for($i=0;$i -le $d.Length-$needle.Length;$i++){
    $ok=$true
    for($j=0;$j -lt $needle.Length;$j++){if($d[$i+$j]-ne $needle[$j]){$ok=$false;break}}
    if($ok){$res.Add($i);$i+=$needle.Length-1}
  }
  return $res.ToArray()
}
function NearestPrologue([int]$off){
  $min=[Math]::Max(0,$off-0x600)
  for($p=$off;$p -ge $min+2;$p--){
    if($d[$p] -eq 0x55 -and $d[$p+1]-eq 0x8B -and $d[$p+2]-eq 0xEC){return $p}
  }
  return -1
}
function FormatFileOffset([int]$off){
  if($off -ge 0){ return ("0x{0:X8}" -f $off) }
  return "N/A"
}
function HexContext([int]$center,[int]$before=64,[int]$after=96){
  $a=[Math]::Max(0,$center-$before); $b=[Math]::Min($d.Length-1,$center+$after)
  $lines=New-Object System.Collections.Generic.List[string]
  for($o=$a;$o -le $b;$o+=16){
    $take=[Math]::Min(16,$b-$o+1)
    $bytes=$d[$o..($o+$take-1)]
    $lines.Add(("0x{0:X8}: {1}" -f $o,(($bytes|ForEach-Object{$_.ToString("X2")})-join " ")))
  }
  return ($lines -join [Environment]::NewLine)
}
function ScanImmediateRefs([uint32]$va){
  [byte[]]$p=[BitConverter]::GetBytes($va)
  $refs=New-Object System.Collections.Generic.List[int]
  for($i=0;$i -le $d.Length-4;$i++){
    if($d[$i]-eq $p[0] -and $d[$i+1]-eq $p[1] -and $d[$i+2]-eq $p[2] -and $d[$i+3]-eq $p[3]){
      # Include refs whose immediate lands inside executable code; instruction can begin up to 6 bytes earlier.
      $candidate=$false
      for($k=1;$k -le 6;$k++){if($i-$k -ge 0 -and (IsExec ($i-$k))){$candidate=$true;break}}
      if($candidate){$refs.Add($i)}
    }
  }
  return $refs.ToArray()
}

$terms=@(
  [pscustomobject]@{Name="AVAsphaltConnectivityTracker";Enc="ASCII";Bytes=[Text.Encoding]::ASCII.GetBytes("AVAsphaltConnectivityTracker")},
  [pscustomobject]@{Name="Windows.Networking.Connectivity";Enc="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes("Windows.Networking.Connectivity")},
  [pscustomobject]@{Name="GetInternetConnectionProfile";Enc="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes("GetInternetConnectionProfile")},
  [pscustomobject]@{Name="NetworkConnectivityLevel";Enc="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes("NetworkConnectivityLevel")},
  [pscustomobject]@{Name="InternetAccess";Enc="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes("InternetAccess")}
)

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 25 - Connectivity Tracker Map v2"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}" -f $imageBase)
W ""

$functions=New-Object System.Collections.Generic.List[object]
foreach($t in $terms){
  $hits=@(FindAll $t.Bytes)
  W ("===== TERM {0} ENC={1} HITS={2} =====" -f $t.Name,$t.Enc,$hits.Count)
  foreach($off in $hits){
    $rva=FileToRva $off
    $va=[uint32]($imageBase+$rva)
    W ("STRING file=0x{0:X8} RVA=0x{1:X8} VA=0x{2:X8}" -f $off,$rva,$va)
    $refs=@(ScanImmediateRefs $va)
    W ("ImmediateRefs="+$refs.Count)
    foreach($imm in $refs){
      $pro=NearestPrologue $imm
      W ("REF immediate@file=0x{0:X8} nearestPrologue={1}" -f $imm,(FormatFileOffset $pro))
      W (HexContext $imm 64 96)
      W ""
      $functions.Add([pscustomobject]@{Term=$t.Name;Ref=$imm;Prologue=$pro})
    }
  }
  W ""
}

# Map the known global IsOnline getter and all direct E8 callers.
$isoOff=0x00BACDD0
$isoRva=FileToRva $isoOff
$isoVA=[uint32]($imageBase+$isoRva)
W "===== GLOBAL ISONLINE ====="
W ("Getter file=0x{0:X8} RVA=0x{1:X8} VA=0x{2:X8}" -f $isoOff,$isoRva,$isoVA)
W (HexContext $isoOff 48 64)
W ""

$calls=New-Object System.Collections.Generic.List[object]
foreach($s in $sections){
  if(($s.Chars -band 0x20000000)-eq 0){continue}
  $start=[int]$s.Raw; $end=[Math]::Min($d.Length,[int]($s.Raw+$s.RawSize))
  for($o=$start;$o -le $end-5;$o++){
    if($d[$o]-ne 0xE8){continue}
    $rva=FileToRva $o
    $srcVA=[int64]$imageBase+[int64]$rva
    $rel=[BitConverter]::ToInt32($d,$o+1)
    if(($srcVA+5+$rel)-eq [int64]$isoVA){
      $pro=NearestPrologue $o
      $calls.Add([pscustomobject]@{Call=$o;Prologue=$pro})
    }
  }
}
W ("DirectIsOnlineCalls="+$calls.Count)
foreach($c in $calls){
  W ("CALL file=0x{0:X8} nearestPrologue={1}" -f $c.Call,(FormatFileOffset $c.Prologue))
}
W ""

W "===== CROSS-MATCH: CONNECTIVITY REF FUNCTION ALSO CALLS ISONLINE ====="
$matched=0
foreach($f in $functions){
  if($f.Prologue -lt 0){continue}
  foreach($c in $calls){
    if($c.Prologue -eq $f.Prologue){
      W ("MATCH prologue=0x{0:X8} term={1} ref=0x{2:X8} IsOnlineCall=0x{3:X8}" -f $f.Prologue,$f.Term,$f.Ref,$c.Call)
      W (HexContext $c.Call 96 128)
      W ""
      $matched++
    }
  }
}
W ("CrossMatches="+$matched)

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 25 CONNECTIVITY MAP READY (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
