param([string]$ProjectRoot = "")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = $ProjectRoot.Trim().Trim('"').TrimEnd("\")
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$pkgRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$ams = Join-Path $pkgRoot "AMS.exe"
$igp = Join-Path $pkgRoot "IGPLib_x86.dll"
$phase2 = Join-Path $ProjectRoot "_AMS_PHASE2\AMS.exe"
$cleanIgp = Join-Path $ProjectRoot "CLEAN-1.7.3.8-EXTRACTED\Game\IGPLib_x86.dll"
$coreIgp = Join-Path $ProjectRoot "prebuilt\campaign-core\IGPLib_x86.dll"
$python = Join-Path $ProjectRoot "runtime\python312-x86\python.exe"
$manifest = Join-Path $pkgRoot "AppxManifest.xml"

foreach ($p in @($ams,$igp,$phase2,$cleanIgp,$coreIgp,$python,$manifest)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "Arquivo necessario ausente: $p"
    }
}

[xml]$mx = Get-Content -LiteralPath $manifest -Raw
$name = [string]$mx.Package.Identity.Name
$app = $mx.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
$appId = [string]$app.Id
$expected = [IO.Path]::GetFullPath($pkgRoot).TrimEnd("\")
$pkg = Get-AppxPackage -Name $name -ErrorAction Stop |
    Where-Object {
        $_.InstallLocation -and
        [StringComparer]::OrdinalIgnoreCase.Equals(
            [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd("\"),
            $expected
        )
    } | Sort-Object Version -Descending | Select-Object -First 1
if (-not $pkg) { throw "Pacote beta registrado em outra pasta ou ausente." }

$root = Join-Path $ProjectRoot "_BETA_DIAGNOSTICS"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$run = Join-Path $root ("startup-bisect-" + $stamp)
New-Item -ItemType Directory -Force -Path $run | Out-Null

$originalAms = Join-Path $run "AMS.final.bin"
$originalIgp = Join-Path $run "IGPLib.final.bin"
Copy-Item -LiteralPath $ams -Destination $originalAms -Force
Copy-Item -LiteralPath $igp -Destination $originalIgp -Force

$campaignState = Join-Path $env:LOCALAPPDATA ("Packages\" + $pkg.PackageFamilyName + "\LocalState\CampaignEdition")
$campaignBackup = Join-Path $run "CampaignEdition.before"
$campaignExisted = Test-Path -LiteralPath $campaignState -PathType Container
if ($campaignExisted) {
    Copy-Item -LiteralPath $campaignState -Destination $campaignBackup -Recurse -Force
}

$results = New-Object System.Collections.Generic.List[object]

function Stop-Ams {
    Get-Process -Name "AMS" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 700
}

function Hash-File([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Reset-Phase2([bool]$UseCampaignCore) {
    Stop-Ams
    Copy-Item -LiteralPath $phase2 -Destination $ams -Force
    if ($UseCampaignCore) {
        Copy-Item -LiteralPath $coreIgp -Destination $igp -Force
    } else {
        Copy-Item -LiteralPath $cleanIgp -Destination $igp -Force
    }
}

function Apply-Tool([string]$Tool) {
    $path = Join-Path $ProjectRoot ("tools\" + $Tool)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Tool ausente: $path"
    }
    & $python $path --project-root $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "$Tool falhou com codigo $LASTEXITCODE"
    }
}

function Get-CrashEvent([datetime]$Start, [datetime]$End) {
    try {
        return Get-WinEvent -FilterHashtable @{
            LogName = "Application"
            Id = 1000
            StartTime = $Start.AddSeconds(-1)
            EndTime = $End.AddSeconds(2)
        } -ErrorAction Stop | Where-Object {
            ([string]$_.Message) -match '(?i)AMS\.exe'
        } | Sort-Object TimeCreated -Descending | Select-Object -First 1
    } catch {
        return $null
    }
}

function Run-Stage([string]$Stage) {
    Stop-Ams
    $start = Get-Date
    Write-Host ""
    Write-Host ("[BISECT] " + $Stage) -ForegroundColor Cyan
    Write-Host ("  AMS: " + (Hash-File $ams))
    Write-Host ("  IGP: " + (Hash-File $igp))

    Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!" + $appId)

    $proc = $null
    $detectDeadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $detectDeadline -and -not $proc) {
        Start-Sleep -Milliseconds 200
        $proc = Get-Process -Name "AMS" -ErrorAction SilentlyContinue |
            Sort-Object StartTime -Descending | Select-Object -First 1
    }

    $base = $null
    $pidValue = $null
    if ($proc) {
        $pidValue = $proc.Id
        try {
            $base = ("0x{0:X8}" -f $proc.MainModule.BaseAddress.ToInt64())
        } catch {}
    }

    if (-not $proc) {
        $end = Get-Date
        $ev = Get-CrashEvent $start $end
        return [ordered]@{
            stage=$Stage; result="NO_PROCESS"; pid=$null; image_base=$null;
            seconds=[math]::Round(($end-$start).TotalSeconds,3);
            ams_sha256=(Hash-File $ams); igp_sha256=(Hash-File $igp);
            event=if($ev){[string]$ev.Message}else{$null}
        }
    }

    $survived = $true
    $deadline = (Get-Date).AddSeconds(12)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
            $survived = $false
            break
        }
    }

    $end = Get-Date
    if ($survived) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        $result = "SURVIVED_12S"
    } else {
        Start-Sleep -Seconds 2
        $result = "EXITED_EARLY"
    }

    $ev = Get-CrashEvent $start (Get-Date)
    if ($ev) {
        $result = "CRASH"
    }

    return [ordered]@{
        stage=$Stage; result=$result; pid=$pidValue; image_base=$base;
        seconds=[math]::Round(($end-$start).TotalSeconds,3);
        ams_sha256=(Hash-File $ams); igp_sha256=(Hash-File $igp);
        event=if($ev){[string]$ev.Message}else{$null}
    }
}

function Record-Stage([string]$Name) {
    $r = Run-Stage $Name
    $results.Add([pscustomobject]$r) | Out-Null
    Write-Host ("  Resultado: " + $r.result)
    if ($r.image_base) { Write-Host ("  ImageBase: " + $r.image_base) }
    if ($r.event) {
        $m = [regex]::Match($r.event, 'Código de exceção:\s*(0x[0-9a-fA-F]+)')
        $f = [regex]::Match($r.event, 'Deslocamento da falha:\s*(0x[0-9a-fA-F]+)')
        if ($m.Success) { Write-Host ("  Exception: " + $m.Groups[1].Value) }
        if ($f.Success) { Write-Host ("  Fault: " + $f.Groups[1].Value) }
    }
    return ($r.result -eq "SURVIVED_12S")
}

$failedBoundary = $null

try {
    Reset-Phase2 $false
    if (-not (Record-Stage "phase2-original-igp")) {
        $failedBoundary = "Phase2/original IGPLib"
    }

    if (-not $failedBoundary) {
        Reset-Phase2 $true
        if (-not (Record-Stage "phase2-campaign-core")) {
            $failedBoundary = "Campaign Core / IGPLib replacement"
        }
    }

    if (-not $failedBoundary) {
        Reset-Phase2 $true
        Apply-Tool "campaign_garage_v2.py"
        if (-not (Record-Stage "garage")) {
            $failedBoundary = "Campaign Garage v2"
        }
    }

    if (-not $failedBoundary) {
        Reset-Phase2 $true
        Apply-Tool "campaign_garage_v2.py"
        Apply-Tool "campaign_career_adapter_v3.py"
        if (-not (Record-Stage "career")) {
            $failedBoundary = "Career Adapter v3"
        }
    }

    if (-not $failedBoundary) {
        Reset-Phase2 $true
        Apply-Tool "campaign_garage_v2.py"
        Apply-Tool "campaign_career_adapter_v3.py"
        Apply-Tool "campaign_upgrade_adapter_v1.py"
        if (-not (Record-Stage "upgrade")) {
            $failedBoundary = "Upgrade Adapter v1"
        }
    }

    if (-not $failedBoundary) {
        Reset-Phase2 $true
        Apply-Tool "campaign_garage_v2.py"
        Apply-Tool "campaign_career_adapter_v3.py"
        Apply-Tool "campaign_upgrade_adapter_v1.py"
        Apply-Tool "campaign_store_adapter_v1.py"
        if (-not (Record-Stage "store")) {
            $failedBoundary = "Store Adapter v1"
        }
    }
}
finally {
    Stop-Ams
    Copy-Item -LiteralPath $originalAms -Destination $ams -Force
    Copy-Item -LiteralPath $originalIgp -Destination $igp -Force

    if (Test-Path -LiteralPath $campaignState -PathType Container) {
        Remove-Item -LiteralPath $campaignState -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($campaignExisted -and (Test-Path -LiteralPath $campaignBackup -PathType Container)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $campaignState -Parent) | Out-Null
        Copy-Item -LiteralPath $campaignBackup -Destination $campaignState -Recurse -Force
    }
}

$report = [ordered]@{
    generated=(Get-Date).ToString("o")
    package=$pkg.PackageFullName
    failed_boundary=$failedBoundary
    current_build_restored=$true
    campaign_save_restored=$true
    results=@($results)
}
$json = Join-Path $run "STARTUP-BISECT.json"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $json -Encoding UTF8

$txt = Join-Path $run "STARTUP-BISECT.txt"
@(
    "Asphalt ReXtreme Beta Startup Bisect",
    "Generated: $($report.generated)",
    "FailedBoundary: $failedBoundary",
    ""
) | Set-Content -LiteralPath $txt -Encoding UTF8
foreach ($r in $results) {
    Add-Content -LiteralPath $txt -Encoding UTF8 -Value (
        "{0} | {1} | {2}s | base={3} | AMS={4} | IGP={5}" -f
        $r.stage,$r.result,$r.seconds,$r.image_base,$r.ams_sha256,$r.igp_sha256
    )
    if ($r.event) {
        Add-Content -LiteralPath $txt -Encoding UTF8 -Value $r.event
        Add-Content -LiteralPath $txt -Encoding UTF8 -Value ""
    }
}

$zip = Join-Path $root ("BETA-STARTUP-BISECT-" + $stamp + ".zip")
Compress-Archive -Path (Join-Path $run "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " BETA STARTUP BISECT COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Primeiro limite com falha: " + $(if($failedBoundary){$failedBoundary}else{"nenhum nos 6 estagios"}))
Write-Host ("Build final restaurado: sim")
Write-Host ("ZIP: " + $zip)
Write-Host ""
Write-Host "Envie esse ZIP."
