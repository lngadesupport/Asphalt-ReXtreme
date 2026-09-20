param(
    [Parameter(Mandatory=$true)]
    [string]$GameDir,

    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Get-RelativePathCompat {
    param([string]$Base, [string]$Full)
    $baseNorm = [System.IO.Path]::GetFullPath($Base).TrimEnd("\") + "\"
    $fullNorm = [System.IO.Path]::GetFullPath($Full)
    if ($fullNorm.StartsWith($baseNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fullNorm.Substring($baseNorm.Length)
    }
    return $fullNorm
}

function Extract-BinaryStrings {
    param([System.IO.FileInfo]$File, [int64]$MaxBytes = 268435456)

    $set = New-Object System.Collections.Generic.HashSet[string]
    if ($File.Length -gt $MaxBytes) { return $set }

    try {
        $bytes = [System.IO.File]::ReadAllBytes($File.FullName)
        $ascii = [System.Text.Encoding]::ASCII.GetString($bytes)
        foreach ($m in [regex]::Matches($ascii, "[\x20-\x7E]{5,}")) {
            [void]$set.Add($m.Value)
            if ($set.Count -ge 150000) { break }
        }

        if ($set.Count -lt 150000) {
            $unicode = [System.Text.Encoding]::Unicode.GetString($bytes)
            foreach ($m in [regex]::Matches($unicode, "[\x20-\x7E]{5,}")) {
                [void]$set.Add($m.Value)
                if ($set.Count -ge 150000) { break }
            }
        }
    } catch {}
    return $set
}

$root = (Resolve-Path -LiteralPath $GameDir).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "campaign-audit-output"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $OutputRoot ("Campaign-Audit-" + $stamp)
$reports = Join-Path $runDir "reports"
$collected = Join-Path $runDir "collected"
New-Item -ItemType Directory -Force -Path $reports,$collected | Out-Null

$signatures = [ordered]@{
    package_identity = @(
        "AppxManifest.xml",
        "AppxSignature.p7x",
        "AppxBlockMap.xml",
        "PackageFamilyName",
        "PackageFullName",
        "AppUserModelID",
        "Windows.ApplicationModel.Package",
        "PackageManager",
        "A278AB0D.AsphaltXtreme",
        "h6adky7gbf63m"
    )
    store_iap = @(
        "Windows.ApplicationModel.Store",
        "Windows.Services.Store",
        "CurrentApp",
        "CurrentAppSimulator",
        "StoreContext",
        "ms-windows-store:",
        "InAppPurchaseComponentW8",
        "IapComponent"
    )
    microsoft_auth = @(
        "Microsoft.Live",
        "XboxLive",
        "Xbox Live",
        "OnlineId",
        "WebAuthenticationBroker",
        "Microsoft account"
    )
    uwp_activation = @(
        "Windows.ApplicationModel.Activation",
        "Windows.ApplicationModel.Core",
        "CoreApplication",
        "RoActivateInstance",
        "RoGetActivationFactory",
        "Windows.UI.Core",
        "Windows.Foundation",
        "api-ms-win-appmodel",
        "api-ms-win-core-winrt"
    )
    gameloft_services = @(
        "iap.gameloft.com",
        "secure.gameloft.com",
        "eve.gameloft.com",
        "gameoptions.gameloft.com",
        "201205igp.gameloft.com",
        "scripts/ad_rewards/",
        "scripts/credits/",
        "scripts/energy/",
        "IGPLib_x86.dll"
    )
    social_telemetry = @(
        "Facebook.dll",
        "GoogleAnalytics",
        "Vungle",
        "advertisingId",
        "telemetry",
        "analytics"
    )
}

$allFiles = @(Get-ChildItem -LiteralPath $root -Recurse -File)
$inventory = New-Object System.Collections.Generic.List[object]

foreach ($f in $allFiles) {
    $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
    $hash = ""
    try { $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName).Hash.ToLowerInvariant() } catch {}
    $inventory.Add([pscustomobject]@{
        Path = $rel
        Size = $f.Length
        Extension = $f.Extension.ToLowerInvariant()
        SHA256 = $hash
    })
}
$inventory | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reports "inventory.csv")

$focusExtensions = @(".exe",".dll",".winmd",".xml",".json",".ini",".cfg",".txt",".dat",".bin")
$findings = New-Object System.Collections.Generic.List[object]
$dllCandidates = New-Object System.Collections.Generic.HashSet[string]

foreach ($f in $allFiles) {
    $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
    $nameLower = $f.Name.ToLowerInvariant()

    if ($nameLower -in @("appxmanifest.xml","appxsignature.p7x","appxblockmap.xml","[content_types].xml")) {
        $findings.Add([pscustomobject]@{
            File = $rel
            Category = "package_identity"
            Signature = $f.Name
            Source = "package-file"
        })
    }

    if ($focusExtensions -notcontains $f.Extension.ToLowerInvariant()) { continue }
    if ($f.Length -gt 268435456) { continue }

    $strings = Extract-BinaryStrings -File $f
    foreach ($s in $strings) {
        $clean = ($s -replace "[\r\n\t]+"," ").Trim()
        if (-not $clean) { continue }

        foreach ($category in $signatures.Keys) {
            foreach ($sig in $signatures[$category]) {
                if ($clean.IndexOf($sig, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    $findings.Add([pscustomobject]@{
                        File = $rel
                        Category = $category
                        Signature = $sig
                        Source = "string"
                    })
                }
            }
        }

        foreach ($m in [regex]::Matches($clean, "(?i)\b[a-z0-9_.-]+\.dll\b")) {
            [void]$dllCandidates.Add(($rel + [char]9 + $m.Value.ToLowerInvariant()))
        }
    }
}

$uniqueFindings = @($findings | Sort-Object File,Category,Signature,Source -Unique)
$uniqueFindings | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reports "microsoft-service-findings.csv")
$dllCandidates | Sort-Object | Set-Content -LiteralPath (Join-Path $reports "dll-string-candidates.tsv") -Encoding UTF8

$categoryCounts = @{}
foreach ($category in $signatures.Keys) {
    $categoryCounts[$category] = @($uniqueFindings | Where-Object { $_.Category -eq $category }).Count
}

$fileSummary = @(
    $uniqueFindings |
    Group-Object File |
    ForEach-Object {
        $cats = @($_.Group.Category | Sort-Object -Unique)
        [pscustomobject]@{
            File = $_.Name
            FindingCount = $_.Count
            Categories = ($cats -join ",")
        }
    } |
    Sort-Object -Property @{Expression={$_.FindingCount};Descending=$true}, File
)
$fileSummary | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reports "finding-summary-by-file.csv")

$keyNames = @(
    "AMS.exe",
    "AppxManifest.xml",
    "WCPToolkit.dll",
    "InAppPurchaseComponentW8.dll",
    "IGPLib_x86.dll",
    "Microsoft.Live.dll",
    "Facebook.dll"
)

foreach ($name in $keyNames) {
    $matches = @($allFiles | Where-Object { $_.Name -ieq $name })
    foreach ($f in $matches) {
        $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
        $dst = Join-Path $collected $rel
        $parent = Split-Path -Parent $dst
        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
    }
}

$summary = New-Object System.Collections.Generic.List[string]
$summary.Add("Asphalt ReXtreme: Campaign Edition static audit")
$summary.Add("Generated: $(Get-Date -Format o)")
$summary.Add("GameRoot: $root")
$summary.Add("FilesScanned: $($allFiles.Count)")
$summary.Add("Findings: $($uniqueFindings.Count)")
$summary.Add("")
$summary.Add("Category counts:")
foreach ($category in $signatures.Keys) {
    $summary.Add(("  {0}: {1}" -f $category,$categoryCounts[$category]))
}
$summary.Add("")
$summary.Add("Interpretation:")
$summary.Add("  package_identity/store_iap/microsoft_auth are direct removal/replacement targets.")
$summary.Add("  uwp_activation findings require call-site classification; some WinRT helpers may be generic Windows plumbing.")
$summary.Add("  gameloft_services/social_telemetry are separate offline-service removal targets.")
$summary.Add("")
$summary.Add("This audit does not register APPX, query Microsoft Store, launch the game, or modify Windows.")
$summary | Set-Content -LiteralPath (Join-Path $runDir "REPORT_README.txt") -Encoding UTF8

$zipPath = $runDir + ".zip"
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zipPath -CompressionLevel Optimal -Force
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
("SHA256  " + $zipHash + "  " + [System.IO.Path]::GetFileName($zipPath)) |
    Set-Content -LiteralPath ($zipPath + ".sha256.txt") -Encoding UTF8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "CAMPAIGN STATIC AUDIT COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ("Report: " + $runDir)
Write-Host ("ZIP: " + $zipPath)
