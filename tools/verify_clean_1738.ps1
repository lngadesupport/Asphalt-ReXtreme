param(
    [string]$SourceDir = ".",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Base = "A278AB0D.AsphaltXtreme_1.7.3.8_x86__h6adky7gbf63m"
$Parts = 1..4 | ForEach-Object { Join-Path $SourceDir ("$Base.part$_.rar") }

foreach ($p in $Parts) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "Missing multipart archive: $p"
    }
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path (Resolve-Path $SourceDir).Path "CLEAN-1.7.3.8-EXTRACTED"
}

$seven = $null
$winrar = $null
foreach ($candidate in @(
    "$env:ProgramFiles\7-Zip\7z.exe",
    "$env:ProgramFiles(x86)\7-Zip\7z.exe"
)) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
        $seven = $candidate
        break
    }
}

if (-not $seven) {
    foreach ($candidate in @(
        "$env:ProgramFiles\WinRAR\WinRAR.exe",
        "$env:ProgramFiles(x86)\WinRAR\WinRAR.exe"
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $winrar = $candidate
            break
        }
    }
}

if (-not $seven -and -not $winrar) {
    throw "7-Zip or WinRAR was not found."
}

$first = $Parts[0]

Write-Host "Testing multipart archive..." -ForegroundColor Cyan
if ($seven) {
    & $seven t $first | Tee-Object -FilePath (Join-Path $SourceDir "CLEAN-1738-RAR-TEST.txt")
    if ($LASTEXITCODE -ne 0) { throw "7-Zip test failed: $LASTEXITCODE" }
} else {
    & $winrar t -ibck $first | Tee-Object -FilePath (Join-Path $SourceDir "CLEAN-1738-RAR-TEST.txt")
    if ($LASTEXITCODE -ne 0) { throw "WinRAR test failed: $LASTEXITCODE" }
}

if (Test-Path -LiteralPath $OutputDir) {
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Write-Host "Extracting clean 1.7.3.8 baseline..." -ForegroundColor Cyan
if ($seven) {
    & $seven x -y "-o$OutputDir" $first
    if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed: $LASTEXITCODE" }
} else {
    & $winrar x -y -ibck $first "$OutputDir\"
    if ($LASTEXITCODE -ne 0) { throw "WinRAR extraction failed: $LASTEXITCODE" }
}

$ams = Get-ChildItem -LiteralPath $OutputDir -Recurse -File -Filter "AMS.exe" |
    Sort-Object Length -Descending |
    Select-Object -First 1
if (-not $ams) { throw "AMS.exe not found after extraction." }

$gameRoot = $ams.Directory.FullName
$coreNames = @(
    "AMS.exe",
    "WCPToolkit.dll",
    "InAppPurchaseComponentW8.dll",
    "IGPLib_x86.dll",
    "Microsoft.Live.dll",
    "Facebook.dll",
    "AppxManifest.xml",
    "AMS.winmd",
    "resources.pri",
    "App.xbf",
    "DirectXPage.xbf"
)

$known = @{
    "AMS.exe" = "3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8"
    "WCPToolkit.dll" = "ca67dd62c599d00868b230e4e536bb1ad4ad3c19f3e62293e42cd297b44b60a5"
    "InAppPurchaseComponentW8.dll" = "1699bf0d42e336c738785a2985db20e72205478a14df569e75ff4eea49a08e77"
    "IGPLib_x86.dll" = "a17bc02a6b799bc5bcb219a04ba1bfa4501efe7b9b47adeb4b0a1ab89580f2b5"
    "Microsoft.Live.dll" = "ca8ae5a3226394c3ca84a671d5e90f7d5f972d4aecbbbaa6bcf451f4bff5e320"
    "Facebook.dll" = "271a2199abc52783aea3104765cb87ace7e4fde9a9654b91be70bace0e630191"
}

$rows = foreach ($name in $coreNames) {
    $p = Join-Path $gameRoot $name
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        $item = Get-Item -LiteralPath $p
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
        $expected = if ($known.ContainsKey($name)) { $known[$name] } else { "" }
        [pscustomobject]@{
            File = $name
            Present = $true
            Size = $item.Length
            SHA256 = $hash
            KnownSHA256 = $expected
            KnownMatch = if ($expected) { $hash -eq $expected } else { $null }
        }
    } else {
        [pscustomobject]@{
            File = $name
            Present = $false
            Size = 0
            SHA256 = ""
            KnownSHA256 = if ($known.ContainsKey($name)) { $known[$name] } else { "" }
            KnownMatch = $false
        }
    }
}

$allFiles = @(Get-ChildItem -LiteralPath $gameRoot -Recurse -File)
$zero = @($allFiles | Where-Object Length -eq 0)

$reportDir = Join-Path $SourceDir "CLEAN-1738-REPORT"
if (Test-Path -LiteralPath $reportDir) { Remove-Item -LiteralPath $reportDir -Recurse -Force }
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reportDir "core-hashes.csv")

$summary = [ordered]@{
    Build = "1.7.3.8"
    Architecture = "x86"
    SourceParts = 4
    GameRoot = $gameRoot
    FileCount = $allFiles.Count
    ZeroByteFiles = $zero.Count
    AMSMatchesKnownOriginal = (($rows | Where-Object File -eq "AMS.exe").KnownMatch)
    CoreKnownMatches = @(
        $rows | Where-Object { $_.KnownSHA256 -and $_.KnownMatch -eq $true } | Select-Object -ExpandProperty File
    )
    CoreKnownMismatches = @(
        $rows | Where-Object { $_.KnownSHA256 -and $_.KnownMatch -ne $true } | Select-Object -ExpandProperty File
    )
}

$summary | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $reportDir "summary.json") -Encoding UTF8

$allFiles | ForEach-Object {
    [pscustomobject]@{
        Path = $_.FullName.Substring($gameRoot.Length).TrimStart("\")
        Size = $_.Length
        SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
} | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reportDir "full-manifest.csv")

Compress-Archive -Path (Join-Path $reportDir "*") -DestinationPath (Join-Path $SourceDir "CLEAN-1738-REPORT.zip") -Force

Write-Host ""
Write-Host "CLEAN 1.7.3.8 VALIDATION COMPLETE" -ForegroundColor Green
Write-Host "Game root: $gameRoot"
Write-Host "Files: $($allFiles.Count)"
Write-Host "Zero-byte files: $($zero.Count)"
Write-Host "AMS known-original match: $($summary.AMSMatchesKnownOriginal)"
Write-Host "Report: $(Join-Path $SourceDir 'CLEAN-1738-REPORT.zip')"
