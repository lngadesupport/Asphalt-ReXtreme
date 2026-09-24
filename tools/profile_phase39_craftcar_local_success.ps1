param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE39-CRAFTCAR.exe"
$report=Join-Path $game "PHASE39-CRAFTCAR-LOCAL-SUCCESS.json"

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

if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}

# Stable global policy.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw "Global IsOnline is not in expected FALSE state."
}

# Phase36 remains active.
$popupOff=0x009168B0
[byte[]]$popupOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$popupSafe=@(0x31,0xC0,0xC2,0x18,0x00)
$popupCur=ReadBytes $popupOff 5
if(Same $popupCur $popupOrig){
  WriteBytes $popupOff $popupSafe
}elseif(-not(Same $popupCur $popupSafe)){
  throw ("Unexpected GS_MessagePopup wrapper bytes: "+(Hex $popupCur))
}

# Phase37 must be normalized.
$p37Off=0x008D3A02
[byte[]]$p37Orig=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,
  0x8B,0x0D,0xD0,0xA1,0x93,0x01,
  0xE8,0x1C,0x5F,0xAB,0xFF,
  0x8B,0xF0,0x8D,0x45,0xEC
)
[byte[]]$p37Patch=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,
  0x6A,0x00,0x6A,0x00,0x8B,0xCF,
  0xE8,0x4C,0x7F,0x00,0x00,
  0xE9,0x6A,0x00,0x00,0x00
)
$p37=ReadBytes $p37Off $p37Orig.Length
if(Same $p37 $p37Patch){
  WriteBytes $p37Off $p37Orig
}elseif(-not(Same $p37 $p37Orig)){
  throw ("Unexpected Phase37 site bytes: "+(Hex $p37))
}

# Normalize failed Phase38 OnlinePurchase experiment if present.
$p38ControllerOff=0x005FC518
[byte[]]$p38ControllerOrig=@(0x8B,0x4E,0x08,0x83,0xEC)
[byte[]]$p38ControllerPatch=@(0xE9,0xD3,0x50,0x05,0x00)

$p38StubOff=0x006515F0
[byte[]]$p38StubOrig=@(
  0x55,0x8B,0xEC,0x6A,0xFF,0x68,0x00,0xCD,0x3E,0x01,0x64,0xA1,0x00,0x00,0x00,0x00,
  0x50,0x81,0xEC,0xBC,0x00,0x00,0x00,0xA1,0x00,0x7A,0x89,0x01,0x33,0xC5,0x89,0x45,
  0xF0,0x53,0x56,0x57,0x50,0x8D,0x45,0xF4,0x64,0xA3,0x00,0x00,0x00,0x00,0x8B,0xC1,
  0x89,0x45,0xE8,0x8B,0x0D,0x90,0x89,0x94,0x01,0xC7,0x45,0xFC,0x00,0x00,0x00,0x00,
  0xC7,0x85,0x58,0xFF,0xFF,0xFF,0x90,0xCE,0xA5,0x00,0x89,0x85,0x54,0xFF,0xFF,0xFF
)
[byte[]]$p38StubPatch=@(
  0x8B,0x56,0x08,0x85,0xD2,0x74,0x44,0x83,0xEC,0x14,0x31,0xC0,0x89,0x04,0x24,0x8B,
  0x42,0x50,0x89,0x44,0x24,0x04,0x8B,0x42,0x54,0x89,0x44,0x24,0x08,0x85,0xC0,0x74,
  0x04,0xF0,0xFF,0x40,0x04,0xC7,0x44,0x24,0x0C,0x00,0x00,0x00,0x00,0xC7,0x44,0x24,
  0x10,0x00,0x00,0x00,0x00,0x8D,0x04,0x24,0x50,0x89,0xF1,0xE8,0x60,0x48,0xFC,0xFF,
  0x8D,0x0C,0x24,0xE8,0x68,0xFE,0xF9,0xFF,0x83,0xC4,0x14,0xE9,0x0B,0xAF,0xFA,0xFF
)

$c38=ReadBytes $p38ControllerOff 5
$s38=ReadBytes $p38StubOff 80
$phase38Normalized=$false
if((Same $c38 $p38ControllerPatch) -and (Same $s38 $p38StubPatch)){
  WriteBytes $p38ControllerOff $p38ControllerOrig
  WriteBytes $p38StubOff $p38StubOrig
  $phase38Normalized=$true
}elseif((Same $c38 $p38ControllerOrig) -and (Same $s38 $p38StubOrig)){
  # already clean
}else{
  throw ("Unexpected Phase38 state. Controller=["+(Hex $c38)+"]")
}

# Exact tutorial/build-car path: prokitsv2::CraftCarRequestImpl
#
# Start wrapper at VA 0x009A4BA0 / file 0x005A3FA0 originally builds
# scripts/cars/craft_car.php and starts the remote request.
# Replace it with a direct local success callback:
#   push 0 ; fake Json pointer (never dereferenced by patched handler)
#   push 0 ; result code SUCCESS
#   call CraftCarRequestImpl::result handler
#   ret
$craftStartOff=0x005A3FA0
[byte[]]$craftStartOrig=@(0xFF,0x71,0x68,0xE8,0x08,0x00,0x00,0x00,0xC3,0xCC)
[byte[]]$craftStartPatch=@(0x6A,0x00,0x6A,0x00,0xE8,0xF7,0xFC,0xFF,0xFF,0xC3)

# Result handler at VA 0x009A48A0.
# After the normal prologue, skip base/network JSON parsing and jump directly
# to the original observer-dispatch path with EAX=0 (success).
$craftHandlerOff=0x005A3CB6
[byte[]]$craftHandlerOrig=@(0x56,0xFF,0x75,0x08,0x8B,0xF9,0xE8,0x2F,0xFF,0x3F,0x00)
[byte[]]$craftHandlerPatch=@(0x8B,0xF9,0x31,0xC0,0xE9,0x89,0x01,0x00,0x00,0x90,0x90)

$startCur=ReadBytes $craftStartOff 10
$handlerCur=ReadBytes $craftHandlerOff 11
$status=""
if((Same $startCur $craftStartPatch) -and (Same $handlerCur $craftHandlerPatch)){
  $status="already-patched"
}elseif((Same $startCur $craftStartOrig) -and (Same $handlerCur $craftHandlerOrig)){
  WriteBytes $craftHandlerOff $craftHandlerPatch
  WriteBytes $craftStartOff $craftStartPatch
  $status="patched"
}else{
  throw ("Unexpected CraftCar patch state. Start=["+(Hex $startCur)+"] Handler=["+(Hex $handlerCur)+"]")
}

if(-not(Same (ReadBytes $craftStartOff 10) $craftStartPatch)){throw "Phase39 CraftCar start verification failed"}
if(-not(Same (ReadBytes $craftHandlerOff 11) $craftHandlerPatch)){throw "Phase39 CraftCar handler verification failed"}
if(-not(Same (ReadBytes $popupOff 5) $popupSafe)){throw "Phase36 popup bypass is not active"}
if(-not(Same (ReadBytes $p37Off $p37Orig.Length) $p37Orig)){throw "Phase37 is not normalized"}
if(-not(Same (ReadBytes $p38ControllerOff 5) $p38ControllerOrig)){throw "Phase38 controller is not normalized"}
if(-not(Same (ReadBytes $p38StubOff 80) $p38StubOrig)){throw "Phase38 stub is not normalized"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="39-craftcar-local-success"
  TargetClass="prokitsv2::CraftCarRequestImpl"
  Endpoint="scripts/cars/craft_car.php (bypassed)"
  CraftStartFileOffset="0x005A3FA0"
  CraftStartPreferredVA="0x009A4BA0"
  CraftResultHandlerFileOffset="0x005A3CB6"
  CraftResultHandlerPreferredVA="0x009A48B6"
  Behavior="CraftCar request completes immediately through its original observer-dispatch path with result 0; remote JSON is not required"
  IntendedCoverage=@(
    "tutorial first-car assembly",
    "blueprint vehicle assembly",
    "other CraftCarRequestImpl vehicle builds"
  )
  Phase38Normalized=$phase38Normalized
  Phase37="original"
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  ExpectedHash="2a33ba33874f66af40f092c4ad29b524606edc1fc43ee96ea49a86c230455b5b"
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 39 CRAFTCAR LOCAL SUCCESS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "CraftCarRequestImpl: backend bypassed."
Write-Host "Original CraftCar observer dispatch: used with result 0."
Write-Host "Phase38: normalized back."
Write-Host "Phase36 popup bypass: active."
Write-Host "Global IsOnline: FALSE."
Write-Host ("AMS SHA256: "+$hash)
