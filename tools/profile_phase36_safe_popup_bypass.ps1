param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE36-SAFE-POPUP-BYPASS.exe"
$report=Join-Path $game "PHASE36-SAFE-POPUP-BYPASS.json"

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

# Known-safe global IsOnline policy.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw ("Global IsOnline is not in expected FALSE state.")
}

# Roll back the broken Phase35 hook and code cave if present.
$hookOff=0x009168B0
$caveOff=0x004693C1

[byte[]]$hookOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$phase35Hook=@(0xE9,0x0C,0x2B,0xB5,0xFF)

[byte[]]$caveOrig=New-Object byte[] 47
for($i=0;$i-lt47;$i++){$caveOrig[$i]=0xCC}
[byte[]]$phase35Cave=@(
  0x8B,0x44,0x24,0x04,0x8B,0x00,0x85,0xC0,0x74,0x1B,
  0x8B,0x00,0x85,0xC0,0x74,0x15,
  0x81,0x78,0x01,0x53,0x54,0x52,0x5F,0x75,0x0C,
  0x81,0x78,0x0E,0x49,0x4E,0x54,0x45,0x75,0x03,
  0xC2,0x18,0x00,
  0x55,0x8B,0xEC,0x6A,0xFF,
  0xE9,0xC5,0xD4,0x4A,0x00
)

$hookCur=ReadBytes $hookOff 5
$caveCur=ReadBytes $caveOff 47
$phase35Normalized=$false

if(Same $hookCur $phase35Hook){
  if(-not(Same $caveCur $phase35Cave)){throw "Phase35 hook exists but cave bytes are unexpected."}
  WriteBytes $hookOff $hookOrig
  WriteBytes $caveOff $caveOrig
  $phase35Normalized=$true
}elseif(-not(Same $hookCur $hookOrig)){
  # Phase36 may already be installed; checked below.
  [byte[]]$phase36Patch=@(0x31,0xC0,0xC2,0x18,0x00)
  if(-not(Same $hookCur $phase36Patch)){
    throw ("Unexpected popup wrapper bytes: "+(Hex $hookCur))
  }
}

# Safe Phase36: suppress the wrapper without touching any argument memory.
# Original function itself ends in RET 18h, so this preserves its real calling convention.
[byte[]]$safePatch=@(0x31,0xC0,0xC2,0x18,0x00) # xor eax,eax ; ret 18h

$cur=ReadBytes $hookOff 5
$status=""
if(Same $cur $safePatch){
  $status="already-patched"
}elseif(Same $cur $hookOrig){
  # After rolling back Phase35, the expected baseline is the stable pre-Phase35 AMS.
  $baseline=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  if($baseline-ne"3979935f4740096a8518ef031679787ad40bc4a84f533e15b620a5e06117f9bb"){
    throw ("Unexpected normalized AMS hash before Phase36: "+$baseline)
  }
  if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
  WriteBytes $hookOff $safePatch
  $status="patched"
}else{
  throw ("Cannot apply Phase36 at popup wrapper. Current=["+(Hex $cur)+"]")
}

if(-not(Same (ReadBytes $hookOff 5) $safePatch)){throw "Phase36 verification failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="36-safe-gs-messagepopup-bypass"
  WrapperFileOffset="0x009168B0"
  WrapperPreferredVA="0x00D174B0"
  Original=(Hex $hookOrig)
  Patched=(Hex $safePatch)
  Semantics="xor eax,eax; ret 0x18 -- suppress wrapper without dereferencing arguments"
  Phase35Normalized=$phase35Normalized
  Phase35CodeCaveRestored=$true
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 36 SAFE POPUP BYPASS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Broken Phase35 hook/cave: removed."
Write-Host "GS_MessagePopup wrapper: safe early return (RET 18h)."
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
