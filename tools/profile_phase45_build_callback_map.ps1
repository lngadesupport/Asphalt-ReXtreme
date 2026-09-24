param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE45_BUILD_CALLBACK_MAP"
$out=Join-Path $outDir "LATEST-PHASE45-BUILD-CALLBACK-MAP.txt"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null
if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found"}

function ReadBytes([int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{$fs.Position=$Offset;[byte[]]$b=New-Object byte[] $Count;if($fs.Read($b,0,$Count)-ne$Count){throw "short read"};return $b}
  finally{$fs.Dispose()}
}
function WriteBytes([int]$Offset,[byte[]]$Bytes){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{$fs.Position=$Offset;$fs.Write($Bytes,0,$Bytes.Length);$fs.Flush($true)}
  finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}

# Remove failed Phase42 local-online experiment so analysis returns to Phase36-only.
$p42off=0x00686DA4
[byte[]]$p42orig=@(0x0F,0x85,0xDE,0x01,0x00,0x00)
[byte[]]$p42patch=@(0xE9,0xDF,0x01,0x00,0x00,0x90)
$p42=ReadBytes $p42off 6
$phase42Normalized=$false
if(Same $p42 $p42patch){
  WriteBytes $p42off $p42orig
  $phase42Normalized=$true
}elseif(-not(Same $p42 $p42orig)){
  throw "Unexpected Phase42 site bytes."
}

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
    if($d[$i]-eq0x55-and$d[$i+1]-eq0x8B-and$d[$i+2]-eq0xEC){return $i}
  };return -1
}
function Ctx([int]$o,[int]$before=48,[int]$after=144){
  $a=[Math]::Max(0,$o-$before);$z=[Math]::Min($d.Length-1,$o+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($p=$a;$p-le$z;$p+=16){
    $n=[Math]::Min(16,$z-$p+1);$b=$d[$p..($p+$n-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$p,(($b|ForEach-Object{$_.ToString("X2")})-join" ")))
  };return ($ls-join[Environment]::NewLine)
}

$targets=@(0x298,0x35C,0x3AC,0x3B0)
$exec=@($sections|Where-Object{($_.Chars-band0x20000000)-ne0})
$hits=New-Object Collections.Generic.List[object]

foreach($s in $exec){
  $a=[int]$s.Raw
  $z=[Math]::Min($d.Length-8,[int]([int64]$s.Raw+[int64]$s.RawSize-8))
  for($o=$a;$o-le$z;$o++){
    $op=$d[$o]
    if($op-ne0x8B -and $op-ne0x89 -and $op-ne0x8D -and $op-ne0xC7){continue}
    $m=$d[$o+1]
    if(($m-band0xC0)-ne0x80){continue}
    $disp=[BitConverter]::ToInt32($d,$o+2)
    if($targets-notcontains$disp){continue}
    $kind=switch($op){0x8B{"LOAD"}0x89{"STORE"}0x8D{"LEA"}0xC7{"STORE_IMM"}}
    $imm=$null
    if($op-eq0xC7 -and $o+9-lt$d.Length){$imm=[BitConverter]::ToInt32($d,$o+6)}
    $hits.Add([pscustomobject]@{Kind=$kind;Off=$o;Disp=$disp;Imm=$imm;Pro=(Pro $o)})
  }
}

$groups=$hits|Group-Object Pro
$ranked=@()
foreach($g in $groups){
  $ds=@($g.Group|Select-Object -ExpandProperty Disp -Unique)
  $score=0
  if($ds-contains0x298){$score+=4}
  if($ds-contains0x35C){$score+=4}
  if($ds-contains0x3AC){$score+=3}
  if($ds-contains0x3B0){$score+=3}
  $ranked += [pscustomobject]@{Pro=[int]$g.Name;Score=$score;Refs=$g.Count;Disps=(($ds|Sort-Object|ForEach-Object{"0x{0:X}"-f$_})-join",");Group=$g.Group}
}
$ranked=$ranked|Sort-Object @{Expression="Score";Descending=$true},@{Expression="Refs";Descending=$true}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 45 - Build Callback/UI Completion Map"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("Phase42Normalized="+$phase42Normalized)
W "Expected stable Phase36-only hash=22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
W ""

W "===== RANKED FUNCTIONS ====="
foreach($r in $ranked|Select-Object -First 40){
  W ("Function={0} Score={1} Refs={2} Offsets={3}"-f($(if($r.Pro-ge0){"0x{0:X8}"-f$r.Pro}else{"N/A"}),$r.Score,$r.Refs,$r.Disps))
  foreach($h in $r.Group|Sort-Object Off){
    W (" {0} disp=0x{1:X} file=0x{2:X8} VA=0x{3:X8} imm={4}"-f$h.Kind,$h.Disp,$h.Off,(FileToVa $h.Off),$(if($null-ne$h.Imm){$h.Imm}else{"-"}))
  }
  if($r.Score-ge7 -and $r.Pro-ge0){
    W (Ctx $r.Pro 0 0x340)
  }
  W ""
}

W "===== BUILD HANDLER CALLBACK REGISTRATION ====="
W (Ctx 0x006870D0 0x20 0xB0)

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 45 BUILD CALLBACK MAP READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Phase42 normalized: "+$phase42Normalized)
Write-Host ("Report: "+$out)
