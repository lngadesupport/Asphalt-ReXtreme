param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE34-GAIA-RESULT.exe"
$report=Join-Path $game "PHASE34-GAIA-RESULT.json"

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
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# Keep the known safe global connectivity policy.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
$g=ReadBytes $globalOff $globalExpected.Length
if(-not(Same $g $globalExpected)){
  throw ("Global IsOnline is not in expected FALSE state: "+(Hex $g))
}

# Ensure failed Phase32 experiment is normalized.
$phase32Off=0x0098CF80
[byte[]]$phase32Orig=@(0x33,0xC0,0x39,0x41,0x5C,0x0F,0x95,0xC0,0xC3)
[byte[]]$phase32Patch=@(0xB0,0x01,0xC3,0x90,0x90,0x90,0x90,0x90,0x90)
$p32=ReadBytes $phase32Off 9
if(Same $p32 $phase32Patch){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{$fs.Position=$phase32Off;$fs.Write($phase32Orig,0,9);$fs.Flush($true)}finally{$fs.Dispose()}
}elseif(-not(Same $p32 $phase32Orig)){
  throw ("Unexpected Phase32 site bytes: "+(Hex $p32))
}

# Gaia result normalizer at file offset 0x008BCFF0:
# original:
#   push ebp
#   mov ebp,esp
#   cmp [ebp+0C],0
#   mov eax,[ebp+08]
#   jne fail
#   mov [eax],0
#   ...
# fail:
#   mov [eax],0xBB8
#
# Phase34:
#   mov eax,[esp+4]   ; output pointer
#   mov dword [eax],0 ; always success
#   ret               ; caller remains cdecl and cleans 8 bytes
$off=0x008BCFF0
[byte[]]$expected=@(
  0x55,0x8B,0xEC,0x83,0x7D,0x0C,0x00,0x8B,0x45,0x08,0x75
)
[byte[]]$patched=@(
  0x8B,0x44,0x24,0x04,0xC7,0x00,0x00,0x00,0x00,0x00,0xC3
)

$cur=ReadBytes $off $expected.Length
$status=""
if(Same $cur $patched){
  $status="already-patched"
}elseif(Same $cur $expected){
  if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{
    $fs.Position=$off
    $fs.Write($patched,0,$patched.Length)
    $fs.Flush($true)
  }finally{$fs.Dispose()}
  $status="patched"
}else{
  throw ("Unexpected bytes at Gaia result normalizer 0x{0:X8}: [{1}]"-f$off,(Hex $cur))
}

$verify=ReadBytes $off $patched.Length
if(-not(Same $verify $patched)){throw "Phase34 verification failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="34-gaia-result-force-success"
  FunctionFileOffset=("0x{0:X8}"-f$off)
  Original=(Hex $expected)
  Patched=(Hex $patched)
  Semantics="Gaia/backend task result normalizer always writes success=0"
  KnownDirectCallers=4
  GlobalIsOnline="FALSE / unchanged"
  Phase32="normalized/original"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 34 GAIA RESULT BYPASS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Gaia/backend task result => SUCCESS (0)"
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
