param([string]$GameRoot = "")

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
$packages = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue
$removed = 0

foreach ($pkg in @($packages)) {
    if (-not $pkg.InstallLocation) {
        continue
    }

    $sameLocation = [System.StringComparer]::OrdinalIgnoreCase.Equals(
        [IO.Path]::GetFullPath($pkg.InstallLocation).TrimEnd('\'),
        [IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
    )

    if ($sameLocation) {
        Write-Host "Removing Campaign development registration: $($pkg.PackageFullName)"
        Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
        $removed++
    }
}

if ($removed -eq 0) {
    Write-Host "No Campaign registration from this folder was found. Nothing removed."
} else {
    Write-Host "Removed $removed Campaign registration(s)."
}

Write-Host "Bundled VCLibs was intentionally left installed because other apps may use it."
