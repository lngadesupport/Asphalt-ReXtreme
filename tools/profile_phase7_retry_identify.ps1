param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    [switch]$Restore
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$ams = Join-Path $GameRoot "AMS.exe"
$backup = Join-Path $GameRoot "AMS.PHASE5.RETRY-ID.bak"

$expectedHash = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

if (-not (Test-Path -LiteralPath $ams -PathType Leaf)) {
    throw "AMS.exe not found: $ams"
}

if ($Restore) {
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        throw "Retry-ID backup not found: $backup"
    }
    $bh = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($bh -ne $expectedHash) {
        throw "Retry-ID backup is not the verified Phase 5 AMS. Hash: $bh"
    }
    Copy-Item -LiteralPath $backup -Destination $ams -Force
    Write-Host ""
    Write-Host "PHASE 7 RETRY IDENTIFIER RESTORED" -ForegroundColor Green
    Write-Host "AMS.exe is back to verified Phase 5."
    exit 0
}

$hash = (Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $expectedHash) {
    throw "Verified Phase 5 AMS required before this test. Current hash: $hash"
}

Copy-Item -LiteralPath $ams -Destination $backup -Force

[byte[]]$d = [IO.File]::ReadAllBytes($ams)

# The callback mapper found Action 4 at pattern starts:
#   0x0074084D (slot 0x10)
#   0x007409CE (slot 0x14)
# The actual action dispatch sequences start six bytes later:
#   6A 04 8B 01 FF 50 10
#   6A 04 8B 01 FF 50 14
$patches = @(
    [pscustomobject]@{
        Offset = [Convert]::ToInt32("00740853",16)
        Before = [byte[]](0x6A,0x04,0x8B,0x01,0xFF,0x50,0x10)
        Name = "Action4_Slot10"
    },
    [pscustomobject]@{
        Offset = [Convert]::ToInt32("007409D4",16)
        Before = [byte[]](0x6A,0x04,0x8B,0x01,0xFF,0x50,0x14)
        Name = "Action4_Slot14"
    }
)

foreach($p in $patches) {
    for($i=0; $i -lt $p.Before.Length; $i++) {
        if($d[$p.Offset+$i] -ne $p.Before[$i]) {
            throw ("Unexpected byte for {0} at 0x{1:X8}. Expected {2:X2}, got {3:X2}" -f
                $p.Name,($p.Offset+$i),$p.Before[$i],$d[$p.Offset+$i])
        }
    }
}

foreach($p in $patches) {
    for($i=0; $i -lt 7; $i++) {
        $d[$p.Offset+$i] = 0x90
    }
}

[IO.File]::WriteAllBytes($ams,$d)
$newHash = (Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$report = @(
    "Profile Phase 7 Retry Identifier",
    "Purpose=Temporarily disable Action 4 in both popup callback variants.",
    "Interpretation:",
    "  If Try Again becomes inert -> Action 4 is Retry.",
    "  If Try Again still retries online -> Action 14 is Retry.",
    "Patch1=0x00740853  6A 04 8B 01 FF 50 10 -> 90 90 90 90 90 90 90",
    "Patch2=0x007409D4  6A 04 8B 01 FF 50 14 -> 90 90 90 90 90 90 90",
    "OriginalSHA256=$expectedHash",
    "PatchedSHA256=$newHash",
    "Backup=$backup"
)
$report | Set-Content -LiteralPath (Join-Path $GameRoot "PROFILE-PHASE7-RETRY-ID.txt") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 7 - RETRY IDENTIFIER APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Action 4 is disabled in both popup variants."
Write-Host ""
Write-Host "Now launch the game and click TENTAR NOVAMENTE once."
Write-Host ""
Write-Host "Result A: button does nothing -> Action 4 = Retry"
Write-Host "Result B: online verification starts again -> Action 14 = Retry"
Write-Host ""
Write-Host "Do not keep playing with this test patch."
Write-Host ""
