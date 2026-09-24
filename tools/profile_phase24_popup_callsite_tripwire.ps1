param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE24_POPUP_CALL_TRACE"
$backup=Join-Path $outDir "AMS.PRE-CALL-TRAPS.exe"
$mapFile=Join-Path $outDir "TRAPS.json"
$targetFileOffset=[int]0x00870510
$target=[uint32]0

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}
New-Item -ItemType Directory -Path $outDir -Force|Out-Null

[byte[]]$d=[IO.File]::ReadAllBytes($ams)
$fs=[IO.File]::OpenRead($ams)
$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C
  $pe=$br.ReadInt32()
  $fs.Position=$pe
  if($br.ReadUInt32() -ne 0x00004550){throw "Invalid PE signature"}
  $machine=$br.ReadUInt16()
  $sectionCount=$br.ReadUInt16()
  $fs.Position=$pe+20
  $optSize=$br.ReadUInt16()
  $fs.Position=$pe+24
  $magic=$br.ReadUInt16()
  if($machine -ne 0x014C -or $magic -ne 0x10B){throw "Expected x86 PE32"}
  $fs.Position=$pe+24+28
  $imageBase=$br.ReadUInt32()
  $secOff=$pe+24+$optSize
  $sections=@()
  for($i=0;$i -lt $sectionCount;$i++){
    $fs.Position=$secOff+(40*$i)
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vsize=$br.ReadUInt32()
    $vaddr=$br.ReadUInt32()
    $rawSize=$br.ReadUInt32()
    $rawPtr=$br.ReadUInt32()
    $fs.Position=$secOff+(40*$i)+36
    $chars=$br.ReadUInt32()
    $sections += [pscustomobject]@{
      Name=$name; VirtualSize=$vsize; VirtualAddress=$vaddr
      RawSize=$rawSize; RawPointer=$rawPtr; Characteristics=$chars
    }
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToRva([int]$off){
  foreach($s in $sections){
    if($off -ge $s.RawPointer -and $off -lt ($s.RawPointer+$s.RawSize)){
      return [uint32]($s.VirtualAddress+($off-$s.RawPointer))
    }
  }
  return [uint32]0
}

$targetRva=FileToRva $targetFileOffset
if($targetRva -eq 0){throw ("Popup target file offset 0x{0:X8} is not inside a mapped PE section." -f $targetFileOffset)}
$target=[uint32]($imageBase+$targetRva)
Write-Host ("Popup target file=0x{0:X8} RVA=0x{1:X8} VA=0x{2:X8}" -f $targetFileOffset,$targetRva,$target) -ForegroundColor Cyan

$traps=New-Object System.Collections.Generic.List[object]
foreach($s in $sections){
  if(($s.Characteristics -band 0x20000000) -eq 0){continue}
  $start=[int]$s.RawPointer
  $end=[Math]::Min($d.Length,[int]($s.RawPointer+$s.RawSize))
  for($o=$start;$o -le $end-5;$o++){
    if($d[$o] -ne 0xE8){continue}
    $rva=FileToRva $o
    if($rva -eq 0){continue}
    $callVA=[int64]$imageBase+[int64]$rva
    $rel=[BitConverter]::ToInt32($d,$o+1)
    $dest=$callVA+5+[int64]$rel
    if($dest -eq [int64]$target){
      [byte[]]$orig=$d[$o..($o+4)]
      $traps.Add([pscustomobject]@{
        Kind="POPUP_CALL"
        FileOffset=$o
        FileOffsetHex=("0x{0:X8}" -f $o)
        RVA=[uint32]$rva
        RVAHex=("0x{0:X8}" -f $rva)
        PreferredVA=("0x{0:X8}" -f $callVA)
        TargetVA=("0x{0:X8}" -f $target)
        OriginalBytes=(($orig|ForEach-Object{$_.ToString("X2")}) -join " ")
      })
    }
  }
}

if($traps.Count -eq 0){throw ("No direct CALL rel32 references found for popup target file=0x{0:X8} RVA=0x{1:X8} VA=0x{2:X8}." -f $targetFileOffset,$targetRva,$target)}

Copy-Item -LiteralPath $ams -Destination $backup -Force
$before=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$w=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try{
  foreach($t in $traps){
    $w.Position=[int]$t.FileOffset
    if($w.ReadByte() -ne 0xE8){throw ("Expected E8 at "+$t.FileOffsetHex)}
    $w.Position=[int]$t.FileOffset
    $w.WriteByte(0xCC)
  }
  $w.Flush($true)
}finally{$w.Dispose()}

$after=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="24-popup-callsite-tripwire"
  TargetFunctionFileOffset=("0x{0:X8}" -f $targetFileOffset)
  TargetFunctionRVA=("0x{0:X8}" -f $targetRva)
  TargetFunctionVA=("0x{0:X8}" -f $target)
  PreferredImageBase=("0x{0:X8}" -f $imageBase)
  BeforeSHA256=$before
  TrappedSHA256=$after
  Backup=$backup
  TrapCount=$traps.Count
  Traps=$traps.ToArray()
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $mapFile -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 24 POPUP CALLSITE TRAPS INSTALLED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Target function file=0x{0:X8} RVA=0x{1:X8} VA=0x{2:X8}" -f $targetFileOffset,$targetRva,$target)
Write-Host ("Direct callsites trapped: {0}" -f $traps.Count)
