param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE35-NOINTERNET-UI-FILTER.exe"
$report=Join-Path $game "PHASE35-NOINTERNET-UI-FILTER.json"

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
    $fs.Position=$Offset
    $fs.Write($Bytes,0,$Bytes.Length)
    $fs.Flush($true)
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# Known safe global policy.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
$g=ReadBytes $globalOff $globalExpected.Length
if(-not(Same $g $globalExpected)){
  throw ("Global IsOnline is not in expected FALSE state: "+(Hex $g))
}

# Normalize Phase34 experiment.
$p34Off=0x008BCFF0
[byte[]]$p34Orig=@(0x55,0x8B,0xEC,0x83,0x7D,0x0C,0x00,0x8B,0x45,0x08,0x75)
[byte[]]$p34Patch=@(0x8B,0x44,0x24,0x04,0xC7,0x00,0x00,0x00,0x00,0x00,0xC3)
$p34=ReadBytes $p34Off 11
$phase34Normalized=$false
if(Same $p34 $p34Patch){
  WriteBytes $p34Off $p34Orig
  $phase34Normalized=$true
}elseif(-not(Same $p34 $p34Orig)){
  throw ("Unexpected Phase34 site bytes: "+(Hex $p34))
}

# Phase32 must also remain normalized/original.
$p32Off=0x0098CF80
[byte[]]$p32Orig=@(0x33,0xC0,0x39,0x41,0x5C,0x0F,0x95,0xC0,0xC3)
[byte[]]$p32Patch=@(0xB0,0x01,0xC3,0x90,0x90,0x90,0x90,0x90,0x90)
$p32=ReadBytes $p32Off 9
if(Same $p32 $p32Patch){
  WriteBytes $p32Off $p32Orig
}elseif(-not(Same $p32 $p32Orig)){
  throw ("Unexpected Phase32 site bytes: "+(Hex $p32))
}

# Targeted GS_MessagePopup filter:
# hook file 0x009168B0 / VA 0x00D174B0
# cave file 0x004693C1 / VA 0x00869FC1
# The cave inspects the title string key and returns immediately only when:
#   chars[0..3]  == "STR_"
#   chars[13..16]== "INTE"
# This signature matches STR_POPUP_NO_INTERNET_TITLE while avoiding
# IAP/multiplayer/online-product popup keys observed in AMS.exe.
$hookOff=0x009168B0
$caveOff=0x004693C1

[byte[]]$hookOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$hookPatch=@(0xE9,0x0C,0x2B,0xB5,0xFF)

[byte[]]$caveOrig=New-Object byte[] 47
for($i=0;$i-lt$caveOrig.Length;$i++){$caveOrig[$i]=0xCC}

[byte[]]$cavePatch=@(
  0x8B,0x44,0x24,0x04,             # mov eax,[esp+4] (title wrapper*)
  0x8B,0x00,                       # mov eax,[eax]
  0x85,0xC0,                       # test eax,eax
  0x74,0x1B,                       # jz original
  0x8B,0x00,                       # mov eax,[eax] (buffer header*)
  0x85,0xC0,                       # test eax,eax
  0x74,0x15,                       # jz original
  0x81,0x78,0x01,0x53,0x54,0x52,0x5F, # cmp [eax+1],"STR_"
  0x75,0x0C,                       # jne original
  0x81,0x78,0x0E,0x49,0x4E,0x54,0x45, # cmp [eax+0xE],"INTE"
  0x75,0x03,                       # jne original
  0xC2,0x18,0x00,                  # ret 0x18: suppress this popup
  0x55,0x8B,0xEC,0x6A,0xFF,        # replay overwritten prologue
  0xE9,0xC5,0xD4,0x4A,0x00         # jmp back to 0x00D174B5
)

$hookCur=ReadBytes $hookOff 5
$caveCur=ReadBytes $caveOff 47

$status=""
if((Same $hookCur $hookPatch) -and (Same $caveCur $cavePatch)){
  $status="already-patched"
}elseif((Same $hookCur $hookOrig) -and (Same $caveCur $caveOrig)){
  $baseline=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  if($baseline-ne"3979935f4740096a8518ef031679787ad40bc4a84f533e15b620a5e06117f9bb"){
    throw ("Normalized AMS hash is unexpected: "+$baseline)
  }
  if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
  WriteBytes $caveOff $cavePatch
  WriteBytes $hookOff $hookPatch
  $status="patched"
}else{
  throw ("Unexpected Phase35 hook/cave state. Hook=["+(Hex $hookCur)+"]")
}

if(-not(Same (ReadBytes $hookOff 5) $hookPatch)){throw "Phase35 hook verification failed"}
if(-not(Same (ReadBytes $caveOff 47) $cavePatch)){throw "Phase35 cave verification failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="35-no-internet-ui-filter"
  HookFileOffset="0x009168B0"
  HookPreferredVA="0x00D174B0"
  CaveFileOffset="0x004693C1"
  CavePreferredVA="0x00869FC1"
  TargetClass="GS_MessagePopup"
  Filter="title key signature STR_POPUP_NO_INTERNET_TITLE"
  Behavior="return without creating popup only for matching no-internet title"
  GlobalIsOnline="FALSE / unchanged"
  Phase34Normalized=$phase34Normalized
  Phase32="original"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 35 NO-INTERNET UI FILTER APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "GS_MessagePopup filters only STR_POPUP_NO_INTERNET_TITLE."
Write-Host "Other message popups remain enabled."
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
