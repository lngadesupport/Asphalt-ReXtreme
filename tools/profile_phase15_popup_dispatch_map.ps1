param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ExpectedPhase5="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"

function Get-Hash([string]$p){
    (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Hex-Line([byte[]]$d,[int]$Offset,[int]$Count=16){
    $end=[Math]::Min($d.Length,$Offset+$Count)
    $bytes=for($i=$Offset;$i -lt $end;$i++){$d[$i].ToString("X2")}
    "0x{0:X8}: {1}" -f $Offset,($bytes -join " ")
}
function S8([byte]$b){if($b -ge 0x80){return [int]$b-0x100};return [int]$b}

$candidates=@(
    (Join-Path $GameRoot "_PROFILE_PHASE14_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE13_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
    (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.exe")
)

$Ams=$null
foreach($p in $candidates){
    if((Test-Path -LiteralPath $p -PathType Leaf) -and ((Get-Hash $p) -eq $ExpectedPhase5)){
        $Ams=$p
        break
    }
}
if($null -eq $Ams){throw "Verified Phase 5 AMS not found."}

[byte[]]$d=[IO.File]::ReadAllBytes($Ams)

$targets=@(
    [pscustomobject]@{
        Name="Popup dispatcher family A"
        Center=[Convert]::ToInt32("00870510",16)
        Start=[Convert]::ToInt32("00870280",16)
        End=[Convert]::ToInt32("00870880",16)
    },
    [pscustomobject]@{
        Name="Popup dispatcher family B"
        Center=[Convert]::ToInt32("009168B0",16)
        Start=[Convert]::ToInt32("00916620",16)
        End=[Convert]::ToInt32("00916E20",16)
    }
)

function Decode-Flow([byte[]]$d,[int]$Start,[int]$End){
    $rows=New-Object System.Collections.Generic.List[object]
    for($i=$Start;$i -lt $End;$i++){
        $op=$d[$i]
        if(($op -eq 0xE8 -or $op -eq 0xE9) -and $i+4 -lt $d.Length){
            $rel=[BitConverter]::ToInt32($d,$i+1)
            $dest=$i+5+$rel
            $rows.Add([pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=$(if($op -eq 0xE8){"CALL"}else{"JMP"})
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+4)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            })
            $i+=4
            continue
        }
        if($op -ge 0x70 -and $op -le 0x7F -and $i+1 -lt $d.Length){
            $dest=$i+2+(S8 $d[$i+1])
            $rows.Add([pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=("Jcc-{0:X2}" -f $op)
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+1)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            })
            $i++
            continue
        }
        if($op -eq 0x0F -and $i+5 -lt $d.Length -and $d[$i+1] -ge 0x80 -and $d[$i+1] -le 0x8F){
            $rel=[BitConverter]::ToInt32($d,$i+2)
            $dest=$i+6+$rel
            $rows.Add([pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=("Jcc-0F{0:X2}" -f $d[$i+1])
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+5)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            })
            $i+=5
        }
    }
    return $rows
}

$out=Join-Path $GameRoot "_PROFILE_PHASE15_POPUP_DISPATCH_MAP"
if(Test-Path -LiteralPath $out){Remove-Item -LiteralPath $out -Recurse -Force}
New-Item -ItemType Directory -Path $out -Force|Out-Null

$txt=New-Object System.Collections.Generic.List[string]
$txt.Add("PHASE 15 - POPUP DISPATCHER FOCUS")
$txt.Add("Source: $Ams")
$txt.Add("SHA256: $(Get-Hash $Ams)")
$txt.Add("Read-only: True")
$txt.Add("Reason: local profile/tutorial persistence is now confirmed; isolate only the lobby no-internet modal.")
$txt.Add("")

foreach($t in $targets){
    $txt.Add(("===== {0} center=0x{1:X8} =====" -f $t.Name,$t.Center))
    $txt.Add("HEX:")
    for($o=$t.Start;$o -lt $t.End;$o+=16){
        $txt.Add((Hex-Line $d $o 16))
    }
    $txt.Add("")
    $txt.Add("CONTROL FLOW:")
    foreach($r in @(Decode-Flow $d $t.Start $t.End)){
        $txt.Add(("{0}  {1,-9} -> {2}  [{3}]" -f $r.Offset,$r.Kind,$r.Destination,$r.Bytes))
    }
    $txt.Add("")
}

# Focused caller sites known to use these two dispatcher families.
$callers=@(
    0x004FBF40,0x004FD905,0x0064A9D9,0x00B0CBCC,
    0x00746F2C,0x008DA305,0x0091727C,0x00A680C3
)
$txt.Add("===== KNOWN NETWORK POPUP CALLERS =====")
foreach($c in $callers){
    $start=[Math]::Max(0,$c-96);$end=[Math]::Min($d.Length,$c+128)
    $txt.Add(("--- caller 0x{0:X8} ---" -f $c))
    for($o=$start;$o -lt $end;$o+=16){$txt.Add((Hex-Line $d $o 16))}
}
$txt.Add("")

$current=Join-Path $GameRoot "AMS.exe"
$summary=[ordered]@{
    Phase="15-popup-dispatch-focus"
    ReadOnly=$true
    SourceAMS=$Ams
    SourceAMS_SHA256=(Get-Hash $Ams)
    CurrentAMS_SHA256=$(if(Test-Path -LiteralPath $current){Get-Hash $current}else{""})
    LocalPersistenceConfirmedByRuntime=$true
    Targets=@("0x00870510","0x009168B0")
    Goal="Identify a minimal central bypass for the lobby no-internet modal without touching profile, tutorial, economy, or global connectivity."
}
$summary|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $out "SUMMARY.json") -Encoding UTF8
$txt|Set-Content -LiteralPath (Join-Path $out "PHASE15-POPUP-DISPATCH-FOCUS.txt") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE15-POPUP-DISPATCH-MAP.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 15 - POPUP DISPATCHER FOCUS COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Game modified: False"
Write-Host "Profile/tutorial untouched: True"
Write-Host ("Output: {0}" -f $zip)
Write-Host ""
