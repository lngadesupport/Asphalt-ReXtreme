param(
    [Parameter(Mandatory=$true)]
    [string]$SourceDir,

    [string]$WorkRoot = "",

    [switch]$RunAudit
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Write-Step {
    param([string]$Message)
    Write-Host ("[Campaign] " + $Message) -ForegroundColor Cyan
}

$source = (Resolve-Path -LiteralPath $SourceDir).Path
if ([string]::IsNullOrWhiteSpace($WorkRoot)) {
    $WorkRoot = Join-Path $env:TEMP "ReXtreme-Campaign"
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$WorkRoot = (Resolve-Path -LiteralPath $WorkRoot).Path

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $WorkRoot ("source-" + $stamp)
$volDir = Join-Path $runDir "volumes"
$extractDir = Join-Path $runDir "extracted"
New-Item -ItemType Directory -Force -Path $volDir,$extractDir | Out-Null

Write-Step "Locating multipart RAR volumes"

$selected = @()
for ($i = 1; $i -le 7; $i++) {
    $canonical = "Asphalt Xtreme.part$i.rar"
    $pattern = ("^Asphalt Xtreme\.part{0}(?:\(\d+\))?\.rar$" -f $i)
    $candidates = @(Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Name -match $pattern })

    if ($candidates.Count -eq 0) {
        throw "Missing required volume: $canonical"
    }

    $exact = $candidates | Where-Object { $_.Name -ieq $canonical } | Select-Object -First 1
    if ($exact) {
        $pick = $exact
    } else {
        $pick = $candidates | Sort-Object Length,LastWriteTimeUtc -Descending | Select-Object -First 1
    }

    if ($candidates.Count -gt 1) {
        Write-Step ("Volume {0}: found {1} candidates; using {2}" -f $i,$candidates.Count,$pick.Name)
    } else {
        Write-Step ("Volume {0}: {1}" -f $i,$pick.Name)
    }

    $dst = Join-Path $volDir $canonical
    Copy-Item -LiteralPath $pick.FullName -Destination $dst -Force
    $selected += [pscustomobject]@{
        Part = $i
        SourceName = $pick.Name
        CanonicalName = $canonical
        Size = $pick.Length
        SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $pick.FullName).Hash.ToLowerInvariant()
    }
}

$selected | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $runDir "volumes.csv")

Write-Step "Selecting RAR extractor"
$extractor = $null
$kind = $null
$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")

$sevenCandidates = @(
    (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
    $(if ($pf86) { Join-Path $pf86 "7-Zip\7z.exe" }),
    $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Programs\7-Zip\7z.exe" })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if ($sevenCandidates.Count -gt 0) {
    $extractor = $sevenCandidates[0]
    $kind = "7zip"
}

if (-not $extractor) {
    $cmd = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $extractor = $cmd.Source
        $kind = "7zip"
    }
}

if (-not $extractor) {
    $rarCandidates = @(
        (Join-Path $env:ProgramFiles "WinRAR\WinRAR.exe"),
        $(if ($pf86) { Join-Path $pf86 "WinRAR\WinRAR.exe" })
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

    if ($rarCandidates.Count -gt 0) {
        $extractor = $rarCandidates[0]
        $kind = "winrar"
    }
}

if (-not $extractor) {
    $cmd = Get-Command WinRAR.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $extractor = $cmd.Source
        $kind = "winrar"
    }
}

if (-not $extractor) {
    throw "No supported RAR extractor found. Install 7-Zip or WinRAR, then run this script again."
}

Write-Step ("Extractor: {0} ({1})" -f $extractor,$kind)
$first = Join-Path $volDir "Asphalt Xtreme.part1.rar"

if ($kind -eq "7zip") {
    & $extractor "x" "-y" ("-o" + $extractDir) $first
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip extraction failed with exit code $LASTEXITCODE"
    }
} else {
    & $extractor "x" "-o+" "-ibck" "-y" $first ($extractDir + "\")
    if ($LASTEXITCODE -ne 0) {
        throw "WinRAR extraction failed with exit code $LASTEXITCODE"
    }
}

Write-Step "Locating extracted game root"

function Find-GameRoot {
    param([string]$Root)
    $ams = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Filter "AMS.exe" -ErrorAction SilentlyContinue)
    if ($ams.Count -eq 0) { return $null }

    $preferred = $ams | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.Directory.FullName "AppxManifest.xml")
    } | Select-Object -First 1

    if ($preferred) { return $preferred.Directory.FullName }
    return ($ams | Sort-Object FullName | Select-Object -First 1).Directory.FullName
}

$gameRoot = Find-GameRoot -Root $extractDir

if (-not $gameRoot) {
    $appx = @(Get-ChildItem -LiteralPath $extractDir -Recurse -File -Filter "*.appx" -ErrorAction SilentlyContinue |
        Sort-Object Length -Descending | Select-Object -First 1)

    if ($appx.Count -gt 0) {
        Write-Step ("Found APPX container: " + $appx[0].FullName)
        $appxDir = Join-Path $runDir "appx-extracted"
        New-Item -ItemType Directory -Force -Path $appxDir | Out-Null
        $zipCopy = Join-Path $runDir "source-appx.zip"
        Copy-Item -LiteralPath $appx[0].FullName -Destination $zipCopy -Force
        Expand-Archive -LiteralPath $zipCopy -DestinationPath $appxDir -Force
        $gameRoot = Find-GameRoot -Root $appxDir
    }
}

if (-not $gameRoot) {
    throw "Extraction succeeded, but AMS.exe was not found."
}

$gameRoot | Set-Content -LiteralPath (Join-Path $runDir "game-root.txt") -Encoding UTF8
Write-Step ("Game root: " + $gameRoot)

if ($RunAudit) {
    $auditScript = Join-Path $PSScriptRoot "campaign_static_audit.ps1"
    if (-not (Test-Path -LiteralPath $auditScript)) {
        throw "Audit script not found: $auditScript"
    }

    $auditOut = Join-Path $runDir "audit"
    Write-Step "Running static Campaign dependency audit"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $auditScript -GameDir $gameRoot -OutputRoot $auditOut
    if ($LASTEXITCODE -ne 0) {
        throw "Campaign static audit failed with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "CAMPAIGN SOURCE PREPARED" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ("Working directory: " + $runDir)
Write-Host ("Game root: " + $gameRoot)
if ($RunAudit) {
    Write-Host ("Audit output: " + (Join-Path $runDir "audit"))
}
