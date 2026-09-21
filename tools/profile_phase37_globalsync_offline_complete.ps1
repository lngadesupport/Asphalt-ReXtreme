param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE37-GLOBALSYNC-OFFLINE.exe"
$report=Join-Path $game "PHASE37-GLOBALSYNC-OFFLINE.json"

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

# Keep the proven safe global policy.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw "Global IsOnline is not in expected FALSE state."
}

# Ensure Phase36 popup suppression remains active.
$popupOff=0x009168B0
[byte[]]$popupOrig=@(0x55,0x8B,0xEC,0x6A,0xFF)
[byte[]]$popupSafe=@(0x31,0xC0,0xC2,0x18,0x00)
$popupCur=ReadBytes $popupOff 5
if(Same $popupCur $popupOrig){
  WriteBytes $popupOff $popupSafe
}elseif(-not(Same $popupCur $popupSafe)){
  throw ("Unexpected GS_MessagePopup wrapper bytes: "+(Hex $popupCur))
}

# GlobalSync::Request submit/start path.
# Preferred VA 0x00CD4602 / file offset 0x008D3A02
#
# Original:
#   mov [edi+48],1        ; state=PENDING
#   mov ecx,[0193A1D0]
#   call ...
#   mov esi,eax
#   lea eax,[ebp-14]
#
# Offline Campaign Edition:
#   mov [edi+48],1
#   push 0               ; ignored second completion arg
#   push 0               ; result code = SUCCESS
#   mov ecx,edi
#   call 0x00CDC560      ; built-in completion + observer dispatch
#   jmp  0x00CD4683      ; normal cleanup, skip transport
$off=0x008D3A02
[byte[]]$expected=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,
  0x8B,0x0D,0xD0,0xA1,0x93,0x01,
  0xE8,0x1C,0x5F,0xAB,0xFF,
  0x8B,0xF0,0x8D,0x45,0xEC
)
[byte[]]$patched=@(
  0xC7,0x47,0x48,0x01,0x00,0x00,0x00,
  0x6A,0x00,
  0x6A,0x00,
  0x8B,0xCF,
  0xE8,0x4C,0x7F,0x00,0x00,
  0xE9,0x6A,0x00,0x00,0x00
)

$cur=ReadBytes $off $expected.Length
$status=""
if(Same $cur $patched){
  $status="already-patched"
}elseif(Same $cur $expected){
  $pre=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  # Known valid states: clean baseline or Phase36-only.
  if($pre-ne"3979935f4740096a8518ef031679787ad40bc4a84f533e15b620a5e06117f9bb" -and
     $pre-ne"22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"){
    # Allow an already-Phase36 build even if metadata changes elsewhere only
    # when all guarded patch sites match exactly.
    Write-Host ("[INFO] Hash nao listado, mas bytes guardados estao corretos: "+$pre) -ForegroundColor Yellow
  }
  if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
  WriteBytes $off $patched
  $status="patched"
}else{
  throw ("Unexpected GlobalSync submit bytes at 0x{0:X8}: [{1}]"-f$off,(Hex $cur))
}

if(-not(Same (ReadBytes $off $patched.Length) $patched)){throw "Phase37 GlobalSync verification failed"}
if(-not(Same (ReadBytes $popupOff 5) $popupSafe)){throw "Phase36 popup bypass is not active"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="37-globalsync-offline-complete"
  GlobalSyncSubmitFileOffset="0x008D3A02"
  GlobalSyncSubmitPreferredVA="0x00CD4602"
  CompletionPreferredVA="0x00CDC560"
  Behavior="all requests using this GlobalSync submit path complete immediately with code 0 and skip transport"
  IntendedCoverage=@(
    "vehicle purchase/assembly waits",
    "post-career-event waits",
    "career request family",
    "other GlobalSync-backed mandatory online waits"
  )
  Phase36PopupBypass="ACTIVE"
  GlobalIsOnline="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  ExpectedTestHash="a861fdfb327f2bb44f8e74b7782d3eef362b9e1580196515c8445895573d2b45"
  Backup=$backup
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 37 GLOBALSYNC OFFLINE-COMPLETE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "GlobalSync requests: immediate local completion, result code 0."
Write-Host "Transport path: skipped."
Write-Host "Phase36 popup bypass: active."
Write-Host "Global IsOnline: FALSE."
Write-Host ("AMS SHA256: "+$hash)
