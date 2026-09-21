param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE28_CONNECTIVITY_RTTI"
$out=Join-Path $outDir "LATEST-PHASE28-CONNECTIVITY-RTTI.txt"
New-Item -ItemType Directory -Path $outDir -Force|Out-Null

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

# Normalize only the Phase27 experiment so this map describes the clean connectivity code.
$phase27Off=0x00D2E320
[byte[]]$p27Orig=@(0x55,0x8B,0xEC)
[byte[]]$p27Patch=@(0xB0,0x01,0xC3)
$rw=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try{
  $rw.Position=$phase27Off
  [byte[]]$b=New-Object byte[] 3
  if($rw.Read($b,0,3)-ne3){throw "Short read at Phase27 site"}
  $isPatch=($b[0]-eq$p27Patch[0] -and $b[1]-eq$p27Patch[1] -and $b[2]-eq$p27Patch[2])
  $isOrig=($b[0]-eq$p27Orig[0] -and $b[1]-eq$p27Orig[1] -and $b[2]-eq$p27Orig[2])
  if($isPatch){
    $rw.Position=$phase27Off
    $rw.Write($p27Orig,0,3)
    $rw.Flush($true)
  }elseif(-not$isOrig){
    throw ("Unexpected bytes at Phase27 site: "+(($b|ForEach-Object{$_.ToString("X2")})-join" "))
  }
}finally{$rw.Dispose()}

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

# PE32 mapping.
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
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return [uint32]($s.VA+($off-$s.Raw))}}
  return [uint32]0
}
function FileToVa([int]$off){$r=FileToRva $off;if($r-eq0){return [uint32]0};return [uint32]($imageBase+$r)}
function VaToFile([uint32]$va){
  if($va-lt$imageBase){return -1}
  $rva=[uint32]($va-$imageBase)
  foreach($s in $sections){
    $span=[Math]::Max([uint32]$s.VSize,[uint32]$s.RawSize)
    if($rva-ge$s.VA -and $rva-lt($s.VA+$span)){return [int]($s.Raw+($rva-$s.VA))}
  }
  return -1
}
function SectionName([int]$off){
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return $s.Name}}
  return "?"
}
function IsExec([int]$off){
  foreach($s in $sections){if($off-ge$s.Raw -and $off-lt($s.Raw+$s.RawSize)){return (($s.Chars-band0x20000000)-ne0)}}
  return $false
}
function Fmt([int]$x){if($x-ge0){return ("0x{0:X8}"-f$x)};return "N/A"}
function HexCtx([int]$center,[int]$before=32,[int]$after=96){
  $a=[Math]::Max(0,$center-$before);$z=[Math]::Min($d.Length-1,$center+$after)
  $ls=New-Object Collections.Generic.List[string]
  for($o=$a;$o-le$z;$o+=16){
    $take=[Math]::Min(16,$z-$o+1);$bytes=$d[$o..($o+$take-1)]
    $ls.Add(("0x{0:X8}: {1}"-f$o,(($bytes|ForEach-Object{$_.ToString("X2")})-join" ")))
  }
  return ($ls-join[Environment]::NewLine)
}
function FindAscii([string]$text){
  [byte[]]$n=[Text.Encoding]::ASCII.GetBytes($text)
  $res=New-Object Collections.Generic.List[int]
  for($i=0;$i-le$d.Length-$n.Length;$i++){
    if($d[$i]-ne$n[0]){continue}
    $ok=$true
    for($j=1;$j-lt$n.Length;$j++){if($d[$i+$j]-ne$n[$j]){$ok=$false;break}}
    if($ok){$res.Add($i);$i+=$n.Length-1}
  }
  return $res.ToArray()
}
function FindDword([uint32]$v){
  [byte[]]$p=[BitConverter]::GetBytes($v)
  $res=New-Object Collections.Generic.List[int]
  for($i=0;$i-le$d.Length-4;$i++){
    if($d[$i]-eq$p[0] -and $d[$i+1]-eq$p[1] -and $d[$i+2]-eq$p[2] -and $d[$i+3]-eq$p[3]){$res.Add($i)}
  }
  return $res.ToArray()
}
function ReadU32([int]$off){
  if($off-lt0 -or $off+4-gt$d.Length){return [uint32]0}
  return [BitConverter]::ToUInt32($d,$off)
}
function ContainsDirectCall([int]$funcOff,[int]$maxLen,[int[]]$targetOffs){
  $targets=@{}
  foreach($to in $targetOffs){$tv=FileToVa $to;if($tv-ne0){$targets[[uint32]$tv]=$to}}
  $end=[Math]::Min($d.Length-5,$funcOff+$maxLen)
  $hits=New-Object Collections.Generic.List[string]
  for($o=$funcOff;$o-le$end;$o++){
    if($d[$o]-ne0xE8){continue}
    $sv=[int64](FileToVa $o);if($sv-eq0){continue}
    $rel=[BitConverter]::ToInt32($d,$o+1)
    $dest64=[int64]$sv + 5 + [int64]$rel
    if($dest64 -lt 0 -or $dest64 -gt 4294967295){continue}
    $dest=[uint32]$dest64
    if($targets.ContainsKey($dest)){$hits.Add(("call@{0}->targetFile={1}"-f(Fmt $o),(Fmt $targets[$dest])))}
  }
  return $hits.ToArray()
}

$sb=New-Object Text.StringBuilder
function W([string]$s=""){[void]$sb.AppendLine($s)}
W "============================================================"
W " ReXtreme Phase 28 - AVAsphaltConnectivityTracker RTTI v2"
W "============================================================"
W ("AMS_SHA256="+$hash)
W ("ImageBase=0x{0:X8}"-f$imageBase)
W ""

# Correct MSVC RTTI decorated name. TypeDescriptor = 8 bytes before name.
$decorated=".?AVAsphaltConnectivityTracker@@"
$nameHits=@(FindAscii $decorated)
W ("DecoratedName="+$decorated)
W ("DecoratedNameHits="+$nameHits.Count)

$knownTargets=[int[]]@(0x00B989D0,0x00B9A100,0x00D2DEA0,0x00D2E320,0x00E07C40,0x00E0E490,0x00BACDD0)

foreach($nameOff in $nameHits){
  $tdOff=$nameOff-8
  $tdVA=FileToVa $tdOff
  W ""
  W "===== TYPE DESCRIPTOR ====="
  W ("Name file={0} VA=0x{1:X8}"-f(Fmt $nameOff),(FileToVa $nameOff))
  W ("TypeDescriptor file={0} VA=0x{1:X8} section={2}"-f(Fmt $tdOff),$tdVA,(SectionName $tdOff))
  W (HexCtx $tdOff 16 80)

  $tdRefs=@(FindDword $tdVA)
  W ("TypeDescriptorPointerRefs="+$tdRefs.Count)

  foreach($tdRef in $tdRefs){
    $colOff=$tdRef-12
    if($colOff-lt0){continue}
    $sig=ReadU32 $colOff
    $offset=ReadU32 ($colOff+4)
    $cdOffset=ReadU32 ($colOff+8)
    $pTD=ReadU32 ($colOff+12)
    $pCHD=ReadU32 ($colOff+16)
    if($pTD-ne$tdVA){continue}
    $colVA=FileToVa $colOff
    W ""
    W ("COL candidate file={0} VA=0x{1:X8} section={2} signature={3} offset={4} cdOffset={5} pCHD=0x{6:X8}"-f(Fmt $colOff),$colVA,(SectionName $colOff),$sig,$offset,$cdOffset,$pCHD)
    W (HexCtx $colOff 16 48)

    $colRefs=@(FindDword $colVA)
    W ("COLPointerRefs="+$colRefs.Count)
    foreach($cr in $colRefs){
      # In MSVC x86, vftable[-1] points to CompleteObjectLocator.
      $vfOff=$cr+4
      $vfVA=FileToVa $vfOff
      W ""
      W ("VFTABLE candidate anchor={0} vftableFile={1} vftableVA=0x{2:X8} section={3}"-f(Fmt $cr),(Fmt $vfOff),$vfVA,(SectionName $vfOff))

      $methods=New-Object Collections.Generic.List[object]
      for($i=0;$i-lt64;$i++){
        $entryOff=$vfOff+4*$i
        if($entryOff+4-gt$d.Length){break}
        $fnVA=ReadU32 $entryOff
        $fnOff=VaToFile $fnVA
        if($fnOff-lt0 -or -not(IsExec $fnOff)){break}
        $calls=@(ContainsDirectCall $fnOff 0x300 $knownTargets)
        $methods.Add([pscustomobject]@{Index=$i;Entry=$entryOff;FnVA=$fnVA;FnOff=$fnOff;Calls=$calls})
      }
      W ("Methods="+$methods.Count)
      foreach($m in $methods){
        $tag=""
        if($m.Calls.Count-gt0){$tag="  *** KNOWN CONNECTIVITY CALL: "+($m.Calls-join"; ")}
        W ("[{0}] entry={1} fnVA=0x{2:X8} fnFile={3}{4}"-f$m.Index,(Fmt $m.Entry),$m.FnVA,(Fmt $m.FnOff),$tag)
        if($m.Calls.Count-gt0){W (HexCtx $m.FnOff 16 160)}
      }

      # Constructor/initializer clues: executable immediates that load/store the vftable address.
      $vfRefs=@(FindDword $vfVA)
      $execRefs=@($vfRefs|Where-Object{IsExec $_})
      W ("ExecutableRefsToVftable="+$execRefs.Count)
      foreach($er in $execRefs|Select-Object -First 32){
        W (" VFTABLE REF file={0}"-f(Fmt $er))
        W (HexCtx $er 32 64)
      }
    }
  }
}

W ""
W "===== NOTE ====="
W "Phase27 predicate was normalized back to its original prologue before this analysis."
W "Methods marked KNOWN CONNECTIVITY CALL directly call one of the Phase25/26 WinRT wrappers, the candidate InternetAccess predicate, or global IsOnline."

$sb.ToString()|Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 28 CONNECTIVITY RTTI READY (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: "+$out)
