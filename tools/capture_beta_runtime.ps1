param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$PackageRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$ManifestPath = Join-Path $PackageRoot "AppxManifest.xml"
$AmsPath = Join-Path $PackageRoot "AMS.exe"

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "_PACKAGE_PHASE5\AppxManifest.xml nao encontrado."
}
if (-not (Test-Path -LiteralPath $AmsPath -PathType Leaf)) {
    throw "_PACKAGE_PHASE5\AMS.exe nao encontrado."
}

[xml]$manifest = Get-Content -LiteralPath $ManifestPath -Raw
$packageName = [string]$manifest.Package.Identity.Name
$appNode = $manifest.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId = [string]$appNode.Id

$expected = [IO.Path]::GetFullPath($PackageRoot).TrimEnd("\")
$pkg = Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue |
    Where-Object {
        $_.InstallLocation -and
        [StringComparer]::OrdinalIgnoreCase.Equals(
            [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd("\"),
            $expected
        )
    } |
    Sort-Object Version -Descending |
    Select-Object -First 1

if (-not $pkg) {
    throw "O pacote beta nao esta registrado a partir de _PACKAGE_PHASE5. Rode INSTALL-BETA.cmd."
}

$root = Join-Path $ProjectRoot "_BETA_DIAGNOSTICS"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$run = Join-Path $root ("run-" + $stamp)
$dumpDir = Join-Path $run "dumps"
New-Item -ItemType Directory -Force -Path $dumpDir | Out-Null

$summaryPath = Join-Path $run "RUNTIME-SUMMARY.txt"
$eventPath = Join-Path $run "WINDOWS-EVENTS.txt"
$hashPath = Join-Path $run "BUILD-HASHES.txt"
$werKey = "HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\AMS.exe"

function Add-Line([string]$Path, [string]$Text = "") {
    Add-Content -LiteralPath $Path -Value $Text -Encoding UTF8
}

function Hex-Exit([int]$Code) {
    $u = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$Code), 0)
    return ("0x{0:X8}" -f $u)
}

try {
    New-Item -Path $werKey -Force | Out-Null
    New-ItemProperty -Path $werKey -Name "DumpFolder" -PropertyType ExpandString -Value $dumpDir -Force | Out-Null
    New-ItemProperty -Path $werKey -Name "DumpCount" -PropertyType DWord -Value 2 -Force | Out-Null
    # DumpType 1 = minidump. Small enough to share and enough for exception/module triage.
    New-ItemProperty -Path $werKey -Name "DumpType" -PropertyType DWord -Value 1 -Force | Out-Null

    "Asphalt ReXtreme Public Beta Runtime Probe" | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    Add-Line $summaryPath ("Generated: " + (Get-Date).ToString("o"))
    Add-Line $summaryPath ("PackageFullName: " + $pkg.PackageFullName)
    Add-Line $summaryPath ("PackageFamilyName: " + $pkg.PackageFamilyName)
    Add-Line $summaryPath ("InstallLocation: " + $pkg.InstallLocation)
    Add-Line $summaryPath ("ApplicationId: " + $appId)
    Add-Line $summaryPath ""

    $files = @(
        "AMS.exe",
        "IGPLib_x86.dll",
        "CampaignCatalog.dat",
        "CampaignEvents.dat",
        "CampaignUpgrades.dat",
        "CampaignUpgradeUiMap.dat",
        "CampaignStore.dat"
    )
    foreach ($rel in $files) {
        $p = Join-Path $PackageRoot $rel
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
            $size = (Get-Item -LiteralPath $p).Length
            Add-Line $hashPath ("$rel | $size | $h")
        } else {
            Add-Line $hashPath ("$rel | MISSING")
        }
    }

    $finalStatus = Join-Path $ProjectRoot "_TRACE_MONTAR\CAMPAIGN-FINAL-STATUS.json"
    if (Test-Path -LiteralPath $finalStatus) {
        Copy-Item -LiteralPath $finalStatus -Destination (Join-Path $run "CAMPAIGN-FINAL-STATUS.json") -Force
    }

    Get-Process -Name "AMS" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue

    $start = Get-Date
    Add-Line $summaryPath ("LaunchTime: " + $start.ToString("o"))
    Add-Line $summaryPath "LaunchMode: shell:AppsFolder"

    Write-Host "[ReXtreme Beta] Iniciando o jogo pelo registro UWP..." -ForegroundColor Cyan
    Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!" + $appId)

    $proc = $null
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline -and -not $proc) {
        Start-Sleep -Milliseconds 250
        $proc = Get-Process -Name "AMS" -ErrorAction SilentlyContinue |
            Sort-Object StartTime -Descending |
            Select-Object -First 1
    }

    if (-not $proc) {
        Add-Line $summaryPath "ProcessDetected: false"
        Write-Host "[AVISO] AMS.exe nao apareceu em 20 segundos." -ForegroundColor Yellow
    } else {
        Add-Line $summaryPath "ProcessDetected: true"
        Add-Line $summaryPath ("PID: " + $proc.Id)
        Write-Host ("[ReXtreme Beta] AMS.exe PID " + $proc.Id + " detectado. Aguarde ele fechar...") -ForegroundColor Cyan

        try {
            Wait-Process -Id $proc.Id -ErrorAction Stop
            $proc.Refresh()
            $exit = [int32]$proc.ExitCode
            Add-Line $summaryPath ("ExitCodeDecimal: " + $exit)
            Add-Line $summaryPath ("ExitCodeHex: " + (Hex-Exit $exit))
            Write-Host ("[ReXtreme Beta] Exit code: " + (Hex-Exit $exit))
        } catch {
            Add-Line $summaryPath ("Wait/ExitCode error: " + $_.Exception.Message)
        }
    }

    Start-Sleep -Seconds 3
    $end = Get-Date
    Add-Line $summaryPath ("CaptureEnd: " + $end.ToString("o"))

    $dumps = @(Get-ChildItem -LiteralPath $dumpDir -File -Filter "*.dmp" -ErrorAction SilentlyContinue)
    Add-Line $summaryPath ("DumpCount: " + $dumps.Count)
    foreach ($d in $dumps) {
        Add-Line $summaryPath ("Dump: " + $d.Name + " | " + $d.Length + " bytes")
    }

    "Asphalt ReXtreme Public Beta - Windows runtime events" |
        Set-Content -LiteralPath $eventPath -Encoding UTF8

    foreach ($logName in @(
        "Application",
        "Microsoft-Windows-AppModel-Runtime/Admin",
        "Microsoft-Windows-TWinUI/Operational"
    )) {
        Add-Line $eventPath ""
        Add-Line $eventPath ("===== " + $logName + " =====")
        try {
            $events = @(Get-WinEvent -FilterHashtable @{
                LogName = $logName
                StartTime = $start.AddSeconds(-3)
                EndTime = $end.AddSeconds(3)
            } -ErrorAction Stop | Where-Object {
                ([string]$_.Message) -match '(?i)AMS\.exe|Asphalt|A278AB0D\.AsphaltXtreme|IGPLib_x86'
            } | Select-Object -First 100)

            if ($events.Count -eq 0) {
                Add-Line $eventPath "(no matching events)"
            } else {
                foreach ($e in $events) {
                    Add-Line $eventPath ("[{0}] Id={1} Provider={2}" -f $e.TimeCreated.ToString("o"), $e.Id, $e.ProviderName)
                    Add-Line $eventPath ([string]$e.Message)
                    Add-Line $eventPath ""
                }
            }
        } catch {
            Add-Line $eventPath ("Log read error: " + $_.Exception.Message)
        }
    }

    $zip = Join-Path $root ("BETA-RUNTIME-PROBE-" + $stamp + ".zip")
    if (Test-Path -LiteralPath $zip) {
        Remove-Item -LiteralPath $zip -Force
    }
    Compress-Archive -Path (Join-Path $run "*") -DestinationPath $zip -Force

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " BETA RUNTIME PROBE COMPLETE" -ForegroundColor Green
    Write-Host "============================================================"
    Write-Host ("Resumo: " + $summaryPath)
    Write-Host ("Eventos: " + $eventPath)
    Write-Host ("ZIP:     " + $zip)
    Write-Host ""
    Write-Host "Envie o ZIP acima para diagnosticar o fechamento."
}
finally {
    if (Test-Path -LiteralPath $werKey) {
        Remove-Item -LiteralPath $werKey -Recurse -Force -ErrorAction SilentlyContinue
    }
}
