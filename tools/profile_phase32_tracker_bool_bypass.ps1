param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE32-TRACKER-BOOL.exe"
$report=Join-Path $game "PHASE32-TRACKER-BOOL.json"

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
function Hex([byte[]]$b){return (($b|ForEach-Object{$_.ToString("X2")})-join" ")}

# AVAsphaltConnectivityTracker secondary-vtable bool getter:
# xor eax,eax ; cmp [ecx+5C],eax ; setne al ; ret
$off=0x0098CF80
[byte[]]$expected=@(0x33,0xC0,0x39,0x41,0x5C,0x0F,0x95,0xC0,0xC3)
[byte[]]$patched=@(0xB0,0x01,0xC3,0x90,0x90,0x90,0x90,0x90,0x90)

# Preserve the known safe global IsOnline=false patch.
$globalOff=0x00BACDD0
[byte[]]$globalExpected=@(0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
$g=ReadBytes $globalOff $globalExpected.Length
if(-not(Same $g $globalExpected)){
  throw ("Global IsOnline is not in expected offline-safe state at 0x{0:X8}: [{1}]"-f$globalOff,(Hex $g))
}

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
  throw ("Unexpected bytes at 0x{0:X8}. Expected [{1}] or patched [{2}], found [{3}]"-f$off,(Hex $expected),(Hex $patched),(Hex $cur))
}

$verify=ReadBytes $off $patched.Length
if(-not(Same $verify $patched)){throw "Phase32 verification failed."}

$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="32-connectivity-tracker-virtual-bool-force-true"
  FunctionFileOffset=("0x{0:X8}"-f$off)
  Original=(Hex $expected)
  Patched=(Hex $patched)
  Semantics="force AVAsphaltConnectivityTracker virtual bool getter true"
  GlobalIsOnlineState="FALSE / unchanged"
  Status=$status
  AMS_SHA256=$hash
  Backup=$backup
}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 32 TRACKER BOOL BYPASS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "AVAsphaltConnectivityTracker virtual bool => TRUE"
Write-Host "Global IsOnline remains FALSE."
Write-Host ("AMS SHA256: "+$hash)
