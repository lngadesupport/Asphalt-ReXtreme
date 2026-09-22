param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE54-CRAFTCAR-STATE2.exe"
$report=Join-Path $game "PHASE54-CRAFTCAR-STATE2.json"
$phase53Report=Join-Path $game "PHASE53-PRECLICK-BUILD-ACTIVE.json"

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

# Phase53 must remain active: pre-click build_button state = 1.
$phase53Off=0x00574FA7
[byte[]]$phase53Expected=@(0x6A,0x01,0x90)
if(-not(Same (ReadBytes $phase53Off 3) $phase53Expected)){
  throw "Phase53 is not active at 0x00574FA7."
}

# Unique CraftCar caller (VA 0x0099FF50) performs:
#   mov eax,[esi+0F8h]
#   cmp eax,1
#   je  reject
#   cmp eax,2
#   jne reject
#
# Force only the value consumed by those two guards to 2.
# This does NOT mutate [esi+0xF8] in memory and does NOT call CraftCar directly.
$off=0x0059F3F2
[byte[]]$orig=@(0x8B,0x86,0xF8,0x00,0x00,0x00)
[byte[]]$patch=@(0xB8,0x02,0x00,0x00,0x00,0x90)

# Verify the comparison tail has not drifted.
$tailOff=0x0059F3F8
[byte[]]$tailExpected=@(
  0x83,0xF8,0x01,0x0F,0x84,0x72,0x01,0x00,0x00,
  0x83,0xF8,0x02,0x0F,0x85,0x69,0x01,0x00,0x00
)
if(-not(Same (ReadBytes $tailOff $tailExpected.Length) $tailExpected)){
  throw ("Unexpected CraftCar state-guard tail: "+(Hex (ReadBytes $tailOff $tailExpected.Length)))
}

$cur=ReadBytes $off 6
$status=""
$preHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

if(Same $cur $patch){
  $status="already-patched"
}elseif(Same $cur $orig){
  # Hash guard against the exact Phase53 image produced on this machine.
  if(-not(Test-Path -LiteralPath $phase53Report -PathType Leaf)){
    throw "Phase53 report missing. Re-run PHASE53-PRECLICK-BUILD-BUTTON-ACTIVE.cmd first."
  }
  $p53=Get-Content -LiteralPath $phase53Report -Raw | ConvertFrom-Json
  if([string]$p53.Phase -ne "53-preclick-build-button-active"){
    throw "Unexpected Phase53 report identity."
  }
  $expectedHash=([string]$p53.AMS_SHA256).ToLowerInvariant()
  if([string]::IsNullOrWhiteSpace($expectedHash)){
    throw "Phase53 report does not contain AMS_SHA256."
  }
  if($preHash-ne$expectedHash){
    throw ("Hash guard failed. Current AMS="+$preHash+" Phase53 report="+$expectedHash)
  }

  if(-not(Test-Path -LiteralPath $backup)){
    Copy-Item -LiteralPath $ams -Destination $backup -Force
  }
  WriteBytes $off $patch
  $status="patched"
}else{
  throw ("Unexpected Phase54 site bytes: "+(Hex $cur))
}

if(-not(Same (ReadBytes $off 6) $patch)){throw "Phase54 verification failed"}
if(-not(Same (ReadBytes $phase53Off 3) $phase53Expected)){throw "Phase53 changed unexpectedly"}
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline changed unexpectedly"}
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){throw "Phase36 changed unexpectedly"}

$postHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[ordered]@{
  Phase="54-craftcar-pre-request-state2"
  CraftCarCallerFileOffset="0x0059F350"
  CraftCarCallerPreferredVA="0x0099FF50"
  PatchFileOffset="0x0059F3F2"
  PatchPreferredVA="0x0099FFF2"
  Original="mov eax,[esi+0xF8]"
  Patched="mov eax,2; nop"
  Purpose="pass only the local state==2 gate immediately before CraftCar request construction"
  CraftCarDirectCall="UNCHANGED"
  Phase53PreClickBuildButton="ACTIVE"
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  PrePatchSHA256=$preHash
  AMS_SHA256=$postHash
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 54 CRAFTCAR PRE-REQUEST STATE=2 APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Phase53 MONTAR state remains active."
Write-Host "CraftCar local gate now consumes state 2."
Write-Host "CraftCar direct call is unchanged."
Write-Host "Global IsOnline remains FALSE."
Write-Host "Phase36 popup bypass remains ACTIVE."
Write-Host ("AMS SHA256: "+$postHash)
