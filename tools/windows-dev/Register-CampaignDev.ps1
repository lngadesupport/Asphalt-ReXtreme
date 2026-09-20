param(
    [switch]$ForceReplace,
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

$Manifest = Join-Path $GameRoot "AppxManifest.xml"
$Dependency = Join-Path $GameRoot "_campaign_runtime\Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe.appx"
$PackageName = "A278AB0D.AsphaltXtreme"

Write-Host "Asphalt ReXtreme Campaign - loose layout bootstrap"
Write-Host "Game root: $GameRoot"

if (-not (Test-Path $Manifest)) {
    throw "AppxManifest.xml not found: $Manifest"
}
if (-not (Test-Path $Dependency)) {
    throw "VC runtime package not found: $Dependency"
}

$existing = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue
if ($existing) {
    $sameLocation = $false
    foreach ($pkg in @($existing)) {
        if ($pkg.InstallLocation -and
            [System.StringComparer]::OrdinalIgnoreCase.Equals(
                [IO.Path]::GetFullPath($pkg.InstallLocation).TrimEnd('\'),
                [IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
            )) {
            $sameLocation = $true
        }
    }

    if (-not $sameLocation) {
        if (-not $ForceReplace) {
            throw @"
A package named $PackageName is already registered from another location.
Nothing was removed.

If that is an old test/installation that you explicitly want to replace, rerun:
  .\Register-CampaignDev.ps1 -ForceReplace
"@
        }

        Write-Host "Removing the conflicting package registration..."
        foreach ($pkg in @($existing)) {
            Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
        }
    }
}

$vclibs = Get-AppxPackage -Name "Microsoft.VCLibs.120.00" -ErrorAction SilentlyContinue |
    Where-Object { $_.Architecture -eq "X86" -or $_.Architecture -eq "x86" }

if (-not $vclibs) {
    Write-Host "Installing bundled Microsoft.VCLibs.120.00 x86 dependency..."
    Add-AppxPackage -Path $Dependency -ErrorAction Stop
} else {
    Write-Host "Microsoft.VCLibs.120.00 x86 already registered."
}

Write-Host "Registering loose development layout..."
Add-AppxPackage -Register $Manifest -ForceApplicationShutdown -ErrorAction Stop

$pkg = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
    Sort-Object Version -Descending |
    Select-Object -First 1

Write-Host ""
Write-Host "REGISTERED"
Write-Host "  Package: $($pkg.PackageFullName)"
Write-Host "  Family:  $($pkg.PackageFamilyName)"
Write-Host "  Location:$($pkg.InstallLocation)"
Write-Host ""
Write-Host "Next: run .\Launch-CampaignDev.ps1"
