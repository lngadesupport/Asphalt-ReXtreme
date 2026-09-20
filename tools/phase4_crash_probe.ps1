param(
    [string]$GameRoot = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$exe = Join-Path $GameRoot "AMS.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "AMS.exe not found: $exe"
}

$logDir = Join-Path $GameRoot "_PHASE4_CRASH_PROBE"
if (Test-Path -LiteralPath $logDir) {
    Remove-Item -LiteralPath $logDir -Recurse -Force
}
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$start = Get-Date
Write-Host "Starting AMS.exe..." -ForegroundColor Cyan
$p = Start-Process -FilePath $exe -WorkingDirectory $GameRoot -PassThru
$p.WaitForExit()
$end = Get-Date
$exit = [int32]$p.ExitCode
$exitHex = ("0x{0:X8}" -f [BitConverter]::ToUInt32([BitConverter]::GetBytes($exit), 0))

@(
    "Start=$($start.ToString('o'))",
    "End=$($end.ToString('o'))",
    "ExitCode=$exit",
    "ExitHex=$exitHex"
) | Set-Content -LiteralPath (Join-Path $logDir "exit.txt") -Encoding UTF8

Start-Sleep -Seconds 2

$events = @()
try {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName = "Application"
        StartTime = $start.AddSeconds(-3)
        EndTime = (Get-Date).AddSeconds(2)
    } -ErrorAction Stop | Where-Object {
        $_.Id -in 1000,1001,1026 -or
        $_.ProviderName -match "Application Error|Windows Error Reporting|Application Hang"
    } | Where-Object {
        $_.Message -match "(?i)AMS\.exe|Asphalt"
    })
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $logDir "application-events-error.txt") -Encoding UTF8
}

if ($events.Count -gt 0) {
    $events | ForEach-Object {
        "TimeCreated: $($_.TimeCreated)"
        "Provider: $($_.ProviderName)"
        "Id: $($_.Id)"
        "Level: $($_.LevelDisplayName)"
        "Message:"
        $_.Message
        "------------------------------------------------------------"
    } | Set-Content -LiteralPath (Join-Path $logDir "application-events.txt") -Encoding UTF8
}

$werRoots = @(
    (Join-Path $env:LOCALAPPDATA "Microsoft\Windows\WER\ReportArchive"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\Windows\WER\ReportQueue")
)

$copiedWer = @()
foreach ($root in $werRoots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    $dirs = @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $start.AddMinutes(-1) } |
        Sort-Object LastWriteTime -Descending)
    foreach ($d in $dirs) {
        $werFiles = @(Get-ChildItem -LiteralPath $d.FullName -File -Filter "*.wer" -ErrorAction SilentlyContinue)
        foreach ($wf in $werFiles) {
            $txt = Get-Content -LiteralPath $wf.FullName -Raw -ErrorAction SilentlyContinue
            if ($txt -match "(?i)AMS\.exe|Asphalt") {
                $safe = ($d.Name -replace '[^A-Za-z0-9._-]', '_')
                $dest = Join-Path $logDir ("WER-" + $safe + ".wer")
                Copy-Item -LiteralPath $wf.FullName -Destination $dest -Force
                $copiedWer += $dest
            }
        }
    }
}

$summary = [ordered]@{
    Start = $start.ToString("o")
    End = $end.ToString("o")
    ExitCode = $exit
    ExitHex = $exitHex
    ApplicationEventCount = $events.Count
    WERFilesCopied = $copiedWer.Count
}
$summary | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $logDir "summary.json") -Encoding UTF8

$zip = Join-Path $GameRoot "PHASE4-CRASH-PROBE.zip"
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -Path (Join-Path $logDir "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 4 CRASH PROBE COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Exit: {0} ({1})" -f $exit, $exitHex)
Write-Host ("Application events: {0}" -f $events.Count)
Write-Host ("WER reports copied: {0}" -f $copiedWer.Count)
Write-Host ("ZIP: {0}" -f $zip)
Write-Host ""
