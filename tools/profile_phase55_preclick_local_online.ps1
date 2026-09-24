param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE55-PRECLICK-LOCAL-ONLINE.exe"
$report=Join-Path $game "PHASE55-PRECLICK-LOCAL-ONLINE.json"
$phase54Report=Join-Path $game "PHASE54-CRAFTCAR-STATE2.json"

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

# Stable offline invariants.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw "Global IsOnline is not in expected FALSE state."
}

$popupOff=0x009168B0
[byte[]]$popupExpected=@(0x31,0xC0,0xC2,0x18,0x00)
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){
  throw "Phase36 popup bypass is not active."
}

# Phase53: visible/active MONTAR state.
$phase53Off=0x00574FA7
[byte[]]$phase53Expected=@(0x6A,0x01,0x90)
if(-not(Same (ReadBytes $phase53Off 3) $phase53Expected)){
  throw "Phase53 is not active."
}

# Phase54: CraftCar's local state guard consumes state 2.
$phase54Off=0x0059F3F2
[byte[]]$phase54Expected=@(0xB8,0x02,0x00,0x00,0x00,0x90)
if(-not(Same (ReadBytes $phase54Off 6) $phase54Expected)){
  throw "Phase54 is not active."
}

# Pre-click/action handler starts at file 0x00573BF0 / VA 0x009747F0.
# It calls the global IsOnline getter at file 0x00573C3E.
# Immediately after:
#   test al,al
#   je 0x00573CCE
#
# With global IsOnline intentionally FALSE, this JE always leaves the
# actionable path before the build request can be dispatched.
# Neutralize ONLY this conditional jump so execution follows the same
# local action path used when online.
$off=0x00573C45
[byte[]]$orig=@(0x0F,0x84,0x83,0x00,0x00,0x00)
[byte[]]$patch=@(0x90,0x90,0x90,0x90,0x90,0x90)

# Guard surrounding bytes to avoid patching a shifted/different binary.
$prefixOff=0x00573C3E
[byte[]]$prefixExpected=@(0xE8,0x8D,0x91,0x63,0x00,0x84,0xC0)
if(-not(Same (ReadBytes $prefixOff $prefixExpected.Length) $prefixExpected)){
  throw ("Unexpected pre-click IsOnline sequence: "+(Hex (ReadBytes $prefixOff $prefixExpected.Length)))
}

$cur=ReadBytes $off 6
$status=""
$preHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

if(Same $cur $patch){
  $status="already-patched"
}elseif(Same $cur $orig){
  if(-not(Test-Path -LiteralPath $phase54Report -PathType Leaf)){
    throw "Phase54 report missing. Run PHASE54-CRAFTCAR-STATE2.cmd first."
  }
  $p54=Get-Content -LiteralPath $phase54Report -Raw | ConvertFrom-Json
  if([string]$p54.Phase -ne "54-craftcar-pre-request-state2"){
    throw "Unexpected Phase54 report identity."
  }
  $expectedHash=([string]$p54.AMS_SHA256).ToLowerInvariant()
  if([string]::IsNullOrWhiteSpace($expectedHash)){
    throw "Phase54 report does not contain AMS_SHA256."
  }
  if($preHash-ne$expectedHash){
    throw ("Hash guard failed. Current AMS="+$preHash+" Phase54 report="+$expectedHash)
  }

  if(-not(Test-Path -LiteralPath $backup)){
    Copy-Item -LiteralPath $ams -Destination $backup -Force
  }

  WriteBytes $off $patch
  $status="patched"
}else{
  throw ("Unexpected Phase55 site bytes: "+(Hex $cur))
}

if(-not(Same (ReadBytes $off 6) $patch)){throw "Phase55 verification failed"}
if(-not(Same (ReadBytes $phase53Off 3) $phase53Expected)){throw "Phase53 changed unexpectedly"}
if(-not(Same (ReadBytes $phase54Off 6) $phase54Expected)){throw "Phase54 changed unexpectedly"}
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline changed unexpectedly"}
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){throw "Phase36 changed unexpectedly"}

$postHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[ordered]@{
  Phase="55-preclick-local-online"
  HandlerFileOffset="0x00573BF0"
  HandlerPreferredVA="0x009747F0"
  IsOnlineCallFileOffset="0x00573C3E"
  BranchFileOffset="0x00573C45"
  BranchPreferredVA="0x00974845"
  Original="je 0x009748CE"
  Patched="nop x6 / fall through local action path"
  Purpose="allow build-button action dispatch while global IsOnline remains false"
  Phase53PreClickBuildButton="ACTIVE"
  Phase54CraftCarState2="ACTIVE"
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  PrePatchSHA256=$preHash
  AMS_SHA256=$postHash
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 55 PRE-CLICK LOCAL ONLINE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Pre-click IsOnline rejection branch neutralized."
Write-Host "Phase53 MONTAR state remains active."
Write-Host "Phase54 CraftCar state=2 remains active."
Write-Host "Global IsOnline remains FALSE."
Write-Host "Phase36 popup bypass remains ACTIVE."
Write-Host ("AMS SHA256: "+$postHash)
