param(
    [string]$SourceDir = ".",
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path

# Check effective AppX policies as well as AppModelUnlock.
$policyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Appx"
$policyTrusted = $null
$policyDev = $null
try {
    $p = Get-ItemProperty -Path $policyPath -ErrorAction Stop
    $policyTrusted = $p.AllowAllTrustedApps
    $policyDev = $p.AllowDevelopmentWithoutDevLicense
} catch {}

if (($policyTrusted -eq 0) -or ($policyDev -eq 0)) {
    Write-Host ""
    Write-Host "AppX Group Policy explicitly denies sideload/developer registration." -ForegroundColor Red
    Write-Host "AllowAllTrustedApps=$policyTrusted"
    Write-Host "AllowDevelopmentWithoutDevLicense=$policyDev"
    throw "Windows AppX policy blocks Add-AppxPackage -Register (0x80073CFF)."
}

# Loose-file registration (-Register) requires Windows developer mode.
$devMode = 0
try {
    $unlock = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -ErrorAction Stop
    if ($null -ne $unlock.AllowDevelopmentWithoutDevLicense) {
        $devMode = [int]$unlock.AllowDevelopmentWithoutDevLicense
    }
} catch {
    $devMode = 0
}
if ($devMode -ne 1) {
    Write-Host ""
    Write-Host "Developer Mode is not enabled." -ForegroundColor Yellow
    Write-Host "Windows 10: Settings > Update & Security > For developers > Developer mode"
    Write-Host ""
    throw "Package Phase 5 requires Windows Developer Mode for Add-AppxPackage -Register."
}
$ExpectedAMS = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

function Get-PeDllCharacteristics([string]$Path) {
    [byte[]]$d = [IO.File]::ReadAllBytes($Path)
    if ($d.Length -lt 0x200 -or $d[0] -ne 0x4D -or $d[1] -ne 0x5A) { throw "Not a valid PE: $Path" }
    $pe = [BitConverter]::ToInt32($d,0x3C)
    if ($d[$pe] -ne 0x50 -or $d[$pe+1] -ne 0x45) { throw "PE signature missing: $Path" }
    $opt = $pe + 24
    if ([BitConverter]::ToUInt16($d,$opt) -ne 0x10B) { throw "Expected x86 PE32: $Path" }
    return [BitConverter]::ToUInt16($d,$opt+0x46)
}

$cleanBase = Join-Path $SourceDir "CLEAN-1.7.3.8-EXTRACTED"
$cleanAms = @(Get-ChildItem -LiteralPath $cleanBase -Recurse -File -Filter "AMS.exe")
if ($cleanAms.Count -ne 1) { throw "Expected exactly one clean AMS.exe under $cleanBase; found $($cleanAms.Count)." }
$cleanGameRoot = $cleanAms[0].Directory.FullName

$phase2 = Join-Path $SourceDir "_AMS_PHASE2\AMS.exe"
if (-not (Test-Path -LiteralPath $phase2 -PathType Leaf)) { throw "Missing Phase 2 AMS.exe: $phase2" }

$phase2Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $phase2).Hash.ToLowerInvariant()
if ($phase2Hash -ne $ExpectedAMS) { throw "Unexpected Phase 2 AMS hash: $phase2Hash" }

$dllChars = Get-PeDllCharacteristics $phase2
if (($dllChars -band 0x1000) -eq 0) {
    throw ("Phase 2 AMS no longer has AppContainer set (DllCharacteristics=0x{0:X4})." -f $dllChars)
}

$out = Join-Path $SourceDir "_PACKAGE_PHASE5"
if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
Write-Host "Copying pristine packaged tree..." -ForegroundColor Cyan
Copy-Item -LiteralPath $cleanGameRoot -Destination $out -Recurse -Force

Write-Host "Overlaying verified Phase 2 AMS (AppContainer preserved)..." -ForegroundColor Cyan
Copy-Item -LiteralPath $phase2 -Destination (Join-Path $out "AMS.exe") -Force

$manifestPath = Join-Path $out "AppxManifest.xml"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "AppxManifest.xml missing from Phase 5 tree." }

[xml]$manifest = Get-Content -LiteralPath $manifestPath -Raw
$ns = New-Object System.Xml.XmlNamespaceManager($manifest.NameTable)
$ns.AddNamespace("f","http://schemas.microsoft.com/appx/manifest/foundation/windows10")
$identity = $manifest.Package.Identity
$packageName = [string]$identity.Name
$packageVersion = [string]$identity.Version
$packageArch = [string]$identity.ProcessorArchitecture

$appNode = $manifest.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
if (-not $appNode) { throw "No Application entry found in AppxManifest.xml." }
$appId = [string]$appNode.Id
if ([string]::IsNullOrWhiteSpace($appId)) { throw "Application Id is empty in manifest." }

Write-Host ""
Write-Host "Package identity:" -ForegroundColor Cyan
Write-Host "  Name:    $packageName"
Write-Host "  Version: $packageVersion"
Write-Host "  Arch:    $packageArch"
Write-Host "  AppId:   $appId"

# Register VCLibs dependency if it is not already registered.
$vclib = Get-AppxPackage -Name "Microsoft.VCLibs.120.00" -ErrorAction SilentlyContinue |
    Where-Object { $_.Architecture -eq "X86" -or $_.Architecture -eq "Neutral" } |
    Select-Object -First 1

if (-not $vclib) {
    Write-Host ""
    Write-Host "Microsoft.VCLibs.120.00 x86 is not registered. Looking for local dependency..." -ForegroundColor Yellow

    $vclibFolder = Join-Path $SourceDir "VCLIBS120_X86"
    $vclibManifest = Join-Path $vclibFolder "AppxManifest.xml"
    $vclibAppx = @(Get-ChildItem -LiteralPath $SourceDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe*.appx" } |
        Select-Object -First 1)

    if (Test-Path -LiteralPath $vclibManifest -PathType Leaf) {
        Write-Host "Registering extracted VCLibs dependency..." -ForegroundColor Cyan
        Add-AppxPackage -Register $vclibManifest -ForceApplicationShutdown
    } elseif ($vclibAppx) {
        Write-Host "Installing local VCLibs APPX dependency..." -ForegroundColor Cyan
        Add-AppxPackage -Path $vclibAppx.FullName -ForceApplicationShutdown
    } else {
        throw "Microsoft.VCLibs.120.00 x86 is not installed, and no local VCLibs AppxManifest.xml/.appx was found."
    }
}

# Preserve any pre-existing registration info for the report.
$before = Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue | Select-Object -First 1

Write-Host ""
Write-Host "Registering loose Phase 5 package..." -ForegroundColor Cyan
try {
    Add-AppxPackage -Register $manifestPath -ForceApplicationShutdown
} catch {
    $detail = $_ | Out-String
    $detail | Set-Content -LiteralPath (Join-Path $out "PHASE5-REGISTER-ERROR.txt") -Encoding UTF8
    try {
        Get-AppxLog | Out-String -Width 300 |
            Set-Content -LiteralPath (Join-Path $out "PHASE5-APPXLOG.txt") -Encoding UTF8
    } catch {}
    throw
}

$pkg = Get-AppxPackage -Name $packageName -ErrorAction Stop |
    Sort-Object Version -Descending |
    Select-Object -First 1

$pfn = $pkg.PackageFamilyName
$full = $pkg.PackageFullName
$install = $pkg.InstallLocation

$report = [ordered]@{
    Phase = "Package Phase 5"
    SourceGameRoot = $cleanGameRoot
    OutputRoot = $out
    PackageName = $packageName
    PackageVersion = $packageVersion
    ProcessorArchitecture = $packageArch
    ApplicationId = $appId
    PackageFamilyName = $pfn
    PackageFullName = $full
    RegisteredInstallLocation = $install
    AMS_SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out "AMS.exe")).Hash.ToLowerInvariant()
    AMS_DllCharacteristics = ("0x{0:X4}" -f (Get-PeDllCharacteristics (Join-Path $out "AMS.exe")))
    AMS_AppContainer = $true
    UsedOriginalWCPToolkit = $true
    UsedOriginalIGPLib = $true
    UsedOriginalIAP = $true
    StorePurchasePathBlockedInAMS = $true
    BaselineUntouched = $true
    PreviousRegistration = if ($before) { $before.PackageFullName } else { $null }
}
$report | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $out "PACKAGE-PHASE5-REPORT.json") -Encoding UTF8

$launchCmd = @"
@echo off
start "" "shell:AppsFolder\$pfn!$appId"
"@
Set-Content -LiteralPath (Join-Path $out "RUN-PACKAGE-PHASE5.cmd") -Value $launchCmd -Encoding ASCII

Write-Host ""
Write-Host "============================================================"
Write-Host " PACKAGE PHASE 5 REGISTERED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "PackageFullName: $full"
Write-Host "PackageFamily:   $pfn"
Write-Host "ApplicationId:   $appId"
Write-Host "InstallLocation: $install"
Write-Host ""
Write-Host "Launch with:"
Write-Host "  _PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd"
Write-Host ""

if ($Launch) {
    Start-Process "shell:AppsFolder\$pfn!$appId"
}
