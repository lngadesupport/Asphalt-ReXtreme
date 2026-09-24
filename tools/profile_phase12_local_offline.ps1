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
$BackupRoot=Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP"
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
        throw "Phase 12 backup not found: $Backup"
    }
    if((Get-Hash $Backup) -ne $ExpectedPhase5){
        throw "Phase 12 backup is not verified Phase 5."
    }
    Copy-Item -LiteralPath $Backup -Destination $Ams -Force
    Write-Host ""
    Write-Host "PHASE 12 RESTORED TO VERIFIED PHASE 5" -ForegroundColor Green
    exit 0
}

# Always rebuild from a verified Phase 5 AMS.
$current=Get-Hash $Ams
if($current -ne $ExpectedPhase5){
    $candidates=@(
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
    # Phase 9: native default profile object is accepted locally.
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
    # Phase 10: all known profile-sync loading sites are neutralized.
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
    # Phase 12: keep the Phase 5 connectivity shim FALSE.
    #
    # Do NOT change 0x00BACDD0 to true. The remote backend is dead.
    # Instead every known complete NO_INTERNET popup block jumps to its
    # own existing cleanup/return path before a popup is constructed.
    #
    # 3 result-callback paths:
    # ------------------------------------------------------------------
    [pscustomobject]@{
        Name="NO_INTERNET callback 1 -> cleanup"
        Offset=[Convert]::ToInt32("004FBCF0",16)
        Before=[byte[]](0x8B,0x8E,0xAC,0x01,0x00)
        After=[byte[]](0xE9,0x3C,0x02,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 2 -> cleanup"
        Offset=[Convert]::ToInt32("004FD6A5",16)
        Before=[byte[]](0x8B,0x8E,0xB0,0x01,0x00)
        After=[byte[]](0xE9,0x49,0x02,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET callback 3 -> cleanup"
        Offset=[Convert]::ToInt32("0064A789",16)
        Before=[byte[]](0x8B,0x8E,0xB8,0x01,0x00)
        After=[byte[]](0xE9,0x3C,0x02,0x00,0x00)
    },

    # 12 connectivity-gated NO_INTERNET popup blocks:
    [pscustomobject]@{
        Name="NO_INTERNET site 04 -> cleanup"
        Offset=[Convert]::ToInt32("00689741",16)
        Before=[byte[]](0x84,0xDB,0x0F,0x85,0xF5)
        After=[byte[]](0xE9,0xF8,0x01,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 05 -> cleanup"
        Offset=[Convert]::ToInt32("006A1CE7",16)
        Before=[byte[]](0xC7,0x45,0xC4,0x00,0x00)
        After=[byte[]](0xE9,0xEB,0x07,0x00,0x00)
    },
    [pscustomobject]@{
        Name="NO_INTERNET site 06 -> cleanup"
        Offset=[Convert]::ToInt32("006A1E09",16)
        Before=[byte[]](0xC7,0x45,0xD4,0x00,0x00)
        After=[byte[]](0xE9,0xAC,0xFF,0xFF,0xFF)
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
    Phase="12-local-offline-no-network-ui"
    OriginalAMS_SHA256=$ExpectedPhase5
    PatchedAMS_SHA256=(Get-Hash $Ams)
    LogicalConnectivity="offline/false"
    KnownNoInternetPopupBlocksBypassed=15
    KnownProfileLoadingSitesNeutralized=3
    Patches=$report
    Notes=@(
        "Unlike Phase 11, Phase 12 does not report logical connectivity true.",
        "No known NO_INTERNET block is allowed to construct its modal popup.",
        "Each known NO_INTERNET block jumps to its own existing cleanup/return path.",
        "No remote service is enabled by this layer.",
        "Store purchase, ads and remote profile sync remain separately neutralized."
    )
}

$status|ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $GameRoot "PROFILE-PHASE12-LOCAL-OFFLINE-REPORT.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 12 - LOCAL OFFLINE / NO NETWORK UI APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Logical connectivity remains offline: True"
Write-Host "Known NO_INTERNET popup blocks bypassed: 15 / 15"
Write-Host "Known profile loading sites neutralized: 3 / 3"
Write-Host ("Patched AMS SHA-256: {0}" -f $status.PatchedAMS_SHA256)
Write-Host ""
Write-Host "Test age/gender -> ACEITAR first."
Write-Host ""
