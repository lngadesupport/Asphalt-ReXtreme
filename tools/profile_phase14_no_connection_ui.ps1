param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    [switch]$Restore
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams=Join-Path $GameRoot "AMS.exe"
$BackupRoot=Join-Path $GameRoot "_PROFILE_PHASE14_BACKUP"
$Backup=Join-Path $BackupRoot "AMS.phase5.bak"
$ReportPath=Join-Path $GameRoot "PROFILE-PHASE14-NO-CONNECTION-UI-REPORT.json"

$ExpectedPhase5="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

function Get-Hash([string]$p){
    (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}

if(-not (Test-Path -LiteralPath $Ams -PathType Leaf)){
    throw "AMS.exe not found: $Ams"
}

if($Restore){
    if(-not (Test-Path -LiteralPath $Backup -PathType Leaf)){
        throw "Phase 14 backup not found: $Backup"
    }
    if((Get-Hash $Backup) -ne $ExpectedPhase5){
        throw "Phase 14 backup is not verified Phase 5."
    }
    Copy-Item -LiteralPath $Backup -Destination $Ams -Force
    Write-Host ""
    Write-Host "PHASE 14 RESTORED TO VERIFIED PHASE 5" -ForegroundColor Green
    exit 0
}

# Always rebuild from the verified Phase 5 executable.
$current=Get-Hash $Ams
if($current -ne $ExpectedPhase5){
    $candidates=@(
        (Join-Path $GameRoot "_PROFILE_PHASE14_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "_PROFILE_PHASE13_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP\AMS.phase5.bak"),
        (Join-Path $GameRoot "AMS.PHASE5.RETRY-ID.bak"),
        (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
        (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak")
    )
    $restored=$false
    foreach($candidate in $candidates){
        if(-not (Test-Path -LiteralPath $candidate -PathType Leaf)){continue}
        if((Get-Hash $candidate) -eq $ExpectedPhase5){
            Copy-Item -LiteralPath $candidate -Destination $Ams -Force
            $restored=$true
            break
        }
    }
    if(-not $restored){
        throw "Verified Phase 5 AMS required and no verified backup was found. Current hash: $current"
    }
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Copy-Item -LiteralPath $Ams -Destination $Backup -Force

[byte[]]$d=[IO.File]::ReadAllBytes($Ams)

$patches=@(
    # ------------------------------------------------------------------
    # Phase 9: accept the native default profile object locally.
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="Campaign profile: first local validation uses valid path"
        Offset=[Convert]::ToInt32("0069B8C6",16)
        Before=[byte[]](0x74,0x24)
        After=[byte[]](0x74,0x22)
    },
    [pscustomobject]@{
        Name="Campaign profile: secondary local validation returns true"
        Offset=[Convert]::ToInt32("0069B8E6",16)
        Before=[byte[]](0x32,0xC0)
        After=[byte[]](0xB0,0x01)
    },

    # ------------------------------------------------------------------
    # Phase 10: neutralize the three known remote profile-loading sites.
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="Profile sync loading site 1"
        Offset=[Convert]::ToInt32("00685F9C",16)
        Before=[byte[]](0x0F,0x84,0xDF,0x00,0x00,0x00)
        After=[byte[]](0xE9,0xE0,0x00,0x00,0x00,0x90)
    },
    [pscustomobject]@{
        Name="Profile sync loading site 2"
        Offset=[Convert]::ToInt32("006CF957",16)
        Before=[byte[]](0x8D,0x45,0xE0,0x0F,0x57,0xC0,0x50,0x66,0x0F)
        After=[byte[]](0xC6,0x47,0x4C,0x00,0xE9,0x43,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="Startup profile state machine"
        Offset=[Convert]::ToInt32("0092B82A",16)
        Before=[byte[]](0x0F,0x84,0x8D,0x01,0x00,0x00)
        After=[byte[]](0xE9,0x8E,0x01,0x00,0x00,0x90)
    },

    # ------------------------------------------------------------------
    # Phase 14: repair the age/gender handler itself.
    #
    # In pristine Phase 5, both branches below are taken only when the
    # global connectivity getter returns true:
    #
    #   0x006A1CE1 JNZ 0x006A1DE5
    #   0x006A1E03 JNZ 0x006A1EE1
    #
    # Phase 12 instead patched the bodies at 0x006A1CE7 / 0x006A1E09,
    # causing the first-run handler to exit/cleanup before it finishes
    # wiring the local age/gender flow.
    #
    # Keep global IsOnline FALSE. Only this handler follows its already-
    # existing success continuations, so obsolete remote systems remain
    # disabled while ACEITAR can execute the native local flow.
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="Age/gender handler gate 1: local success continuation"
        Offset=[Convert]::ToInt32("006A1CE1",16)
        Before=[byte[]](0x0F,0x85,0xFE,0x00,0x00,0x00)
        After=[byte[]](0xE9,0xFF,0x00,0x00,0x00,0x90)
    },
    [pscustomobject]@{
        Name="Age/gender handler gate 2: local success continuation"
        Offset=[Convert]::ToInt32("006A1E03",16)
        Before=[byte[]](0x0F,0x85,0xD8,0x00,0x00,0x00)
        After=[byte[]](0xE9,0xD9,0x00,0x00,0x00,0x90)
    },

    # ------------------------------------------------------------------
    # Phase 12 NO_INTERNET coverage retained everywhere else.
    #
    # IMPORTANT: the former Phase 12 site 05 (0x006A1CE7) and site 06
    # (0x006A1E09) body patches are intentionally NOT present here.
    # They are superseded by the two targeted handler-gate patches above.
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="NO_INTERNET callback 1 -> true epilogue"
        Offset=[Convert]::ToInt32("004FBCF0",16)
        Before=[byte[]](0x8B,0x8E,0xAC,0x01,0x00)
        After=[byte[]](0xE9,0x09,0xFF,0xFF,0xFF)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 2 -> true epilogue"
        Offset=[Convert]::ToInt32("004FD6A5",16)
        Before=[byte[]](0x8B,0x8E,0xB0,0x01,0x00)
        After=[byte[]](0xE9,0xE0,0xFF,0xFF,0xFF)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 3 -> true epilogue"
        Offset=[Convert]::ToInt32("0064A789",16)
        Before=[byte[]](0x8B,0x8E,0xB8,0x01,0x00)
        After=[byte[]](0xE9,0x09,0xFF,0xFF,0xFF)
    },
    # ------------------------------------------------------------------
    # Phase 14: uncovered STR_POPUP_NO_INTERNET_TITLE paths.
    #
    # The Phase 14 map found ten title-only xrefs in addition to the
    # fifteen paired/known blocks.  Three are sibling branches inside the
    # callback functions; the others are standalone popup construction
    # paths used by later UI states such as the lobby/post-tutorial flow.
    #
    # Every jump below lands on an existing native epilogue, common
    # continuation, or post-popup cleanup sequence.  No online service is
    # enabled and no localization resource is modified.
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="NO_INTERNET callback 1 sibling popup -> epilogue"
        Offset=[Convert]::ToInt32("004FBEC1",16)
        Before=[byte[]](0x8B,0x8E,0xAC,0x01,0x00)
        After=[byte[]](0xE9,0x9A,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 2 sibling popup -> epilogue"
        Offset=[Convert]::ToInt32("004FD876",16)
        Before=[byte[]](0x8B,0x8E,0xB0,0x01,0x00)
        After=[byte[]](0xE9,0xA7,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 3 sibling popup -> epilogue"
        Offset=[Convert]::ToInt32("0064A95A",16)
        Before=[byte[]](0x8B,0x8E,0xB8,0x01,0x00)
        After=[byte[]](0xE9,0x9A,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 04 -> native common continuation"
        Offset=[Convert]::ToInt32("00530935",16)
        Before=[byte[]](0x8B,0x0D,0x64,0x85,0x94)
        After=[byte[]](0xE9,0xAD,0x02,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 05 -> native common continuation"
        Offset=[Convert]::ToInt32("006D62C5",16)
        Before=[byte[]](0x51,0x8B,0xCC,0x68,0x88)
        After=[byte[]](0xE9,0x3A,0x06,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 06 -> post-popup cleanup"
        Offset=[Convert]::ToInt32("00746EDB",16)
        Before=[byte[]](0x68,0xF0,0x60,0x53,0x01)
        After=[byte[]](0xE9,0x86,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 07 -> post-popup cleanup"
        Offset=[Convert]::ToInt32("008DA2B4",16)
        Before=[byte[]](0x68,0xF0,0x60,0x53,0x01)
        After=[byte[]](0xE9,0x83,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 08 lobby -> common continuation"
        Offset=[Convert]::ToInt32("009171DC",16)
        Before=[byte[]](0x51,0x8B,0xCC,0xC6,0x45)
        After=[byte[]](0xE9,0x28,0x02,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 09 -> native common continuation"
        Offset=[Convert]::ToInt32("0099D3F7",16)
        Before=[byte[]](0x51,0x8B,0xCC,0x89,0x8D)
        After=[byte[]](0xE9,0x7A,0x04,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET title-only path 10 -> common continuation"
        Offset=[Convert]::ToInt32("00A68023",16)
        Before=[byte[]](0x51,0x8B,0xCC,0xC6,0x45)
        After=[byte[]](0xE9,0x3B,0x02,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 04 -> cleanup"
        Offset=[Convert]::ToInt32("00689741",16)
        Before=[byte[]](0x84,0xDB,0x0F,0x85,0xF5)
        After=[byte[]](0xE9,0xF8,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 07 -> cleanup"
        Offset=[Convert]::ToInt32("006A46DC",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0xD9,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 08 -> cleanup"
        Offset=[Convert]::ToInt32("006A5EFC",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0xD9,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 09 -> cleanup"
        Offset=[Convert]::ToInt32("006A6BCC",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0xD9,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 10 -> cleanup"
        Offset=[Convert]::ToInt32("00809EB2",16)
        Before=[byte[]](0x51,0x8B,0xC4,0x68,0xA8)
        After=[byte[]](0xE9,0xEC,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 11 -> cleanup"
        Offset=[Convert]::ToInt32("008B5441",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0x98,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 12 -> cleanup"
        Offset=[Convert]::ToInt32("00B0CB4C",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0xD9,0x00,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 13 -> cleanup"
        Offset=[Convert]::ToInt32("00B24D61",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0x98,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 14 -> cleanup"
        Offset=[Convert]::ToInt32("00B44EA1",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0x98,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 15 -> cleanup"
        Offset=[Convert]::ToInt32("00B6A0A0",16)
        Before=[byte[]](0xC7,0x45,0xF0,0x00,0x00)
        After=[byte[]](0xE9,0x98,0x01,0x00,0x00)
    }
)

$patchReport=@()
foreach($p in $patches){
    if($p.Before.Length -ne $p.After.Length){
        throw ("Patch length mismatch: {0}" -f $p.Name)
    }

    for($i=0;$i -lt $p.Before.Length;$i++){
        if($d[$p.Offset+$i] -ne $p.Before[$i]){
            throw ("Unexpected byte for {0} at 0x{1:X8}: expected {2:X2}, got {3:X2}" -f
                $p.Name,($p.Offset+$i),$p.Before[$i],$d[$p.Offset+$i])
        }
    }

    [Array]::Copy($p.After,0,$d,$p.Offset,$p.After.Length)

    $patchReport += [ordered]@{
        Name=$p.Name
        Offset=("0x{0:X8}" -f $p.Offset)
        Before=(($p.Before|ForEach-Object{$_.ToString("X2")}) -join " ")
        After=(($p.After|ForEach-Object{$_.ToString("X2")}) -join " ")
    }
}

[IO.File]::WriteAllBytes($Ams,$d)

$status=[ordered]@{
    Phase="14-no-connection-ui"
    OriginalAMS_SHA256=$ExpectedPhase5
    PatchedAMS_SHA256=(Get-Hash $Ams)
    LogicalConnectivity="offline/false"
    AgeGenderHandlerLocalSuccessGates=2
    FormerPhase12AgeHandlerBodySkipsRemoved=2
    KnownNoInternetBlocksCovered=23
    AdditionalTitleOnlyPopupPathsCovered=10
    CorrectedCallbackEpilogues=3
    KnownProfileLoadingSitesNeutralized=3
    PatchCount=$patches.Count
    Patches=$patchReport
    Notes=@(
        "Global connectivity getter remains the Phase 5 offline/false implementation.",
        "Phase 13 age/gender local-success gates are retained.",
        "The three legacy callback jumps now land on true function epilogues instead of sibling popup code.",
        "All ten additional STR_POPUP_NO_INTERNET_TITLE paths found by the Phase 14 map are bypassed.",
        "Direct string-xref operands at 0x00746EDC and 0x008DA2B5 are patched from their actual PUSH opcodes one byte earlier (0x00746EDB / 0x008DA2B4)."
        "No remote profile, Store, advertising or backend service is re-enabled.",
        "Runtime acceptance test: tutorial must still complete and lobby must open without SEM CONEXAO / NOVAMENTE."
    )
}

$status|ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 14 - NO CONNECTION UI APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Logical connectivity remains offline: True"
Write-Host "Age/gender local-success gates retained: 2 / 2"
Write-Host "Uncovered NO_INTERNET title-only paths bypassed: 10 / 10"
Write-Host "Legacy callback popup paths corrected: 3 / 3"
Write-Host ("Total binary patches: {0}" -f $patches.Count)
Write-Host ("Patched AMS SHA-256: {0}" -f $status.PatchedAMS_SHA256)
Write-Host ""
Write-Host "Runtime check:"
Write-Host "  launch -> tutorial/lobby -> normal local navigation"
Write-Host "Expected:"
Write-Host "  no SEM CONEXAO / FALHA DE CONEXAO modal; lobby remains usable."
Write-Host ""
