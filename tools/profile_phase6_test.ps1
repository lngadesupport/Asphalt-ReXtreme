param(
    [switch]$Restore
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PackageName = "A278AB0D.AsphaltXtreme"
$ExpectedHash = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$Offset = [Convert]::ToInt32("006A4E50",16)
[byte[]]$Expected = 0x55,0x8B,0xEC,0x6A,0xFF,0x68,0x70,0x1E,0x41,0x01

$pkg = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
    Sort-Object Version -Descending |
    Select-Object -First 1

$root = $pkg.InstallLocation
$ams = Join-Path $root "AMS.exe"
$backupDir = Join-Path $root "_PROFILE_PHASE6_BACKUP"
$backup = Join-Path $backupDir "AMS.phase5.bak"
$report = Join-Path $root "PROFILE-PHASE6-TEST-REPORT.txt"

if (-not (Test-Path -LiteralPath $ams -PathType Leaf)) {
    throw "AMS.exe not found: $ams"
}

if ($Restore) {
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        throw "Backup not found: $backup"
    }
    $backupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash.ToLowerInvariant()
    if ($backupHash -ne $ExpectedHash) {
        throw "Backup hash mismatch: $backupHash"
    }
    Copy-Item -LiteralPath $backup -Destination $ams -Force
    Write-Host ""
    Write-Host "PROFILE PHASE 6 RESTORED" -ForegroundColor Green
    Write-Host "AMS.exe restored to Phase 5."
    exit 0
}

$currentHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ams).Hash.ToLowerInvariant()

if ($currentHash -eq $ExpectedHash) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        Copy-Item -LiteralPath $ams -Destination $backup -Force
    }

    [byte[]]$data = [IO.File]::ReadAllBytes($ams)
    for ($i=0; $i -lt $Expected.Length; $i++) {
        if ($data[$Offset+$i] -ne $Expected[$i]) {
            throw ("Unexpected byte at 0x{0:X8}: expected {1:X2}, got {2:X2}" -f ($Offset+$i),$Expected[$i],$data[$Offset+$i])
        }
    }

    # Experimental, reversible test: return immediately from the login-error handler.
    $data[$Offset] = 0xC3
    [IO.File]::WriteAllBytes($ams,$data)
} else {
    [byte[]]$data = [IO.File]::ReadAllBytes($ams)
    if ($data[$Offset] -ne 0xC3) {
        throw "AMS.exe is neither the verified Phase 5 binary nor the Phase 6 test patch."
    }
}

$newHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ams).Hash.ToLowerInvariant()

@(
    "Profile Phase 6 Test",
    "PackageFullName=$($pkg.PackageFullName)",
    "InstallLocation=$root",
    "PatchOffset=0x006A4E50",
    "OriginalFirstBytes=55 8B EC 6A FF 68 70 1E 41 01",
    "PatchedFirstByte=C3",
    "OriginalSHA256=$ExpectedHash",
    "PatchedSHA256=$newHash",
    "Backup=$backup",
    "Purpose=Suppress only the mapped legacy login-error handler to test whether startup can fall through to local state."
) | Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 6 TEST APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Mapped handler: 0x006A4E50"
Write-Host "Backup created:  $backup"
Write-Host "Report:          $report"
Write-Host ""
Write-Host "Now launch the already-registered game normally."
Write-Host ""
