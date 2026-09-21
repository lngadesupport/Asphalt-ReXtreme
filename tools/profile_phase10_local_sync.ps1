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
$BackupRoot=Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP"
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
        throw "Phase 10 backup not found: $Backup"
    }
    if((Get-Hash $Backup) -ne $ExpectedPhase5){
        throw "Phase 10 backup is not verified Phase 5."
    }
    Copy-Item -LiteralPath $Backup -Destination $Ams -Force
    Write-Host ""
    Write-Host "PHASE 10 RESTORED TO VERIFIED PHASE 5" -ForegroundColor Green
    exit 0
}

# Always rebuild Phase 10 from verified Phase 5.
$current=Get-Hash $Ams
if($current -ne $ExpectedPhase5){
    $candidates=@(
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
    # Phase 9: accept the game's native default profile object.
    [pscustomobject]@{
        Name="Phase9 local validation path"
        Offset=[Convert]::ToInt32("0069B8C6",16)
        Before=[byte[]](0x74,0x24)
        After=[byte[]](0x74,0x22)
    },
    [pscustomobject]@{
        Name="Phase9 secondary local validation"
        Offset=[Convert]::ToInt32("0069B8E6",16)
        Before=[byte[]](0x32,0xC0)
        After=[byte[]](0xB0,0x01)
    },

    # STR_MENU_SYNC_LOADING site 1.
    # Follow the existing "no remote sync object" path immediately.
    [pscustomobject]@{
        Name="Global local sync: loading site 1"
        Offset=[Convert]::ToInt32("00685F9C",16)
        Before=[byte[]](0x0F,0x84,0xDF,0x00,0x00,0x00)
        After=[byte[]](0xE9,0xE0,0x00,0x00,0x00,0x90)
    },

    # STR_MENU_SYNC_LOADING site 2.
    # The local mutation has already been prepared. Consume the pending
    # sync flag (+0x4C) and jump to cleanup without opening the remote
    # loading UI or calling the obsolete backend.
    [pscustomobject]@{
        Name="Global local sync: consume pending runtime sync"
        Offset=[Convert]::ToInt32("006CF957",16)
        Before=[byte[]](0x8D,0x45,0xE0,0x0F,0x57,0xC0,0x50,0x66,0x0F)
        After=[byte[]](0xC6,0x47,0x4C,0x00,0xE9,0x43,0x01,0x00,0x00)
    },

    # STR_MENU_SYNC_LOADING site 3 / startup state machine.
    [pscustomobject]@{
        Name="Phase9 startup remote-profile gate"
        Offset=[Convert]::ToInt32("0092B82A",16)
        Before=[byte[]](0x0F,0x84,0x8D,0x01,0x00,0x00)
        After=[byte[]](0xE9,0x8E,0x01,0x00,0x00,0x90)
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
    Phase="10-global-local-profile-sync"
    OriginalAMS_SHA256=$ExpectedPhase5
    PatchedAMS_SHA256=(Get-Hash $Ams)
    KnownLoadingSitesNeutralized=3
    Patches=$report
    Notes=@(
        "All three known STR_MENU_SYNC_LOADING construction sites are neutralized.",
        "Startup still uses the Phase 9 native default-profile path.",
        "Runtime profile sync requests consume the pending local sync flag and skip the obsolete remote backend.",
        "This is a reversible test build. Verify age/gender acceptance, race-end flow, upgrades, boxes and purchases."
    )
}

$status|ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $GameRoot "PROFILE-PHASE10-LOCAL-SYNC-REPORT.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 10 GLOBAL LOCAL SYNC APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Known online-profile loading sites neutralized: 3 / 3"
Write-Host ("Patched AMS SHA-256: {0}" -f $status.PatchedAMS_SHA256)
Write-Host ""
Write-Host "Test these flows:"
Write-Host "  1. Accept age/gender"
Write-Host "  2. Finish a race"
Write-Host "  3. Upgrade a vehicle"
Write-Host "  4. Open/buy a box"
Write-Host "  5. Buy another local item"
Write-Host ""
