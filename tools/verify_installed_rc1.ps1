[CmdletBinding()]
param(
    [string]$OutFile = ".artifacts\rc1-installed-report.json"
)

$ErrorActionPreference = "Stop"

$package = Get-AppxPackage -Name "ReXtreme.AsphaltXtreme" -ErrorAction Stop
$manifest = Get-AppxPackageManifest $package

$identity = $manifest.Package.Identity
$app = @($manifest.Package.Applications.Application)[0]
$capabilities = @(
    $manifest.Package.Capabilities.ChildNodes |
        ForEach-Object { $_.Name }
) | Where-Object { $_ }

$checks = [ordered]@{
    PackageName = ($identity.Name -eq "ReXtreme.AsphaltXtreme")
    Publisher = ($identity.Publisher -eq "CN=ReXtreme")
    Version = ($identity.Version -eq "1.0.0.0")
    Architecture = ($identity.ProcessorArchitecture -eq "x86")
    AMS = (Test-Path (Join-Path $package.InstallLocation "AMS.exe"))
    ReXtremeIni = (Test-Path (Join-Path $package.InstallLocation "ReXtreme.ini"))
    NoInternetClient = ($capabilities -notcontains "internetClient")
    NoInternetClientServer = ($capabilities -notcontains "internetClientServer")
    NoPrivateNetwork = ($capabilities -notcontains "privateNetworkClientServer")
    NoLocation = ($capabilities -notcontains "location")
}

$passed = -not ($checks.Values -contains $false)

$report = [ordered]@{
    Product = "Asphalt ReXtreme"
    Gate = "installed-package-static"
    Passed = $passed
    TimestampUtc = [DateTime]::UtcNow.ToString("o")
    PackageFullName = $package.PackageFullName
    PackageFamilyName = $package.PackageFamilyName
    InstallLocation = $package.InstallLocation
    ApplicationId = $app.Id
    Executable = $app.Executable
    EntryPoint = $app.EntryPoint
    Capabilities = $capabilities
    Checks = $checks
}

$target = [IO.Path]::GetFullPath($OutFile)
$parent = Split-Path -Parent $target
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}

$report | ConvertTo-Json -Depth 8 | Set-Content -Path $target -Encoding UTF8
$report | ConvertTo-Json -Depth 8

if (-not $passed) {
    exit 1
}
