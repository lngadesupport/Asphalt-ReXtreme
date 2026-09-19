param(
    [Parameter(Mandatory=$true)]
    [string]$GameDir,

    [ValidateSet("Safe","Deep")]
    [string]$Mode = "Safe",

    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$CollectorVersion = "1.0.0"
$TargetPackage = "A278AB0D.AsphaltXtreme"
$TargetVersion = "1.7.3.8"
$TargetArch = "x86"
$TargetFamily = "A278AB0D.AsphaltXtreme_h6adky7gbf63m"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = ("{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message)
    Add-Content -LiteralPath $script:LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Get-RelativePathCompat {
    param([string]$Base, [string]$Full)
    $baseNorm = [System.IO.Path]::GetFullPath($Base).TrimEnd("\") + "\"
    $fullNorm = [System.IO.Path]::GetFullPath($Full)
    if ($fullNorm.StartsWith($baseNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fullNorm.Substring($baseNorm.Length)
    }
    return $fullNorm
}

function Safe-CopyFile {
    param([System.IO.FileInfo]$File, [string]$Root, [string]$DestRoot)
    try {
        $rel = Get-RelativePathCompat -Base $Root -Full $File.FullName
        $dst = Join-Path $DestRoot $rel
        $parent = Split-Path -Parent $dst
        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        Copy-Item -LiteralPath $File.FullName -Destination $dst -Force
        return $true
    } catch {
        Write-Log ("Copy failed: {0} :: {1}" -f $File.FullName, $_.Exception.Message) "WARN"
        return $false
    }
}

function Get-Sha256Safe {
    param([string]$Path)
    try {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    } catch {
        Write-Log ("SHA256 failed: {0} :: {1}" -f $Path, $_.Exception.Message) "WARN"
        return ""
    }
}

function Get-PEBasicInfo {
    param([string]$Path)
    $result = [ordered]@{
        Path = $Path
        IsPE = $false
        Machine = ""
        Architecture = ""
        TimestampUtc = ""
        Sections = ""
        Characteristics = ""
    }
    try {
        $fs = $null
        $br = $null
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $br = New-Object System.IO.BinaryReader($fs)
            if ($br.ReadUInt16() -ne 0x5A4D) { return [pscustomobject]$result }
            $fs.Position = 0x3C
            $peOffset = $br.ReadInt32()
            if ($peOffset -lt 0 -or $peOffset -gt ($fs.Length - 256)) { return [pscustomobject]$result }
            $fs.Position = $peOffset
            if ($br.ReadUInt32() -ne 0x00004550) { return [pscustomobject]$result }

            $machine = $br.ReadUInt16()
            $numSections = $br.ReadUInt16()
            $timeStamp = $br.ReadUInt32()
            [void]$br.ReadUInt32()
            [void]$br.ReadUInt32()
            $sizeOptional = $br.ReadUInt16()
            $characteristics = $br.ReadUInt16()

            $arch = switch ($machine) {
                0x014c { "x86" }
                0x8664 { "x64" }
                0x01c0 { "ARM" }
                0xAA64 { "ARM64" }
                default { ("0x{0:X4}" -f $machine) }
            }

            $sectionOffset = $peOffset + 24 + $sizeOptional
            $names = New-Object System.Collections.Generic.List[string]
            if ($numSections -le 96 -and $sectionOffset -lt $fs.Length) {
                $fs.Position = $sectionOffset
                for ($i = 0; $i -lt $numSections; $i++) {
                    if (($fs.Position + 40) -gt $fs.Length) { break }
                    $nameBytes = $br.ReadBytes(8)
                    $name = [System.Text.Encoding]::ASCII.GetString($nameBytes).Trim([char]0)
                    if ($name) { $names.Add($name) }
                    $fs.Position += 32
                }
            }

            $epoch = [DateTimeOffset]::FromUnixTimeSeconds([int64]$timeStamp).UtcDateTime
            $result.IsPE = $true
            $result.Machine = ("0x{0:X4}" -f $machine)
            $result.Architecture = $arch
            $result.TimestampUtc = $epoch.ToString("o")
            $result.Sections = ($names -join ",")
            $result.Characteristics = ("0x{0:X4}" -f $characteristics)
        } finally {
            if ($br) { $br.Close() }
            if ($fs) { $fs.Close() }
        }
    } catch {
        Write-Log ("PE parse failed: {0} :: {1}" -f $Path, $_.Exception.Message) "WARN"
    }
    return [pscustomobject]$result
}

function Extract-BinaryStrings {
    param([System.IO.FileInfo]$File, [int64]$MaxBytes = 134217728)

    $list = New-Object System.Collections.Generic.HashSet[string]
    if ($File.Length -gt $MaxBytes) { return $list }

    try {
        $bytes = [System.IO.File]::ReadAllBytes($File.FullName)
        $ascii = [System.Text.Encoding]::ASCII.GetString($bytes)
        foreach ($m in [regex]::Matches($ascii, "[\x20-\x7E]{5,}")) {
            [void]$list.Add($m.Value)
            if ($list.Count -ge 100000) { break }
        }

        if ($list.Count -lt 100000) {
            $unicode = [System.Text.Encoding]::Unicode.GetString($bytes)
            foreach ($m in [regex]::Matches($unicode, "[\x20-\x7E]{5,}")) {
                [void]$list.Add($m.Value)
                if ($list.Count -ge 100000) { break }
            }
        }
    } catch {
        Write-Log ("String extraction failed: {0} :: {1}" -f $File.FullName, $_.Exception.Message) "WARN"
    }
    return $list
}

$root = (Resolve-Path -LiteralPath $GameDir).Path

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "collector-output"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runName = "ReXtreme-Collector-$stamp"
$runDir = Join-Path $OutputRoot $runName
$reportsDir = Join-Path $runDir "reports"
$collectedDir = Join-Path $runDir "collected"
$binariesDir = Join-Path $collectedDir "binaries"
$candidatesDir = Join-Path $collectedDir "candidates"
$savesDir = Join-Path $runDir "save-snapshot"
New-Item -ItemType Directory -Force -Path $reportsDir,$binariesDir,$candidatesDir | Out-Null

$script:LogPath = Join-Path $runDir "collector.log"
"" | Set-Content -LiteralPath $script:LogPath -Encoding UTF8

Write-Log "Asphalt ReXtreme Collector $CollectorVersion"
Write-Log "Mode: $Mode"
Write-Log "Game root: $root"

# ---------------------------------------------------------------------------
# System information (intentionally excludes username, computer name and IPs)
# ---------------------------------------------------------------------------
Write-Log "Collecting system information"
$systemLines = New-Object System.Collections.Generic.List[string]
$systemLines.Add("Asphalt ReXtreme Collector $CollectorVersion")
$systemLines.Add("Mode: $Mode")
$systemLines.Add("Generated: $(Get-Date -Format o)")
$systemLines.Add("")
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $systemLines.Add("OS: $($os.Caption)")
    $systemLines.Add("OS Version: $($os.Version)")
    $systemLines.Add("OS Build: $($os.BuildNumber)")
    $systemLines.Add("OS Architecture: $($os.OSArchitecture)")
} catch {}
try {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $systemLines.Add("CPU: $($cpu.Name)")
    $systemLines.Add("CPU Cores: $($cpu.NumberOfCores)")
    $systemLines.Add("CPU LogicalProcessors: $($cpu.NumberOfLogicalProcessors)")
} catch {}
try {
    $cs = Get-CimInstance Win32_ComputerSystem
    $ramGB = [Math]::Round(($cs.TotalPhysicalMemory / 1GB), 2)
    $systemLines.Add("RAM_GB: $ramGB")
} catch {}
try {
    foreach ($gpu in (Get-CimInstance Win32_VideoController)) {
        $systemLines.Add("GPU: $($gpu.Name)")
        if ($gpu.DriverVersion) { $systemLines.Add("GPU Driver: $($gpu.DriverVersion)") }
        if ($gpu.CurrentHorizontalResolution -and $gpu.CurrentVerticalResolution) {
            $systemLines.Add("Display: $($gpu.CurrentHorizontalResolution)x$($gpu.CurrentVerticalResolution)")
        }
    }
} catch {}
$systemLines.Add("Culture: $([System.Globalization.CultureInfo]::CurrentCulture.Name)")
$systemLines.Add("PowerShell: $($PSVersionTable.PSVersion)")
$systemLines | Set-Content -LiteralPath (Join-Path $reportsDir "system-info.txt") -Encoding UTF8

# ---------------------------------------------------------------------------
# AppX registration
# ---------------------------------------------------------------------------
Write-Log "Checking AppX registration"
try {
    $pkg = Get-AppxPackage -Name $TargetPackage -ErrorAction SilentlyContinue
    if ($pkg) {
        $pkg | Select-Object Name,Version,Architecture,PackageFullName,PackageFamilyName,Status |
            Format-List | Out-String |
            Set-Content -LiteralPath (Join-Path $reportsDir "appx-registration.txt") -Encoding UTF8
    } else {
        "Package is not currently registered for this Windows user." |
            Set-Content -LiteralPath (Join-Path $reportsDir "appx-registration.txt") -Encoding UTF8
    }
} catch {
    ("AppX query failed: " + $_.Exception.Message) |
        Set-Content -LiteralPath (Join-Path $reportsDir "appx-registration.txt") -Encoding UTF8
}

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
$manifest = Join-Path $root "AppxManifest.xml"
$manifestSummary = New-Object System.Collections.Generic.List[string]
$manifestSummary.Add("Target expected: $TargetPackage $TargetVersion $TargetArch")
if (Test-Path -LiteralPath $manifest) {
    Write-Log "Parsing AppxManifest.xml"
    try {
        [xml]$xml = Get-Content -LiteralPath $manifest -Raw
        $identity = $xml.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Identity']")
        if ($identity) {
            $manifestSummary.Add("Identity.Name: $($identity.GetAttribute('Name'))")
            $manifestSummary.Add("Identity.Version: $($identity.GetAttribute('Version'))")
            $manifestSummary.Add("Identity.Architecture: $($identity.GetAttribute('ProcessorArchitecture'))")
            $manifestSummary.Add("Identity.Publisher: $($identity.GetAttribute('Publisher'))")
        }
        foreach ($app in $xml.SelectNodes("//*[local-name()='Application']")) {
            $manifestSummary.Add("Application: Id=$($app.GetAttribute('Id')) Executable=$($app.GetAttribute('Executable')) EntryPoint=$($app.GetAttribute('EntryPoint'))")
        }
        foreach ($dep in $xml.SelectNodes("//*[local-name()='Dependencies']/*")) {
            $manifestSummary.Add("Dependency: $($dep.OuterXml)")
        }
        foreach ($cap in $xml.SelectNodes("//*[local-name()='Capabilities']/*")) {
            $manifestSummary.Add("Capability: $($cap.OuterXml)")
        }
    } catch {
        $manifestSummary.Add("Manifest parse error: $($_.Exception.Message)")
    }
} else {
    $manifestSummary.Add("AppxManifest.xml NOT FOUND at package root.")
}
$manifestSummary | Set-Content -LiteralPath (Join-Path $reportsDir "manifest-summary.txt") -Encoding UTF8

# ---------------------------------------------------------------------------
# Full inventory + SHA-256
# ---------------------------------------------------------------------------
Write-Log "Building complete inventory and SHA-256 list"
$allFiles = @(Get-ChildItem -LiteralPath $root -Recurse -File)
$inventory = New-Object System.Collections.Generic.List[object]
$counter = 0
foreach ($f in $allFiles) {
    $counter++
    if (($counter % 25) -eq 0) { Write-Log ("Hashing files: {0}/{1}" -f $counter,$allFiles.Count) }
    $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
    $hash = Get-Sha256Safe -Path $f.FullName
    $inventory.Add([pscustomobject]@{
        Path = $rel
        Size = $f.Length
        Extension = $f.Extension.ToLowerInvariant()
        LastWriteTimeUtc = $f.LastWriteTimeUtc.ToString("o")
        SHA256 = $hash
    })
}
$inventory | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reportsDir "inventory-with-hashes.csv")

# ---------------------------------------------------------------------------
# Binary metadata and copies
# ---------------------------------------------------------------------------
Write-Log "Collecting PE/binary metadata"
$binaryRows = New-Object System.Collections.Generic.List[object]
$peRows = New-Object System.Collections.Generic.List[object]
$binaries = @($allFiles | Where-Object { $_.Extension.ToLowerInvariant() -in @(".exe",".dll") })

foreach ($f in $binaries) {
    $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
    $hash = ($inventory | Where-Object { $_.Path -eq $rel } | Select-Object -First 1).SHA256
    $vi = $f.VersionInfo
    $binaryRows.Add([pscustomobject]@{
        Path = $rel
        Size = $f.Length
        SHA256 = $hash
        FileVersion = $vi.FileVersion
        ProductVersion = $vi.ProductVersion
        CompanyName = $vi.CompanyName
        ProductName = $vi.ProductName
        OriginalFilename = $vi.OriginalFilename
    })

    $pe = Get-PEBasicInfo -Path $f.FullName
    $peRows.Add([pscustomobject]@{
        Path = $rel
        IsPE = $pe.IsPE
        Machine = $pe.Machine
        Architecture = $pe.Architecture
        TimestampUtc = $pe.TimestampUtc
        Sections = $pe.Sections
        Characteristics = $pe.Characteristics
    })

    [void](Safe-CopyFile -File $f -Root $root -DestRoot $binariesDir)
}
$binaryRows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reportsDir "binary-metadata.csv")
$peRows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reportsDir "pe-metadata.csv")

# ---------------------------------------------------------------------------
# Text/config and filename candidate collection
# ---------------------------------------------------------------------------
Write-Log "Collecting configuration/economy/network candidates"
$namePattern = "(?i)(gameoption|purchase|iap|econom|currency|credit|token|coin|cash|price|reward|save|profile|config|event|garage|car|vehicle|upgrade|unlock|ads?|advert|server|network|online|offline|telemetry|analytics|fov|fps|frame|resolution|graphic|display|input|controller|camera)"
$exactNames = @(
    "AppxManifest.xml",
    "AppxBlockMap.xml",
    "[Content_Types].xml",
    "Gameoptions_W8.json",
    "in-app-purchase_w8.1.xml"
)
$textExtensions = @(".xml",".json",".ini",".cfg",".conf",".txt",".csv",".lua",".js",".plist",".properties",".log")
$candidateRows = New-Object System.Collections.Generic.List[object]

foreach ($f in $allFiles) {
    $isExact = $exactNames -contains $f.Name
    $isNamed = $f.Name -match $namePattern
    $isText = $textExtensions -contains $f.Extension.ToLowerInvariant()
    if (($isExact -or $isNamed -or $isText) -and $f.Length -le 67108864) {
        $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
        $candidateRows.Add([pscustomobject]@{
            Path = $rel
            Size = $f.Length
            Reason = $(if ($isExact) { "exact" } elseif ($isNamed) { "filename" } else { "text-extension" })
        })
        [void](Safe-CopyFile -File $f -Root $root -DestRoot $candidatesDir)
    }
}
$candidateRows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reportsDir "collected-candidates.csv")

# ---------------------------------------------------------------------------
# Keyword scan in text/config files
# ---------------------------------------------------------------------------
Write-Log "Scanning text/config files for project keywords"
$keywordCategories = [ordered]@{
    network = @("http://","https://","gameloft","server","endpoint","online","offline","login","auth","socket","lobby","matchmaking","multiplayer","cloud")
    ads = @("advert","rewarded","adcolony","admob","mediation","interstitial","banner","video ad")
    economy = @("purchase","iap","store","currency","credit","token","coin","cash","price","sku","product","upgrade","unlock","reward","energy","fuel")
    save = @("save","profile","localstate","roamingstate","applicationdata","settings")
    graphics = @("fps","framerate","frame rate","fov","fieldofview","resolution","vsync","fullscreen","borderless","windowed","dxgi","direct3d")
    input = @("controller","xinput","gamepad","keyboard","mouse","rawinput")
    telemetry = @("analytics","telemetry","tracking","facebook","live")
}

$textHitLines = New-Object System.Collections.Generic.List[string]
$urlSet = New-Object System.Collections.Generic.HashSet[string]
$domainSet = New-Object System.Collections.Generic.HashSet[string]

foreach ($f in $allFiles | Where-Object { ($textExtensions -contains $_.Extension.ToLowerInvariant()) -and $_.Length -le 16777216 }) {
    try {
        $content = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop
        $rel = Get-RelativePathCompat -Base $root -Full $f.FullName
        foreach ($cat in $keywordCategories.Keys) {
            foreach ($kw in $keywordCategories[$cat]) {
                if ($content.IndexOf($kw, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    $textHitLines.Add(($rel + [char]9 + $cat + [char]9 + $kw))
                }
            }
        }
        foreach ($m in [regex]::Matches($content, "https?://[^\s\x22\x27<>]+", "IgnoreCase")) {
            [void]$urlSet.Add($m.Value)
        }
        foreach ($m in [regex]::Matches($content, "(?i)(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|gg|tv|me|cloud|games|game)")) {
            [void]$domainSet.Add($m.Value)
        }
    } catch {}
}
$textHitLines | Sort-Object -Unique | Set-Content -LiteralPath (Join-Path $reportsDir "text-keyword-hits.tsv") -Encoding UTF8

# ---------------------------------------------------------------------------
# Interesting strings from EXE/DLL
# ---------------------------------------------------------------------------
Write-Log "Extracting interesting strings from EXE/DLL files"
$binaryHitLines = New-Object System.Collections.Generic.List[string]
$importCandidates = New-Object System.Collections.Generic.List[string]

foreach ($f in $binaries) {
    Write-Log ("Strings: " + (Get-RelativePathCompat -Base $root -Full $f.FullName))
    $strings = Extract-BinaryStrings -File $f
    $rel = Get-RelativePathCompat -Base $root -Full $f.FullName

    foreach ($s in $strings) {
        $clean = ($s -replace "[\r\n\t]+"," ").Trim()
        if (-not $clean) { continue }

        $matched = $false
        foreach ($cat in $keywordCategories.Keys) {
            foreach ($kw in $keywordCategories[$cat]) {
                if ($clean.IndexOf($kw, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    $binaryHitLines.Add(($rel + [char]9 + $cat + [char]9 + $clean))
                    $matched = $true
                    break
                }
            }
            if ($matched) { break }
        }

        foreach ($m in [regex]::Matches($clean, "https?://[^\s\x22\x27<>]+", "IgnoreCase")) {
            [void]$urlSet.Add($m.Value)
        }
        foreach ($m in [regex]::Matches($clean, "(?i)(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|gg|tv|me|cloud|games|game)")) {
            [void]$domainSet.Add($m.Value)
        }
        foreach ($m in [regex]::Matches($clean, "(?i)\b[a-z0-9_.-]+\.dll\b")) {
            $importCandidates.Add(($rel + [char]9 + $m.Value.ToLowerInvariant()))
        }
    }
}
$binaryHitLines | Sort-Object -Unique | Set-Content -LiteralPath (Join-Path $reportsDir "binary-interesting-strings.tsv") -Encoding UTF8
$importCandidates | Sort-Object -Unique | Set-Content -LiteralPath (Join-Path $reportsDir "imported-dll-candidates.tsv") -Encoding UTF8
$urlSet | Sort-Object | Set-Content -LiteralPath (Join-Path $reportsDir "urls.txt") -Encoding UTF8
$domainSet | Sort-Object | Set-Content -LiteralPath (Join-Path $reportsDir "domains.txt") -Encoding UTF8

# ---------------------------------------------------------------------------
# Save/package-state inventory. Deep mode also copies bytes.
# ---------------------------------------------------------------------------
Write-Log "Inspecting package save/state locations"
$packageDir = Join-Path $env:LOCALAPPDATA ("Packages\" + $TargetFamily)
$saveInventory = New-Object System.Collections.Generic.List[object]
if (Test-Path -LiteralPath $packageDir) {
    foreach ($sub in @("LocalState","RoamingState","Settings","TempState")) {
        $p = Join-Path $packageDir $sub
        if (Test-Path -LiteralPath $p) {
            foreach ($f in (Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue)) {
                $saveInventory.Add([pscustomobject]@{
                    Area = $sub
                    RelativePath = Get-RelativePathCompat -Base $p -Full $f.FullName
                    Size = $f.Length
                    LastWriteTimeUtc = $f.LastWriteTimeUtc.ToString("o")
                    SHA256 = Get-Sha256Safe -Path $f.FullName
                })
                if ($Mode -eq "Deep" -and $f.Length -le 67108864) {
                    $dest = Join-Path $savesDir $sub
                    [void](Safe-CopyFile -File $f -Root $p -DestRoot $dest)
                }
            }
        }
    }
}
$saveInventory | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $reportsDir "save-state-inventory.csv")

# ---------------------------------------------------------------------------
# Summary / readiness
# ---------------------------------------------------------------------------
Write-Log "Writing collector summary"
$summary = New-Object System.Collections.Generic.List[string]
$summary.Add("Asphalt ReXtreme Master Collector")
$summary.Add("CollectorVersion: $CollectorVersion")
$summary.Add("Mode: $Mode")
$summary.Add("Generated: $(Get-Date -Format o)")
$summary.Add("")
$summary.Add("ExpectedTarget: $TargetPackage $TargetVersion $TargetArch")
$summary.Add("FilesFound: $($allFiles.Count)")
$summary.Add("BinaryCount: $($binaries.Count)")
$summary.Add("CandidateFilesCopied: $($candidateRows.Count)")
$summary.Add("SaveFilesInventoried: $($saveInventory.Count)")
$summary.Add("")
$summary.Add("Key files:")
foreach ($name in @("AMS.exe","AppxManifest.xml","Gameoptions_W8.json","in-app-purchase_w8.1.xml","InAppPurchaseComponentW8.dll","IGPLib_x86.dll","Microsoft.Live.dll","Facebook.dll","WCPToolkit.dll")) {
    $match = $allFiles | Where-Object { $_.Name -ieq $name } | Select-Object -First 1
    if ($match) {
        $rel = Get-RelativePathCompat -Base $root -Full $match.FullName
        $hash = ($inventory | Where-Object { $_.Path -eq $rel } | Select-Object -First 1).SHA256
        $summary.Add(("  FOUND {0} | {1} | {2}" -f $name,$match.Length,$hash))
    } else {
        $summary.Add(("  MISSING {0}" -f $name))
    }
}
$summary.Add("")
$summary.Add("Use this ZIP for all future ReXtreme analysis stages.")
$summary.Add("The collector never patches or launches the game.")
$summary | Set-Content -LiteralPath (Join-Path $runDir "REPORT_README.txt") -Encoding UTF8

# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------
Write-Log "Creating ZIP"
$zipPath = Join-Path $OutputRoot ($runName + ".zip")
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zipPath -CompressionLevel Optimal -Force
$zipHash = Get-Sha256Safe -Path $zipPath
("SHA256  " + $zipHash + "  " + [System.IO.Path]::GetFileName($zipPath)) |
    Set-Content -LiteralPath ($zipPath + ".sha256.txt") -Encoding UTF8

Write-Log "ZIP created: $zipPath"
Write-Log "ZIP SHA256: $zipHash"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "COLLECTOR COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host $zipPath
Write-Host ""
exit 0
