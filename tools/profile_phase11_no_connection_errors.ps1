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
$BackupRoot=Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP"
$Backup=Join-Path $BackupRoot "AMS.phase5.bak"

$ExpectedPhase5="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

function Get-Hash([string]$p){
    (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}

if(-not (Test-Path -LiteralPath $Ams -PathType Leaf)){
    throw "AMS.exe not found: $Ams"
}

if($Restore){
    if(-not (Test-Path -LiteralPath $Backup -PathType Leaf)){
        throw "Phase 11 backup not found: $Backup"
    }
    if((Get-Hash $Backup) -ne $ExpectedPhase5){
        throw "Phase 11 backup is not verified Phase 5."
    }

    Copy-Item -LiteralPath $Backup -Destination $Ams -Force

    Write-Host ""
    Write-Host "PHASE 11 RESTORED TO VERIFIED PHASE 5" -ForegroundColor Green
    exit 0
}

# Always rebuild from verified Phase 5.
$current=Get-Hash $Ams
if($current -ne $ExpectedPhase5){
    $candidates=@(
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
    # -----------------------------------------------------------------
    # Campaign profile / Phase 9
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # Global profile sync / Phase 10
    # -----------------------------------------------------------------
    [pscustomobject]@{
        Name="Profile sync loading site 1: skip remote loading block"
        Offset=[Convert]::ToInt32("00685F9C",16)
        Before=[byte[]](0x0F,0x84,0xDF,0x00,0x00,0x00)
        After=[byte[]](0xE9,0xE0,0x00,0x00,0x00,0x90)
    },
    [pscustomobject]@{
        Name="Profile sync loading site 2: consume pending sync locally"
        Offset=[Convert]::ToInt32("006CF957",16)
        Before=[byte[]](0x8D,0x45,0xE0,0x0F,0x57,0xC0,0x50,0x66,0x0F)
        After=[byte[]](0xC6,0x47,0x4C,0x00,0xE9,0x43,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="Startup profile state machine: bypass remote profile gate"
        Offset=[Convert]::ToInt32("0092B82A",16)
        Before=[byte[]](0x0F,0x84,0x8D,0x01,0x00,0x00)
        After=[byte[]](0xE9,0x8E,0x01,0x00,0x00,0x90)
    },

    # -----------------------------------------------------------------
    # Phase 11 — global connectivity compatibility shim
    #
    # Original game implementation at VA 0xFAD9D0:
    #   mov al,[ecx+4B0h]
    #   ret
    #
    # Phase 5 forced this to FALSE:
    #   xor eax,eax
    #   ret
    #
    # That directly activates 12 known STR_POPUP_NO_INTERNET sites.
    # Campaign Edition instead reports logical connectivity TRUE while
    # remote systems are neutralized separately (sync, Store, ads).
    # -----------------------------------------------------------------
    [pscustomobject]@{
        Name="Global connectivity shim: report available"
        Offset=[Convert]::ToInt32("00BACDD0",16)
        Before=[byte[]](0x31,0xC0,0xC3,0x90,0x90,0x90,0x90)
        After=[byte[]](0xB0,0x01,0xC3,0x90,0x90,0x90,0x90)
    },

    # -----------------------------------------------------------------
    # Three remaining complete NO_INTERNET popup paths are not directly
    # gated by IsOnline(). They are remote result callbacks.
    # Route their explicit "network unavailable" result branches into
    # each callback's already-existing success/local-completion path.
    # -----------------------------------------------------------------
    [pscustomobject]@{
        Name="NO_INTERNET callback A: network error -> local success"
        Offset=[Convert]::ToInt32("004FBCF0",16)
        Before=[byte[]](0x8B,0x8E,0xAC,0x01,0x00)
        After=[byte[]](0xE9,0x26,0xFD,0xFF,0xFF)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback B: network error -> local success"
        Offset=[Convert]::ToInt32("004FD6A5",16)
        Before=[byte[]](0x8B,0x8E,0xB0,0x01,0x00)
        After=[byte[]](0xE9,0xFD,0xFD,0xFF,0xFF)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback C: network error -> local success"
        Offset=[Convert]::ToInt32("0064A789",16)
        Before=[byte[]](0x8B,0x8E,0xB8,0x01,0x00)
        After=[byte[]](0xE9,0x26,0xFD,0xFF,0xFF)
    }
)

$report=@()

foreach($p in $patches){
    for($i=0;$i -lt $p.Before.Length;$i++){
        if($d[$p.Offset+$i] -ne $p.Before[$i]){
            throw ("Unexpected byte for {0} at 0x{1:X8}: expected {2:X2}, got {3:X2}" -f
                $p.Name,($p.Offset+$i),$p.Before[$i],$d[$p.Offset+$i])
        }
    }

    [Array]::Copy($p.After,0,$d,$p.Offset,$p.After.Length)

    $report += [ordered]@{
        Name=$p.Name
        Offset=("0x{0:X8}" -f $p.Offset)
        Before=(($p.Before|ForEach-Object{$_.ToString("X2")}) -join " ")
        After=(($p.After|ForEach-Object{$_.ToString("X2")}) -join " ")
    }
}

[IO.File]::WriteAllBytes($Ams,$d)

$status=[ordered]@{
    Phase="11-no-connection-errors"
    OriginalAMS_SHA256=$ExpectedPhase5
    PatchedAMS_SHA256=(Get-Hash $Ams)
    KnownNoInternetPopupConstructionSites=15
    SitesNeutralizedByConnectivityShim=12
    SitesNeutralizedByLocalSuccessCallbacks=3
    KnownSyncLoadingSitesNeutralized=3
    Patches=$report
    Notes=@(
        "All 15 known complete STR_POPUP_NO_INTERNET_DESCRIPTION/TITLE construction sites are covered.",
        "The logical connectivity getter reports available so local Campaign flows do not enter offline-error UI.",
        "Three remote-result callbacks that can independently create NO_INTERNET popups are routed into their existing success/local-completion paths.",
        "Profile sync, Store purchase and ads remain neutralized separately; reporting logical connectivity does not restore those obsolete services.",
        "Other non-connectivity gameplay errors are not suppressed."
    )
}

$status|ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $GameRoot "PROFILE-PHASE11-NO-CONNECTION-ERRORS-REPORT.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 11 - NO CONNECTION ERRORS APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Known NO_INTERNET popup sites covered: 15 / 15"
Write-Host "  connectivity-gated: 12"
Write-Host "  remote-result callbacks: 3"
Write-Host "Known profile loading sites neutralized: 3 / 3"
Write-Host ("Patched AMS SHA-256: {0}" -f $status.PatchedAMS_SHA256)
Write-Host ""
Write-Host "Test first:"
Write-Host "  - age/gender -> ACEITAR"
Write-Host "Then test:"
Write-Host "  - race finish"
Write-Host "  - vehicle upgrade"
Write-Host "  - box open/purchase"
Write-Host "  - shop purchase"
Write-Host ""
