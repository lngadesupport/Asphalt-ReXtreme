param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE38-ONLINEPURCHASE.exe"
$report=Join-Path $game "PHASE38-ONLINEPURCHASE-LOCAL-SUCCESS.json"

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

# Back up exactly what the user currently has before normalization/patching.
if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}

# Keep global IsOnline in the proven safe FALSE state.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw ("Global IsOnline is not in expected FALSE state.")
}

# Keep Phase36: GS_MessagePopup wrapper safe early-return.
$popupOff=0x009168B0
[byte[]]$popupOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$popupSafe=@(0x31,0xC0,0xC2,0x18,0x00)
$popupCur=ReadBytes $popupOff 5
if(Same $popupCur $popupOrig){
  WriteBytes $popupOff $popupSafe
}elseif(-not(Same $popupCur $popupSafe)){
  throw ("Unexpected GS_MessagePopup wrapper bytes: "+(Hex $popupCur))
}

# Phase37 was experimentally broad and did not solve OnlinePurchaseRequest.
# Normalize it back to the original GlobalSync submit path.
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
$phase37Normalized=$false
if(Same $p37 $p37Patch){
  WriteBytes $p37Off $p37Orig
  $phase37Normalized=$true
}elseif(-not(Same $p37 $p37Orig)){
  throw ("Unexpected Phase37 site bytes: "+(Hex $p37))
}

# OnlinePurchase controller:
# original at preferred VA 0x009FD118 / file 0x005FC518 begins:
#   mov ecx,[esi+08]
#   sub esp,08
# It is replaced with a jump to the now-unused unique OnlinePurchase start
# function body at 0x00A521F0, repurposed as an offline completion stub.
$controllerOff=0x005FC518
[byte[]]$controllerOrig=@(0x8B,0x4E,0x08,0x83,0xEC)
[byte[]]$controllerPatch=@(0xE9,0xD3,0x50,0x05,0x00)

# A521F0 had exactly one direct caller (this OnlinePurchase controller).
# Stub:
#   request = shop->activeRequest
#   result.status = 0
#   result.context = request->{+50,+54}
#   call original AsphaltShop::OnlinePurchaseRequestResult
#   destroy synthetic result
#   jump back to original controller cleanup at 0x009FD14B
$stubOff=0x006515F0
[byte[]]$stubOrig=@(
  0x55,0x8B,0xEC,0x6A,0xFF,0x68,0x00,0xCD,0x3E,0x01,0x64,0xA1,0x00,0x00,0x00,0x00,
  0x50,0x81,0xEC,0xBC,0x00,0x00,0x00,0xA1,0x00,0x7A,0x89,0x01,0x33,0xC5,0x89,0x45,
  0xF0,0x53,0x56,0x57,0x50,0x8D,0x45,0xF4,0x64,0xA3,0x00,0x00,0x00,0x00,0x8B,0xC1,
  0x89,0x45,0xE8,0x8B,0x0D,0x90,0x89,0x94,0x01,0xC7,0x45,0xFC,0x00,0x00,0x00,0x00,
  0xC7,0x85,0x58,0xFF,0xFF,0xFF,0x90,0xCE,0xA5,0x00,0x89,0x85,0x54,0xFF,0xFF,0xFF
)
[byte[]]$stubPatch=@(
  0x8B,0x56,0x08,0x85,0xD2,0x74,0x44,0x83,0xEC,0x14,0x31,0xC0,0x89,0x04,0x24,0x8B,
  0x42,0x50,0x89,0x44,0x24,0x04,0x8B,0x42,0x54,0x89,0x44,0x24,0x08,0x85,0xC0,0x74,
  0x04,0xF0,0xFF,0x40,0x04,0xC7,0x44,0x24,0x0C,0x00,0x00,0x00,0x00,0xC7,0x44,0x24,
  0x10,0x00,0x00,0x00,0x00,0x8D,0x04,0x24,0x50,0x89,0xF1,0xE8,0x60,0x48,0xFC,0xFF,
  0x8D,0x0C,0x24,0xE8,0x68,0xFE,0xF9,0xFF,0x83,0xC4,0x14,0xE9,0x0B,0xAF,0xFA,0xFF
)

$cCur=ReadBytes $controllerOff 5
$sCur=ReadBytes $stubOff 80
$status=""

if((Same $cCur $controllerPatch) -and (Same $sCur $stubPatch)){
  $status="already-patched"
}elseif((Same $cCur $controllerOrig) -and (Same $sCur $stubOrig)){
  # Install body first, then redirect execution.
  WriteBytes $stubOff $stubPatch
  WriteBytes $controllerOff $controllerPatch
  $status="patched"
}else{
  throw ("Unexpected Phase38 state. Controller=["+(Hex $cCur)+"] StubPrefix=["+(Hex ($sCur[0..15]))+"]")
}

if(-not(Same (ReadBytes $controllerOff 5) $controllerPatch)){throw "Phase38 controller verification failed"}
if(-not(Same (ReadBytes $stubOff 80) $stubPatch)){throw "Phase38 stub verification failed"}
if(-not(Same (ReadBytes $popupOff 5) $popupSafe)){throw "Phase36 popup bypass is not active"}
if(-not(Same (ReadBytes $p37Off $p37Orig.Length) $p37Orig)){throw "Phase37 normalization failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="38-onlinepurchase-local-success"
  PurchaseControllerFileOffset="0x005FC518"
  PurchaseControllerPreferredVA="0x009FD118"
  OfflineStubFileOffset="0x006515F0"
  OfflineStubPreferredVA="0x00A521F0"
  OriginalShopCallbackPreferredVA="0x00A16A90"
  Behavior="OnlinePurchaseRequest skips backend and invokes original AsphaltShop success callback using request-local context"
  Coverage="all purchases routed through OnlinePurchaseRequest"
  Phase37Normalized=$phase37Normalized
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  ExpectedHash="e76cd3b655f87800f8a7b1b11d09a5072313597c4771e9e1584aaba62fb67dc9"
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 38 ONLINE PURCHASE LOCAL SUCCESS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Phase37 broad GlobalSync experiment: normalized back."
Write-Host "OnlinePurchaseRequest: backend skipped."
Write-Host "Original AsphaltShop success callback: used."
Write-Host "Phase36 popup bypass: active."
Write-Host "Global IsOnline: FALSE."
Write-Host ("AMS SHA256: "+$hash)
