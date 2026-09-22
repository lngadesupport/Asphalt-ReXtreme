param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE48-CRAFTCAR-COMPLETION.exe"
$report=Join-Path $game "PHASE48-CRAFTCAR-DIRECT-COMPLETION.json"

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
$currentHash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

# Idempotence: if already patched, don't require the pre-patch hash.
$siteOff=0x00687110
[byte[]]$siteOrig=@(0x8B,0x55,0xEC,0x8B,0xCE)
[byte[]]$sitePatch=@(0xE9,0xAC,0x22,0xDE,0xFF)

$caveOff=0x004693C1
[byte[]]$caveOrig=New-Object byte[] 47
for($i=0;$i-lt$caveOrig.Length;$i++){$caveOrig[$i]=0xCC}

# Cave VA 0x00869FC1:
#   mov ecx,[ebp-14h]    ; observer = parent+0x298
#   push 0               ; arg3: no auxiliary shared_ptr
#   push 0               ; arg2: unused by callback
#   push 0               ; arg1: result/status SUCCESS
#   call 0x00AA4D00      ; real CraftCar UI completion callback
#   jmp  0x00A87D3C      ; original handler cleanup, after spinner/start block
[byte[]]$stub=@(
  0x8B,0x4D,0xEC,
  0x6A,0x00,
  0x6A,0x00,
  0x6A,0x00,
  0xE8,0x31,0xAD,0x23,0x00,
  0xE9,0x68,0xDD,0x21,0x00
)
[byte[]]$cavePatch=New-Object byte[] 47
for($i=0;$i-lt$cavePatch.Length;$i++){$cavePatch[$i]=0xCC}
[Array]::Copy($stub,0,$cavePatch,0,$stub.Length)

# Stable invariants.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw "Global IsOnline is not in the expected FALSE state."
}

$popupOff=0x009168B0
[byte[]]$popupExpected=@(0x31,0xC0,0xC2,0x18,0x00)
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){
  throw "Phase36 popup bypass is not active."
}

$curSite=ReadBytes $siteOff 5
$curCave=ReadBytes $caveOff 47
$status=""

if((Same $curSite $sitePatch)-and(Same $curCave $cavePatch)){
  $status="already-patched"
}elseif((Same $curSite $siteOrig)-and(Same $curCave $caveOrig)){
  if($currentHash-ne$stableHash){
    throw ("Unexpected pre-Phase48 AMS hash: "+$currentHash+"; expected "+$stableHash)
  }

  if(-not(Test-Path -LiteralPath $backup)){
    Copy-Item -LiteralPath $ams -Destination $backup -Force
  }

  # Install cave first, redirect execution last.
  WriteBytes $caveOff $cavePatch
  WriteBytes $siteOff $sitePatch
  $status="patched"
}else{
  throw ("Unexpected Phase48 state. Site=["+(Hex $curSite)+"] CavePrefix=["+(Hex ($curCave[0..18]))+"]")
}

if(-not(Same (ReadBytes $siteOff 5) $sitePatch)){throw "Phase48 site verification failed"}
if(-not(Same (ReadBytes $caveOff 47) $cavePatch)){throw "Phase48 cave verification failed"}
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){throw "Global IsOnline changed unexpectedly"}
if(-not(Same (ReadBytes $popupOff 5) $popupExpected)){throw "Phase36 changed unexpectedly"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

[ordered]@{
  Phase="48-craftcar-direct-completion"
  BuildHandlerFileOffset="0x00686D60"
  HookFileOffset="0x00687110"
  HookPreferredVA="0x00A87D10"
  CaveFileOffset="0x004693C1"
  CavePreferredVA="0x00869FC1"
  CompletionCallbackPreferredVA="0x00AA4D00"
  ResumeFileOffset="0x0068713C"
  ResumePreferredVA="0x00A87D3C"
  StatusArgument=0
  Behavior=@(
    "uses the real CraftCar UI completion callback",
    "clears request pending fields through original callback",
    "skips remote request start path",
    "skips spinner activation block",
    "resumes at original local cleanup"
  )
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 48 CRAFTCAR DIRECT COMPLETION APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Real CraftCar completion callback: status 0."
Write-Host "Remote start/spinner activation: skipped."
Write-Host "Phase36: active."
Write-Host "Global IsOnline: FALSE."
Write-Host ("AMS SHA256: "+$hash)
