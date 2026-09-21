param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE21-INTERNAL-OFFLINE.exe"
$report=Join-Path $game "PHASE21-INTERNAL-OFFLINE.json"

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}


function ReadB([int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{
    $fs.Position=$Offset
    [byte[]]$b=New-Object byte[] $Count
    if($fs.Read($b,0,$Count) -ne $Count){throw ("Short read at 0x{0:X8}" -f $Offset)}
    return $b
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length -ne $b.Length){return $false}
  for($i=0;$i -lt $a.Length;$i++){if($a[$i] -ne $b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")}) -join " ")}
function WriteB([IO.FileStream]$fs,[int]$Offset,[byte[]]$Bytes){
  $fs.Position=$Offset
  $fs.Write($Bytes,0,$Bytes.Length)
}
function Normalize([IO.FileStream]$fs,[int]$off,[byte[]]$original,[byte[]]$oldPatch,[string]$name){
  $cur=ReadB $off $original.Length
  if(Same $cur $oldPatch){
    WriteB $fs $off $original
    return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Action="restored-previous-test"}
  }
  if(Same $cur $original){
    return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Action="already-original"}
  }
  throw ("Unexpected bytes while normalizing {0} at 0x{1:X8}: [{2}]" -f $name,$off,(Hex $cur))
}
function Patch([IO.FileStream]$fs,[int]$off,[byte[]]$expected,[byte[]]$patched,[string]$name){
  $cur=ReadB $off $expected.Length
  if(Same $cur $patched){
    return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Action="already-patched";Before=(Hex $cur);After=(Hex $patched)}
  }
  if(-not(Same $cur $expected)){
    throw ("Unexpected bytes for {0} at 0x{1:X8}. Expected [{2}], found [{3}]" -f $name,$off,(Hex $expected),(Hex $cur))
  }
  WriteB $fs $off $patched
  return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Action="patched";Before=(Hex $expected);After=(Hex $patched)}
}

if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
$before=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$events=New-Object System.Collections.Generic.List[object]
$fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try{
  # Remove Phase 20 experimental gates so Phase 21 is an isolated internal test.
  $events.Add((Normalize $fs 0x00809EAC ([byte[]]@(0x0F,0x85,0x8A,0x00,0x00,0x00)) ([byte[]]@(0xE9,0x8B,0x00,0x00,0x00,0x90)) "phase20-00809EAC"))
  $events.Add((Normalize $fs 0x008B543B ([byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00)) ([byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)) "phase20-008B543B"))
  $events.Add((Normalize $fs 0x00B24D5B ([byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00)) ([byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)) "phase20-00B24D5B"))
  $events.Add((Normalize $fs 0x00B44E9B ([byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00)) ([byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)) "phase20-00B44E9B"))

  # Remove Phase 19 backend route: Phase 21 is internal-only.
  $events.Add((Normalize $fs 0x00BAEA4B ([byte[]]@(0x22,0x68,0x50,0xA2,0x59,0x01)) ([byte[]]@(0x1C,0x68,0x40,0xC3,0x57,0x01)) "phase19-pjsmmm-route"))

  # 0x00689730: either object flag or online=true jumps over the NO_INTERNET block.
  # Force that exact common-success target without changing the global IsOnline getter.
  $events.Add((Patch $fs 0x0068973B ([byte[]]@(0x0F,0x85,0xFD,0x01,0x00,0x00)) ([byte[]]@(0xE9,0xFE,0x01,0x00,0x00,0x90)) "force-success-0068973B"))

  # These three JZ branches are taken only when IsOnline returned false and land
  # directly in the retained NO_INTERNET construction blocks.
  $events.Add((Patch $fs 0x006A464C ([byte[]]@(0x0F,0x84,0x8A,0x00,0x00,0x00)) ([byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)) "bypass-nointernet-006A464C"))
  $events.Add((Patch $fs 0x006A5E6C ([byte[]]@(0x0F,0x84,0x8A,0x00,0x00,0x00)) ([byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)) "bypass-nointernet-006A5E6C"))
  $events.Add((Patch $fs 0x006A6B3C ([byte[]]@(0x0F,0x84,0x8A,0x00,0x00,0x00)) ([byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)) "bypass-nointernet-006A6B3C"))
  $fs.Flush($true)
}finally{$fs.Dispose()}

$checks=@(
  @{O=0x0068973B;B=[byte[]]@(0xE9,0xFE,0x01,0x00,0x00,0x90)},
  @{O=0x006A464C;B=[byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)},
  @{O=0x006A5E6C;B=[byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)},
  @{O=0x006A6B3C;B=[byte[]]@(0x90,0x90,0x90,0x90,0x90,0x90)}
)
foreach($x in $checks){
  if(-not(Same (ReadB $x.O $x.B.Length) $x.B)){throw ("Verification failed at 0x{0:X8}" -f $x.O)}
}

$after=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="21-internal-force-offline"
  PatcherVersion="phase21-v2-no-native-taskkill-error"
  Strategy="internal-code-only"
  GlobalIsOnline="unchanged-false"
  BackendEmulator="not-required"
  BeforeSHA256=$before
  AfterSHA256=$after
  Backup=$backup
  Changes=$events.ToArray()
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 21 INTERNAL OFFLINE PATCH APPLIED (v2)" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Global IsOnline remains FALSE."
Write-Host "Backend emulator is not required for this test."
Write-Host ("AMS SHA256: "+$after)
