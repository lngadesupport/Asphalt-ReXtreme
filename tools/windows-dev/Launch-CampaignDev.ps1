param(
    [switch]$CollectDiagnostics,
    [string]$GameRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $Candidate = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    if (-not (Test-Path (Join-Path $Candidate "AppxManifest.xml"))) {
        throw "Could not auto-detect the game folder. Pass -GameRoot <folder>."
    }
    $GameRoot = $Candidate
} else {
    $GameRoot = (Resolve-Path $GameRoot).Path
}

$PackageName = "A278AB0D.AsphaltXtreme"
$LogDir = Join-Path $GameRoot "_campaign_logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$pkg = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue |
    Where-Object {
        $_.InstallLocation -and
        [System.StringComparer]::OrdinalIgnoreCase.Equals(
            [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd('\'),
            [IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
        )
    } |
    Sort-Object Version -Descending |
    Select-Object -First 1

if (-not $pkg) {
    throw "Campaign development layout is not registered. Run Register-CampaignDev.ps1 first."
}

$start = Get-Date
$aumid = "$($pkg.PackageFamilyName)!App"

Write-Host "Launching $aumid"
Start-Process "explorer.exe" -ArgumentList "shell:AppsFolder\$aumid"

if (-not $CollectDiagnostics) {
    exit 0
}

Write-Host "Collecting immediate AppModel diagnostics..."
Start-Sleep -Seconds 5

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$summary = Join-Path $LogDir "launch-$stamp.txt"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("Asphalt ReXtreme Campaign launch diagnostics")
$lines.Add("Started: $($start.ToString('o'))")
$lines.Add("Package: $($pkg.PackageFullName)")
$lines.Add("Family: $($pkg.PackageFamilyName)")
$lines.Add("InstallLocation: $($pkg.InstallLocation)")
$lines.Add("")

$proc = Get-Process -Name "AMS" -ErrorAction SilentlyContinue
if ($proc) {
    $lines.Add("AMS.exe process detected: YES")
    foreach ($p in @($proc)) {
        $lines.Add("  PID=$($p.Id) StartTime=$($p.StartTime)")
    }
} else {
    $lines.Add("AMS.exe process detected after 5 seconds: NO")
}
$lines.Add("")

$logs = @(
    "Microsoft-Windows-AppModel-Runtime/Admin",
    "Microsoft-Windows-TWinUI/Operational"
)

foreach ($log in $logs) {
    $lines.Add("===== $log =====")
    try {
        $events = Get-WinEvent -FilterHashtable @{
            LogName = $log
            StartTime = $start.AddSeconds(-2)
        } -ErrorAction Stop | Select-Object -First 80
        if (-not $events) {
            $lines.Add("(no events)")
        } else {
            foreach ($e in $events) {
                $msg = $e.Message.Replace([Environment]::NewLine, " ")
                $lines.Add("[$($e.TimeCreated.ToString('o'))] Id=$($e.Id) Level=$($e.LevelDisplayName)")
                $lines.Add($msg)
                $lines.Add("")
            }
        }
    } catch {
        $lines.Add("Could not read log: $($_.Exception.Message)")
    }
    $lines.Add("")
}

$lines | Set-Content -Path $summary -Encoding UTF8
Write-Host "Diagnostics saved to: $summary"
