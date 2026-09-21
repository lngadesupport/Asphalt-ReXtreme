param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE27-WINRT-INTERNETACCESS.exe"
$report=Join-Path $game "PHASE27-WINRT-INTERNETACCESS.json"

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

# Make sure no running instance keeps the image mapped.

function ReadBytes([int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{
    $fs.Position=$Offset
    [byte[]]$b=New-Object byte[] $Count
    if($fs.Read($b,0,$Count)-ne $Count){throw ("Short read at 0x{0:X8}"-f$Offset)}
    return $b
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length-ne$b.Length){return $false}
  for($i=0;$i-lt$a.Length;$i++){if($a[$i]-ne$b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){return (($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# Phase26-proven helper:
# 0x00D2E320: function calls WinRT connectivity wrapper, then GetNetworkConnectivityLevel,
# compares the returned enum with 3 (InternetAccess), and returns bool.
$off=0x00D2E320
[byte[]]$expected=@(0x55,0x8B,0xEC)
[byte[]]$patched=@(0xB0,0x01,0xC3)  # mov al,1 ; ret

# Keep known global game IsOnline getter OFFLINE; Phase11 showed forcing it globally true freezes.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
$g=ReadBytes $globalOff $globalExpected.Length
if(-not(Same $g $globalExpected)){
  throw ("Global IsOnline bytes are not the expected offline-safe state at 0x{0:X8}: [{1}]"-f$globalOff,(Hex $g))
}

$cur=ReadBytes $off 3
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
  throw ("Unexpected bytes at 0x{0:X8}. Expected [{1}] or patched [{2}], found [{3}]"-f$off,(Hex $expected),(Hex $patched),(Hex $cur))
}

$verify=ReadBytes $off 3
if(-not(Same $verify $patched)){throw "Phase27 verification failed."}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="27-winrt-internetaccess-force-true"
  PatcherVersion="phase27-v2-no-native-taskkill-error"
  Strategy="force only WinRT InternetAccess predicate true"
  FunctionFileOffset=("0x{0:X8}"-f$off)
  Original="55 8B EC ..."
  Patched="B0 01 C3"
  GlobalIsOnlineFileOffset=("0x{0:X8}"-f$globalOff)
  GlobalIsOnlineState="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 27 WINRT INTERNETACCESS BYPASS APPLIED (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "0x00D2E320 => mov al,1 ; ret"
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
