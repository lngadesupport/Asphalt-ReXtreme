param([string]$GameRoot = "")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $GameRoot = (Get-Location).Path
}
$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$Exe = Join-Path $GameRoot "AMS.exe"

if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw "AMS.exe nao encontrado em: $GameRoot"
}

$required = @(
    "WCPToolkit.dll",
    "InAppPurchaseComponentW8.dll",
    "IGPLib_x86.dll",
    "vccorlib120_app.dll",
    "msvcp120_app.dll",
    "msvcr120_app.dll",
    "App.xbf",
    "DirectXPage.xbf",
    "resources.pri"
)

$missing = @()
foreach ($rel in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $GameRoot $rel))) {
        $missing += $rel
    }
}
if ($missing.Count -gt 0) {
    throw ("Runtime minimo incompleto: " + ($missing -join ", "))
}

$logs = Join-Path $GameRoot "_campaign_crash_probe"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $logs ("run-" + $stamp)
$dumpDir = Join-Path $runDir "dumps"
New-Item -ItemType Directory -Force -Path $dumpDir | Out-Null

$werExe = "HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\AMS.exe"

try {
    New-Item -Path $werExe -Force | Out-Null
    New-ItemProperty -Path $werExe -Name "DumpFolder" -PropertyType ExpandString -Value $dumpDir -Force | Out-Null
    New-ItemProperty -Path $werExe -Name "DumpCount" -PropertyType DWord -Value 3 -Force | Out-Null
    New-ItemProperty -Path $werExe -Name "DumpType" -PropertyType DWord -Value 2 -Force | Out-Null

    $start = Get-Date
    Write-Host "Starting AMS.exe..."
    $proc = Start-Process -FilePath $Exe -WorkingDirectory $GameRoot -PassThru
    Write-Host ("PID: " + $proc.Id)
    Wait-Process -Id $proc.Id
    $proc.Refresh()
    $exitCode = $proc.ExitCode

    Start-Sleep -Seconds 3

    $summary = New-Object System.Collections.Generic.List[string]
    $summary.Add("Asphalt ReXtreme Campaign Crash Probe")
    $summary.Add("Generated: $(Get-Date -Format o)")
    $summary.Add("PID: $($proc.Id)")
    $summary.Add("ExitCodeDecimal: $exitCode")
    $summary.Add(("ExitCodeHex: 0x{0:X8}" -f ([uint32]$exitCode)))
    $summary.Add("")

    $dumpFiles = @(Get-ChildItem -LiteralPath $dumpDir -File -Filter "*.dmp" -ErrorAction SilentlyContinue)
    $summary.Add("DumpCount: $($dumpFiles.Count)")
    foreach ($d in $dumpFiles) {
        $summary.Add("Dump: $($d.Name) ($($d.Length) bytes)")
    }
    $summary.Add("")

    foreach ($log in @(
        "Application",
        "Microsoft-Windows-AppModel-Runtime/Admin",
        "Microsoft-Windows-TWinUI/Operational"
    )) {
        $summary.Add("===== $log =====")
        try {
            $events = Get-WinEvent -FilterHashtable @{
                LogName = $log
                StartTime = $start.AddSeconds(-2)
                EndTime = (Get-Date).AddSeconds(5)
            } -ErrorAction Stop | Where-Object {
                ([string]$_.Message) -match '(?i)AMS\.exe|Asphalt|ReXtreme|A278AB0D\.AsphaltXtreme'
            } | Select-Object -First 80

            if (-not $events) {
                $summary.Add("(no matching events)")
            } else {
                foreach ($e in $events) {
                    $summary.Add(
                        ("[{0}] Id={1} Provider={2}" -f
                            $e.TimeCreated.ToString("o"),
                            $e.Id,
                            $e.ProviderName
                        )
                    )
                    $summary.Add([string]$e.Message)
                    $summary.Add("")
                }
            }
        } catch {
            $summary.Add("Log read error: $($_.Exception.Message)")
        }
        $summary.Add("")
    }

    $summary.Add("===== BUILD HASHES =====")
    foreach ($rel in @(
        "AMS.exe",
        "WCPToolkit.dll",
        "InAppPurchaseComponentW8.dll",
        "IGPLib_x86.dll"
    )) {
        $p = Join-Path $GameRoot $rel
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
        $size = (Get-Item -LiteralPath $p).Length
        $summary.Add("$rel | $size | $hash")
    }

    $summaryPath = Join-Path $runDir "CRASH-SUMMARY.txt"
    $summary | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipPath = Join-Path $logs ("AMS-Crash-Probe-" + $stamp + ".zip")
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $runDir,
        $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    Write-Host ""
    Write-Host "CRASH PROBE COMPLETE" -ForegroundColor Green
    Write-Host "Exit code: $exitCode"
    Write-Host "Dump files: $($dumpFiles.Count)"
    Write-Host ""
    Write-Host "Envie este ZIP:"
    Write-Host "  $zipPath"
}
finally {
    if (Test-Path -LiteralPath $werExe) {
        Remove-Item -LiteralPath $werExe -Recurse -Force -ErrorAction SilentlyContinue
    }
}
