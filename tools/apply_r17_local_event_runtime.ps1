param(
    [ValidateSet("Apply","Revert")][string]$Mode = "Apply",
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path

$package = Join-Path $SourceDir "_PACKAGE_PHASE5"
$runtime = Join-Path $SourceDir "RUNTIME_STUBS\IGPLib_x86.dll"
$target = Join-Path $package "IGPLib_x86.dll"
$backupDir = Join-Path $SourceDir "_BACKUPS\R17"
$backup = Join-Path $backupDir "IGPLib_x86.dll"
$traceDir = Join-Path $SourceDir "_TRACE_MONTAR"
$statePath = Join-Path $backupDir "state.json"

if (-not (Test-Path -LiteralPath $package -PathType Container)) {
    throw "Missing package: $package"
}

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
New-Item -ItemType Directory -Path $traceDir -Force | Out-Null

if ($Mode -eq "Apply") {
    if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) {
        throw "Missing R17 runtime DLL. Run BUILD-R17-LOCAL-EVENT-RUNTIME.cmd first."
    }

    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "Package does not contain IGPLib_x86.dll: $target"
    }

    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        Copy-Item -LiteralPath $target -Destination $backup -Force
    }

    $before = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()

    Copy-Item -LiteralPath $runtime -Destination $target -Force

    $after = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()

    $state = [ordered]@{
        Patch = "R17 Local Event Runtime"
        Applied = $true
        Target = $target
        Backup = $backup
        BeforeSHA256 = $before
        AfterSHA256 = $after
        RuntimeOnlyHook = $true
        AMSBytesChanged = $false
        R15R16MayRemainApplied = $true
        Timestamp = (Get-Date).ToString("o")
    }

    $state | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $statePath -Encoding UTF8

    $state | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath (Join-Path $traceDir "R17-LOCAL-EVENT-RUNTIME.json") -Encoding UTF8

    Write-Host "R17 applied to _PACKAGE_PHASE5." -ForegroundColor Green
    Write-Host "AMS.exe was not modified."
    Write-Host "R15/R16 can remain present; R17 replaces BuildCar in memory."
}
else {
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        throw "R17 backup not found: $backup"
    }

    Copy-Item -LiteralPath $backup -Destination $target -Force

    $state = [ordered]@{
        Patch = "R17 Local Event Runtime"
        Applied = $false
        Restored = $target
        RestoredSHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        Timestamp = (Get-Date).ToString("o")
    }

    $state | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $statePath -Encoding UTF8

    Write-Host "R17 reverted." -ForegroundColor Yellow
}
