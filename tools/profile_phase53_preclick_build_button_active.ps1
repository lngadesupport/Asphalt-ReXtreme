param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE53-PRECLICK-BUILD-ACTIVE.exe"
$report=Join-Path $game "PHASE53-PRECLICK-BUILD-ACTIVE.json"

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

$stableHash="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"

# Preserve the proven stable offline policy.
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

# Pre-click periodic build_button updater:
#   mov ecx,[ebp-18h]
#   test ecx,ecx
#   je ...
#   mov eax,[ecx]
#   push dword ptr [ebp-28h]   ; computed state
#   call dword ptr [eax+7Ch]
#
# Real completion paths use the same +7C method with literal 1.
# Force only this PRE-CLICK updater to pass 1.
$off=0x00574FA7
[byte[]]$orig=@(0xFF,0x75,0xD8)       # push dword ptr [ebp-28h]
[byte[]]$patch=@(0x6A,0x01,0x90)      # push 1 ; nop

$cur=ReadBytes $off 3
$status=""
if(Same $cur $patch){
  $status="already-patched"
}elseif(Same $cur $orig){
  $hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  if($hash-ne$stableHash){
    throw ("Unexpected pre-Phase53 AMS hash: "+$hash+"; expected Phase36-only "+$stableHash)
  }
  if(-not(Test-Path -LiteralPath $backup)){
    Copy-Item -LiteralPath $ams -Destination $backup -Force
  }
  WriteBytes $off $patch
  $status="patched"
}else{
  throw ("Unexpected Phase53 site bytes: "+(Hex $cur))
}

if(-not(Same (ReadBytes $off 3) $patch)){throw "Phase53 verification failed"}
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline changed unexpectedly"}
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){throw "Phase36 changed unexpectedly"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[ordered]@{
  Phase="53-preclick-build-button-active"
  UIUpdaterPreferredVA="0x00975A50"
  PatchFileOffset="0x00574FA7"
  PatchPreferredVA="0x00975BA7"
  Original="push dword ptr [ebp-0x28]"
  Patched="push 1; nop"
  Target="build_button virtual method +0x7C"
  Timing="pre-click / periodic UI updater"
  Purpose="force build_button active state before any CraftCar click"
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 53 PRE-CLICK BUILD BUTTON ACTIVE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Pre-click build_button state forced to 1."
Write-Host "No CraftCar/request/completion patch applied."
Write-Host "Phase36 remains active."
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
