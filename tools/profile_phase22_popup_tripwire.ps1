param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE22_POPUP_TRACE"
$backup=Join-Path $outDir "AMS.PRE-TRAPS.exe"
$mapFile=Join-Path $outDir "TRAPS.json"

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
function ExecutableOffset([int]$off){
  foreach($s in $sections){
    if($off -ge $s.RawPointer -and $off -lt ($s.RawPointer+$s.RawSize)){
      return (($s.Characteristics -band 0x20000000) -ne 0)
    }
  }
  return $false
}
function FindPtrPushes([uint32]$va,[string]$kind){
  [byte[]]$p=[BitConverter]::GetBytes($va)
  $list=New-Object System.Collections.Generic.List[object]
  for($i=1;$i -le $d.Length-4;$i++){
    if($d[$i] -eq $p[0] -and $d[$i+1] -eq $p[1] -and $d[$i+2] -eq $p[2] -and $d[$i+3] -eq $p[3]){
      $instr=$i-1
      if($d[$instr] -eq 0x68 -and (ExecutableOffset $instr)){
        $rva=FileToRva $instr
        $list.Add([pscustomobject]@{
          Kind=$kind
          FileOffset=$instr
          FileOffsetHex=("0x{0:X8}" -f $instr)
          RVA=[uint32]$rva
          RVAHex=("0x{0:X8}" -f $rva)
          OriginalByte="68"
          TrapByte="CC"
        })
      }
    }
  }
  return $list.ToArray()
}

# These are the two string-key VAs proven by the earlier static map.
$traps=New-Object System.Collections.Generic.List[object]
foreach($x in @(FindPtrPushes 0x015360F0 "TITLE")){
  $traps.Add($x)
}
foreach($x in @(FindPtrPushes 0x015360CC "DESCRIPTION")){
  if(-not($traps | Where-Object {$_.FileOffset -eq $x.FileOffset})){$traps.Add($x)}
}
if($traps.Count -eq 0){throw "No executable PUSH refs to NO_INTERNET strings were found."}

Copy-Item -LiteralPath $ams -Destination $backup -Force
$before=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$w=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try{
  foreach($t in $traps){
    $w.Position=[int]$t.FileOffset
    if($w.ReadByte() -ne 0x68){throw ("Expected PUSH at "+$t.FileOffsetHex)}
    $w.Position=[int]$t.FileOffset
    $w.WriteByte(0xCC)
  }
  $w.Flush($true)
}finally{$w.Dispose()}

$after=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="22-popup-tripwire"
  ImageBase=("0x{0:X8}" -f $imageBase)
  BeforeSHA256=$before
  TrappedSHA256=$after
  Backup=$backup
  TrapCount=$traps.Count
  Traps=$traps.ToArray()
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $mapFile -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 22 NO_INTERNET TRIPWIRES INSTALLED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Tripwires: {0}" -f $traps.Count)
Write-Host ("Map: {0}" -f $mapFile)
