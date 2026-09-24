param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedPhase5 = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"

function Get-Hash([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$candidates = @(
    (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
    (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.exe")
)

$Ams = $null
foreach($p in $candidates) {
    if((Test-Path -LiteralPath $p -PathType Leaf) -and ((Get-Hash $p) -eq $ExpectedPhase5)) {
        $Ams = $p
        break
    }
}
if($null -eq $Ams) {
    throw "Verified Phase 5 AMS not found."
}

[byte[]]$d = [IO.File]::ReadAllBytes($Ams)

$FunctionStart = [Convert]::ToInt32("006A1CA0",16)
$Site05 = [Convert]::ToInt32("006A1CE7",16)
$Site06 = [Convert]::ToInt32("006A1E09",16)
$Site05Phase12Target = [Convert]::ToInt32("006A24D7",16)
$Site06Phase12Target = [Convert]::ToInt32("006A1DBA",16)
$FunctionEnd = [Convert]::ToInt32("006A2520",16)

if($FunctionStart -lt 0 -or $FunctionEnd -ge $d.Length) {
    throw "Focused age-handler range is outside AMS."
}

function Hex-Line([int]$Offset,[int]$Count=16) {
    $end = [Math]::Min($d.Length,$Offset+$Count)
    $bytes = for($i=$Offset;$i -lt $end;$i++){ $d[$i].ToString("X2") }
    "0x{0:X8}: {1}" -f $Offset,($bytes -join " ")
}

function Signed8([byte]$b) {
    if($b -ge 0x80){ return [int]$b - 0x100 }
    return [int]$b
}

function Decode-Flow([int]$Start,[int]$End) {
    $rows = @()
    for($i=$Start;$i -lt $End;$i++) {
        $op=$d[$i]
        if($op -eq 0xE8 -or $op -eq 0xE9) {
            if($i+4 -ge $d.Length){ break }
            $rel=[BitConverter]::ToInt32($d,$i+1)
            $dest=$i+5+$rel
            $rows += [pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=$(if($op -eq 0xE8){"CALL"}else{"JMP"})
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+4)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            }
            $i += 4
            continue
        }
        if($op -ge 0x70 -and $op -le 0x7F) {
            $dest=$i+2+(Signed8 $d[$i+1])
            $rows += [pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=("Jcc-{0:X2}" -f $op)
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+1)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            }
            $i++
            continue
        }
        if($op -eq 0x0F -and $i+5 -lt $d.Length -and $d[$i+1] -ge 0x80 -and $d[$i+1] -le 0x8F) {
            $rel=[BitConverter]::ToInt32($d,$i+2)
            $dest=$i+6+$rel
            $rows += [pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=("Jcc-0F{0:X2}" -f $d[$i+1])
                Destination=("0x{0:X8}" -f $dest)
                Bytes=(($d[$i..($i+5)]|ForEach-Object{$_.ToString("X2")}) -join " ")
            }
            $i += 5
        }
    }
    return $rows
}

function Find-Rel32Incoming([int]$Target,[int]$Start,[int]$End) {
    $rows=@()
    for($i=$Start;$i -le $End-5;$i++) {
        if($d[$i] -ne 0xE8 -and $d[$i] -ne 0xE9){ continue }
        $rel=[BitConverter]::ToInt32($d,$i+1)
        $dest=$i+5+$rel
        if($dest -eq $Target) {
            $rows += [pscustomobject]@{
                Offset=("0x{0:X8}" -f $i)
                Kind=$(if($d[$i] -eq 0xE8){"CALL"}else{"JMP"})
                Target=("0x{0:X8}" -f $Target)
            }
        }
        $i += 4
    }
    return $rows
}

$expected05=[byte[]](0xC7,0x45,0xC4,0x00,0x00)
$expected06=[byte[]](0xC7,0x45,0xD4,0x00,0x00)
for($i=0;$i -lt $expected05.Length;$i++){
    if($d[$Site05+$i] -ne $expected05[$i]){ throw "Unexpected Phase 5 bytes at site 05." }
}
for($i=0;$i -lt $expected06.Length;$i++){
    if($d[$Site06+$i] -ne $expected06[$i]){ throw "Unexpected Phase 5 bytes at site 06." }
}

$outDir=Join-Path $GameRoot "_PROFILE_PHASE13_AGE_HANDLER_FOCUS"
if(Test-Path -LiteralPath $outDir){ Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$txt=New-Object System.Collections.Generic.List[string]
$txt.Add("PHASE 13 - AGE/GENDER HANDLER FOCUS")
$txt.Add("Source: $Ams")
$txt.Add("SHA256: $(Get-Hash $Ams)")
$txt.Add("Read-only: True")
$txt.Add("")
$txt.Add("Known anchors:")
$txt.Add(("  Function start:         0x{0:X8}" -f $FunctionStart))
$txt.Add(("  Phase12 site 05:        0x{0:X8}" -f $Site05))
$txt.Add(("  Phase12 site 05 target: 0x{0:X8}" -f $Site05Phase12Target))
$txt.Add(("  Phase12 site 06:        0x{0:X8}" -f $Site06))
$txt.Add(("  Phase12 site 06 target: 0x{0:X8}" -f $Site06Phase12Target))
$txt.Add("")
$txt.Add("=== EXACT HEX: 0x006A1C80..0x006A2520 ===")
for($o=$FunctionStart-0x20;$o -lt $FunctionEnd;$o+=16){ $txt.Add((Hex-Line $o 16)) }

$txt.Add("")
$txt.Add("=== CONTROL FLOW INSIDE FOCUSED HANDLER ===")
foreach($r in @(Decode-Flow ($FunctionStart-0x20) $FunctionEnd)){
    $txt.Add(("{0}  {1,-9} -> {2}  [{3}]" -f $r.Offset,$r.Kind,$r.Destination,$r.Bytes))
}

$txt.Add("")
$txt.Add("=== INCOMING REL32 TO HANDLER START ===")
foreach($r in @(Find-Rel32Incoming $FunctionStart 0 ([Math]::Min($d.Length,0x01000000)))){
    $txt.Add(("{0} {1} -> {2}" -f $r.Offset,$r.Kind,$r.Target))
}

$txt.Add("")
$txt.Add("=== BYTES AROUND PHASE12 SITE 05 ===")
for($o=$Site05-0x80;$o -lt $Site05+0x180;$o+=16){ $txt.Add((Hex-Line $o 16)) }

$txt.Add("")
$txt.Add("=== BYTES AROUND PHASE12 SITE 06 / TARGET 0x006A1DBA ===")
for($o=$Site06-0x180;$o -lt $Site06+0x180;$o+=16){ $txt.Add((Hex-Line $o 16)) }

$txt.Add("")
$txt.Add("=== BYTES AROUND PHASE12 SITE 05 CLEANUP TARGET 0x006A24D7 ===")
for($o=$Site05Phase12Target-0x100;$o -lt $Site05Phase12Target+0x80;$o+=16){ $txt.Add((Hex-Line $o 16)) }

$txtPath=Join-Path $outDir "PHASE13-AGE-HANDLER-FOCUS.txt"
$txt | Set-Content -LiteralPath $txtPath -Encoding UTF8

$summary=[ordered]@{
    Phase="13-age-handler-focus"
    ReadOnly=$true
    SourceAMS=$Ams
    SourceAMS_SHA256=(Get-Hash $Ams)
    VerifiedPhase5=$true
    HandlerStart=("0x{0:X8}" -f $FunctionStart)
    Phase12Site05=("0x{0:X8}" -f $Site05)
    Phase12Site05Target=("0x{0:X8}" -f $Site05Phase12Target)
    Phase12Site06=("0x{0:X8}" -f $Site06)
    Phase12Site06Target=("0x{0:X8}" -f $Site06Phase12Target)
    Finding="Phase 12 site 05 is inside the STR_AGE handler and currently exits to the handler cleanup; inspect this focused trace to replace the broad cleanup jump with an existing local-success continuation."
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $outDir "SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE13-AGE-HANDLER-FOCUS.zip"
if(Test-Path -LiteralPath $zip){ Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 13 AGE/GENDER HANDLER FOCUS COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Verified Phase 5: True"
Write-Host "Game modified: False"
Write-Host ("Output: {0}" -f $zip)
Write-Host ""
