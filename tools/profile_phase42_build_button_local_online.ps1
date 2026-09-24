param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE42-BUILD-LOCAL-ONLINE.exe"
$report=Join-Path $game "PHASE42-BUILD-LOCAL-ONLINE.json"

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

# Stable Phase36-only base expected after Phase40.
$baseHash="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"

# Keep global IsOnline FALSE.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
if(-not(Same (ReadBytes $globalOff 7) $globalExpected)){
  throw "Global IsOnline is not in expected FALSE state."
}

# Keep Phase36 safe GS_MessagePopup bypass active.
$popupOff=0x009168B0
[byte[]]$popupSafe=@(0x31,0xC0,0xC2,0x18,0x00)
if(-not(Same (ReadBytes $popupOff 5) $popupSafe)){
  throw "Phase36 popup bypass is not active. Run Phase40 restore first."
}

# Exact local connectivity branch inside the build/tutorial button handler.
# Handler begins at file 0x00686D60.
# 0x00686D96 calls global IsOnline.
# Then:
#   test al,al
#   jne 0x00686F88
#
# Since global IsOnline intentionally stays FALSE, Phase42 forces ONLY this
# branch to the same continuation that the handler would take when online.
$off=0x00686DA4
[byte[]]$expected=@(0x0F,0x85,0xDE,0x01,0x00,0x00)
[byte[]]$patched =@(0xE9,0xDF,0x01,0x00,0x00,0x90)

$cur=ReadBytes $off 6
$status=""
if(Same $cur $patched){
  $status="already-patched"
}elseif(Same $cur $expected){
  $h=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
  if($h-ne$baseHash){
    throw ("Unexpected pre-Phase42 hash: "+$h+" (expected stable Phase36-only "+$baseHash+")")
  }
  if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
  WriteBytes $off $patched
  $status="patched"
}else{
  throw ("Unexpected bytes at build local-online branch: "+(Hex $cur))
}

if(-not(Same (ReadBytes $off 6) $patched)){throw "Phase42 verification failed"}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="42-build-button-local-online"
  HandlerFileOffset="0x00686D60"
  IsOnlineCallFileOffset="0x00686D96"
  ForcedBranchFileOffset="0x00686DA4"
  Original=(Hex $expected)
  Patched=(Hex $patched)
  Behavior="force only build/tutorial handler to online continuation at 0x00686F88"
  GlobalIsOnline="FALSE / unchanged"
  Phase36PopupBypass="ACTIVE"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 42 BUILD BUTTON LOCAL-ONLINE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Build/tutorial handler now takes its local online continuation."
Write-Host "Global IsOnline remains FALSE."
Write-Host "Phase36 popup bypass remains ACTIVE."
Write-Host ("AMS SHA256: "+$hash)
