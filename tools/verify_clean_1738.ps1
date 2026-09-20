param(
    [string]$SourceDir = ".",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Base = "A278AB0D.AsphaltXtreme_1.7.3.8_x86__h6adky7gbf63m"
$ExpectedSizes = @(
    [int64]524288000,
    [int64]524288000,
    [int64]524288000,
    [int64]319794274
)

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$Parts = @()
for ($i = 1; $i -le 4; $i++) {
    $Parts += Join-Path $SourceDir ("{0}.part{1}.rar" -f $Base, $i)
}

Write-Host "============================================================"
Write-Host " Asphalt ReXtreme - CLEAN BASELINE 1.7.3.8 x86"
Write-Host " Phase 1: source validation only"
Write-Host "============================================================"
Write-Host ""

$partRows = @()
$sizeOK = $true
for ($i = 0; $i -lt $Parts.Count; $i++) {
    $p = $Parts[$i]
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "Missing multipart archive: $p"
    }

    $item = Get-Item -LiteralPath $p
    $expected = $ExpectedSizes[$i]
    $matches = ([int64]$item.Length -eq $expected)
    if (-not $matches) { $sizeOK = $false }

    Write-Host ("Hashing part {0}/4..." -f ($i + 1))
    $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()

    $partRows += [pscustomobject]@{
        Part = $i + 1
        File = $item.Name
        Size = [int64]$item.Length
        ExpectedSize = $expected
        SizeMatch = $matches
        SHA256 = $sha
    }
}

$archiverPath = $null
$archiverKind = $null

$commands = @(
    @{ Kind = "7zip"; Name = "7z.exe" },
    @{ Kind = "unrar"; Name = "UnRAR.exe" },
    @{ Kind = "winrar"; Name = "WinRAR.exe" }
)
foreach ($c in $commands) {
    $cmd = Get-Command $c.Name -ErrorAction SilentlyContinue
    if ($cmd) {
        $archiverPath = $cmd.Source
        $archiverKind = $c.Kind
        break
    }
}

if (-not $archiverPath) {
    $candidates = @()
    if (\${env:ProgramFiles}) {
        $candidates += @{ Kind="7zip"; Path=(Join-Path \${env:ProgramFiles} "7-Zip\7z.exe") }
        $candidates += @{ Kind="unrar"; Path=(Join-Path \${env:ProgramFiles} "WinRAR\UnRAR.exe") }
        $candidates += @{ Kind="winrar"; Path=(Join-Path \${env:ProgramFiles} "WinRAR\WinRAR.exe") }
    }
    if (\${env:ProgramFiles(x86)}) {
        $candidates += @{ Kind="7zip"; Path=(Join-Path \${env:ProgramFiles(x86)} "7-Zip\7z.exe") }
        $candidates += @{ Kind="unrar"; Path=(Join-Path \${env:ProgramFiles(x86)} "WinRAR\UnRAR.exe") }
        $candidates += @{ Kind="winrar"; Path=(Join-Path \${env:ProgramFiles(x86)} "WinRAR\WinRAR.exe") }
    }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c.Path -PathType Leaf) {
            $archiverPath = $c.Path
            $archiverKind = $c.Kind
            break
        }
    }
}

if (-not $archiverPath) {
    throw "7-Zip/UnRAR/WinRAR was not found. Install WinRAR or 7-Zip and rerun this verifier."
}

$first = $Parts[0]
$reportDir = Join-Path $SourceDir "CLEAN-1738-REPORT"
if (Test-Path -LiteralPath $reportDir) {
    Remove-Item -LiteralPath $reportDir -Recurse -Force
}
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$partRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reportDir "archive-parts.csv")

Write-Host ""
Write-Host "Testing the complete multipart archive..." -ForegroundColor Cyan
$testLog = Join-Path $reportDir "archive-test.txt"

if ($archiverKind -eq "7zip") {
    $testOutput = @(& $archiverPath t -bso1 -bsp0 $first 2>&1)
} elseif ($archiverKind -eq "unrar") {
    $testOutput = @(& $archiverPath t -idq $first 2>&1)
} else {
    $testOutput = @(& $archiverPath t -ibck $first 2>&1)
}
$testExit = $LASTEXITCODE
$testOutput | Set-Content -LiteralPath $testLog -Encoding UTF8
if ($testExit -ne 0) {
    throw "Multipart RAR integrity test failed with exit code $testExit. See $testLog"
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $SourceDir "CLEAN-1.7.3.8-EXTRACTED"
}
if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $SourceDir $OutputDir
}

if (Test-Path -LiteralPath $OutputDir) {
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Write-Host "Extracting a fresh baseline..." -ForegroundColor Cyan
if ($archiverKind -eq "7zip") {
    & $archiverPath x -y -bso1 -bsp0 ("-o{0}" -f $OutputDir) $first
} elseif ($archiverKind -eq "unrar") {
    & $archiverPath x -y -idq $first ($OutputDir + "\")
} else {
    & $archiverPath x -y -ibck $first ($OutputDir + "\")
}
if ($LASTEXITCODE -ne 0) {
    throw "Extraction failed with exit code $LASTEXITCODE"
}

$amsCandidates = @(Get-ChildItem -LiteralPath $OutputDir -Recurse -File -Filter "AMS.exe")
if ($amsCandidates.Count -ne 1) {
    throw "Expected exactly one AMS.exe after extraction; found $($amsCandidates.Count)."
}
$gameRoot = $amsCandidates[0].Directory.FullName

$requiredFiles = @(
    "AMS.exe",
    "WCPToolkit.dll",
    "InAppPurchaseComponentW8.dll",
    "IGPLib_x86.dll",
    "AppxManifest.xml",
    "resources.pri",
    "App.xbf",
    "DirectXPage.xbf"
)
$requiredDirs = @("Assets", "data")

$missingFiles = @()
foreach ($name in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $gameRoot $name) -PathType Leaf)) {
        $missingFiles += $name
    }
}
$missingDirs = @()
foreach ($name in $requiredDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $gameRoot $name) -PathType Container)) {
        $missingDirs += $name
    }
}

$manifestPath = Join-Path $gameRoot "AppxManifest.xml"
[xml]$manifest = Get-Content -LiteralPath $manifestPath -Raw
$identity = $manifest.Package.Identity

$identityName = [string]$identity.Name
$identityVersion = [string]$identity.Version
$identityArch = [string]$identity.ProcessorArchitecture

$identityOK = (
    $identityName -eq "A278AB0D.AsphaltXtreme" -and
    $identityVersion -eq "1.7.3.8" -and
    $identityArch -eq "x86"
)

$allFiles = @(Get-ChildItem -LiteralPath $gameRoot -Recurse -File)
$zeroFiles = @($allFiles | Where-Object { $_.Length -eq 0 })

Write-Host "Building full SHA-256 manifest..." -ForegroundColor Cyan
$manifestRows = @()
foreach ($f in $allFiles) {
    $relative = $f.FullName.Substring($gameRoot.Length).TrimStart("\")
    $manifestRows += [pscustomobject]@{
        Path = $relative
        Size = [int64]$f.Length
        SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName).Hash.ToLowerInvariant()
    }
}
$manifestRows |
    Sort-Object Path |
    Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reportDir "full-manifest.csv")

$zeroFiles | ForEach-Object {
    $_.FullName.Substring($gameRoot.Length).TrimStart("\")
} | Set-Content -LiteralPath (Join-Path $reportDir "zero-byte-files.txt") -Encoding UTF8

$amsRow = $manifestRows | Where-Object { $_.Path -ieq "AMS.exe" } | Select-Object -First 1

$baselineOK = (
    $sizeOK -and
    $testExit -eq 0 -and
    $identityOK -and
    $missingFiles.Count -eq 0 -and
    $missingDirs.Count -eq 0 -and
    $zeroFiles.Count -eq 0
)

$summary = [ordered]@{
    Baseline = "Asphalt Xtreme 1.7.3.8 x86 CLEAN"
    PackageName = $identityName
    PackageVersion = $identityVersion
    ProcessorArchitecture = $identityArch
    ArchiveParts = 4
    ArchiveTotalBytes = [int64](($partRows | Measure-Object -Property Size -Sum).Sum)
    ArchiveSizesMatchExpected = $sizeOK
    ArchiveIntegrityTestPassed = ($testExit -eq 0)
    GameRoot = $gameRoot
    FileCount = $allFiles.Count
    TotalExtractedBytes = [int64](($allFiles | Measure-Object -Property Length -Sum).Sum)
    ZeroByteFiles = $zeroFiles.Count
    MissingRequiredFiles = $missingFiles
    MissingRequiredDirectories = $missingDirs
    PackageIdentityMatches1738x86 = $identityOK
    AMS_SHA256 = if ($amsRow) { $amsRow.SHA256 } else { "" }
    BaselineValid = $baselineOK
    Note = "Phase 1 only. AMS.exe is hashed but not modified or evaluated against Campaign patches."
}

$summary | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $reportDir "baseline-summary.json") -Encoding UTF8

$zipPath = Join-Path $SourceDir "CLEAN-1738-REPORT.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $reportDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "============================================================"
if ($baselineOK) {
    Write-Host " BASELINE VALID: 1.7.3.8 x86 CLEAN" -ForegroundColor Green
} else {
    Write-Host " BASELINE VALIDATION FAILED" -ForegroundColor Red
}
Write-Host "============================================================"
Write-Host ("Files:               {0}" -f $allFiles.Count)
Write-Host ("Zero-byte files:     {0}" -f $zeroFiles.Count)
Write-Host ("Package identity OK: {0}" -f $identityOK)
Write-Host ("RAR sizes OK:        {0}" -f $sizeOK)
Write-Host ("RAR integrity OK:    {0}" -f ($testExit -eq 0))
Write-Host ("AMS SHA-256:         {0}" -f $summary.AMS_SHA256)
Write-Host ("Report:              {0}" -f $zipPath)
Write-Host ""

if (-not $baselineOK) {
    exit 20
}
exit 0
