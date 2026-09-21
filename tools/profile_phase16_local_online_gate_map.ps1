param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$Expected="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"

function H([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
$c=@(
 (Join-Path $GameRoot "_PROFILE_PHASE15_BACKUP\AMS.phase5.bak"),
 (Join-Path $GameRoot "_PROFILE_PHASE14_BACKUP\AMS.phase5.bak"),
 (Join-Path $GameRoot "_PROFILE_PHASE13_BACKUP\AMS.phase5.bak"),
 (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
 (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
 (Join-Path $GameRoot "AMS.exe")
)
$Ams=$null
foreach($p in $c){if((Test-Path $p) -and ((H $p)-eq $Expected)){$Ams=$p;break}}
if($null -eq $Ams){throw "Verified Phase 5 AMS not found."}
[byte[]]$d=[IO.File]::ReadAllBytes($Ams)

$target=[Convert]::ToInt32("00BACDD0",16)
$rows=@()
for($i=0;$i -le $d.Length-5;$i++){
  if($d[$i] -ne 0xE8){continue}
  $rel=[BitConverter]::ToInt32($d,$i+1)
  $dest=$i+5+$rel
  if($dest -eq $target){
    $start=[Math]::Max(0,$i-96)
    $end=[Math]::Min($d.Length,$i+160)
    $ctx=New-Object System.Collections.Generic.List[string]
    for($o=$start;$o -lt $end;$o+=16){
      $n=[Math]::Min(16,$end-$o)
      $ctx.Add(("0x{0:X8}: {1}" -f $o,(($d[$o..($o+$n-1)]|ForEach-Object{$_.ToString("X2")}) -join " ")))
    }
    $rows += [pscustomobject]@{
      CallOffset=("0x{0:X8}" -f $i)
      NearLobby=($i -ge 0x00916000 -and $i -le 0x00918000)
      Context=($ctx -join [Environment]::NewLine)
    }
  }
}

$out=Join-Path $GameRoot "_PROFILE_PHASE16_LOCAL_ONLINE_GATE_MAP"
if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Path $out -Force|Out-Null

$summary=[ordered]@{
  Phase="16-local-online-gate-map"
  ReadOnly=$true
  SourceAMS=$Ams
  SourceSHA256=(H $Ams)
  IsOnlineGetter="0x00BACDD0"
  CallCount=$rows.Count
  LobbyWindowCallCount=@($rows|Where-Object{$_.NearLobby}).Count
  Calls=@($rows|ForEach-Object{[ordered]@{CallOffset=$_.CallOffset;NearLobby=$_.NearLobby}})
}
$summary|ConvertTo-Json -Depth 5|Set-Content (Join-Path $out "SUMMARY.json") -Encoding UTF8

$txt=New-Object System.Collections.Generic.List[string]
$txt.Add("PHASE 16 - LOCAL ONLINE GATE MAP")
$txt.Add("Source: $Ams")
$txt.Add("SHA256: $(H $Ams)")
$txt.Add("Getter: 0x00BACDD0")
$txt.Add("")
foreach($r in $rows){
  $txt.Add(("===== CALL {0} NearLobby={1} =====" -f $r.CallOffset,$r.NearLobby))
  $txt.Add($r.Context)
  $txt.Add("")
}
$txt|Set-Content (Join-Path $out "ISONLINE-CALLS.txt") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE16-LOCAL-ONLINE-GATE-MAP.zip"
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 16 - LOCAL ONLINE GATE MAP COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("IsOnline calls found: {0}" -f $rows.Count)
Write-Host ("Calls in lobby window: {0}" -f @($rows|Where-Object{$_.NearLobby}).Count)
Write-Host ("Output: {0}" -f $zip)
