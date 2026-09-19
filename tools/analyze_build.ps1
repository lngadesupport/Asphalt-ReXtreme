param(
    [Parameter(Mandatory=$true)]
    [string]$GameDir,

    [string]$OutDir = ".\\analysis-output"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path $GameDir).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out = (Resolve-Path $OutDir).Path

$summary = New-Object System.Collections.Generic.List[string]
$summary.Add("Asphalt ReXtreme build analysis")
$summary.Add("Root: $root")
$summary.Add("Generated: $(Get-Date -Format o)")
$summary.Add("")

$manifest = Join-Path $root "AppxManifest.xml"
if (Test-Path $manifest) {
    try {
        [xml]$xml = Get-Content -LiteralPath $manifest -Raw
        $identity = $xml.Package.Identity
        $summary.Add("Package identity:")
        $summary.Add("  Name: $($identity.Name)")
        $summary.Add("  Version: $($identity.Version)")
        $summary.Add("  ProcessorArchitecture: $($identity.ProcessorArchitecture)")
        $summary.Add("  Publisher: $($identity.Publisher)")
        $summary.Add("")

        $summary.Add("Applications:")
        foreach ($app in $xml.Package.Applications.Application) {
            $summary.Add("  Id=$($app.Id) Executable=$($app.Executable) EntryPoint=$($app.EntryPoint)")
        }
        $summary.Add("")
    }
    catch {
        $summary.Add("Manifest parse error: $($_.Exception.Message)")
        $summary.Add("")
    }
} else {
    $summary.Add("AppxManifest.xml not found at package root.")
    $summary.Add("")
}

$files = Get-ChildItem -LiteralPath $root -Recurse -File

$inventory = foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length).TrimStart("\\")
    [pscustomobject]@{
        Path = $rel
        Size = $f.Length
        Extension = $f.Extension.ToLowerInvariant()
    }
}
$inventory | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out "inventory.csv")

$summary.Add("Files: $($files.Count)")
$summary.Add("")

$summary.Add("Executable / DLL hashes:")
$binaryHashes = foreach ($f in $files | Where-Object { $_.Extension.ToLowerInvariant() -in @(".exe", ".dll") }) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName).Hash.ToLowerInvariant()
    $rel = $f.FullName.Substring($root.Length).TrimStart("\\")
    $summary.Add("  $hash  $rel")
    [pscustomobject]@{
        Path = $rel
        Size = $f.Length
        SHA256 = $hash
    }
}
$binaryHashes | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out "binary-hashes.csv")
$summary.Add("")

$keywords = @(
    "gameloft", "http://", "https://", "server", "online", "offline",
    "advert", "rewarded", "telemetry", "analytics", "purchase", "store",
    "currency", "credit", "token", "coin", "upgrade", "unlock",
    "fov", "fieldofview", "framerate", "fps", "vsync", "resolution"
)

$textHits = New-Object System.Collections.Generic.List[string]
foreach ($f in $files | Where-Object { $_.Extension.ToLowerInvariant() -in @(".json", ".xml", ".ini", ".cfg", ".txt") }) {
    try {
        $content = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop
        foreach ($k in $keywords) {
            if ($content.IndexOf($k, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $rel = $f.FullName.Substring($root.Length).TrimStart("\\")
                $textHits.Add($rel + [char]9 + $k)
            }
        }
    } catch {}
}
$textHits | Sort-Object -Unique | Set-Content -Encoding UTF8 (Join-Path $out "keyword-hits.txt")

$summary | Set-Content -Encoding UTF8 (Join-Path $out "summary.txt")

Write-Host ""
Write-Host "Analysis complete." -ForegroundColor Green
Write-Host "Output: $out"
Write-Host "  summary.txt"
Write-Host "  inventory.csv"
Write-Host "  binary-hashes.csv"
Write-Host "  keyword-hits.txt"
