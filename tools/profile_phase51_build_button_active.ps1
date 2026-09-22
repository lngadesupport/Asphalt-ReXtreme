param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE51-BUILD-BUTTON-ACTIVE.exe"
$report=Join-Path $game "PHASE51-BUILD-BUTTON-ACTIVE.json"

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

# Stable invariants.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline is not FALSE."}

$popupOff=0x009168B0
[byte[]]$popupExpected=@(0x31,0xC0,0xC2,0x18,0x00)
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){throw "Phase36 popup bypass is not active."}

# Exact state toggle after build request is registered:
#   call 0x00973510        ; get build_button
#   mov  ecx,[eax]
#   push 0                ; current code: disabled/loading state
#   ...
#   call [vtable+0x7C]
#
# The real completion callback uses the SAME sequence with push 1.
# Phase51 changes only that immediate argument.
$off=0x0068712F
[byte[]]$orig=@(0x6A,0x00)
[byte[]]$patch=@(0x6A,0x01)

$cur=ReadBytes $off 2
$status=""
if(Same $cur $patch){
  $status="already-patched"
}elseif(Same $cur $orig){
  $hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  if($hash-ne$stableHash){
    throw ("Unexpected pre-Phase51 AMS hash: "+$hash+"; expected "+$stableHash)
  }
  if(-not(Test-Path -LiteralPath $backup)){
    Copy-Item -LiteralPath $ams -Destination $backup -Force
  }
  WriteBytes $off $patch
  $status="patched"
}else{
  throw ("Unexpected bytes at Phase51 site: "+(Hex $cur))
}

if(-not(Same (ReadBytes $off 2) $patch)){throw "Phase51 verification failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="51-build-button-active"
  BuildButtonGetterPreferredVA="0x00973510"
  BuildHandlerPreferredVA="0x00A87960"
  ToggleFileOffset="0x0068712F"
  TogglePreferredVA="0x00A87D2F"
  Original="push 0"
  Patched="push 1"
  Meaning="use the same active/enabled state that the real CraftCar completion callback uses"
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 51 BUILD BUTTON ACTIVE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "build_button toggle: 0 -> 1"
Write-Host "Phase36: active"
Write-Host "Global IsOnline: FALSE"
Write-Host ("AMS SHA256: "+$hash)
