[CmdletBinding()]
param(
    [string]$Candidate = "",
    [switch]$InstalledOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedName = "Microsoft.VCLibs.120.00"
$ExpectedVersion = [version]"12.0.21005.1"
$ExpectedArchitecture = "x86"
$ExpectedPublisherId = "8wekyb3d8bbwe"

function Get-ExactInstalledFramework {
    $packages = Get-AppxPackage -Name $ExpectedName -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Architecture -eq $ExpectedArchitecture -and
            ([version]$_.Version) -ge $ExpectedVersion
        } |
        Sort-Object {[version]$_.Version} -Descending

    return $packages | Select-Object -First 1
}

function Test-ExactVCLibsAppx([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "VC120 candidate does not exist: $Path"
    }

    $resolved = (Resolve-Path $Path).Path
    $leaf = Split-Path $resolved -Leaf
    $expectedPrefix = "Microsoft.VCLibs.120.00_"

    if (-not $leaf.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Wrong framework package name: $leaf"
    }
    if ($leaf -notmatch "_x86__8wekyb3d8bbwe\.appx$") {
        throw "VC120 candidate must be the x86 Microsoft package: $leaf"
    }

    $temp = Join-Path $env:TEMP ("rextreme-vclibs-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $temp | Out-Null
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($resolved, $temp)
        $manifestPath = Join-Path $temp "AppxManifest.xml"
        if (-not (Test-Path $manifestPath)) {
            throw "Candidate APPX has no AppxManifest.xml"
        }

        [xml]$manifest = Get-Content $manifestPath -Raw
        $identity = $manifest.Package.Identity
        if (-not $identity) { throw "Candidate APPX has no package Identity." }

        $name = [string]$identity.Name
        $version = [version]([string]$identity.Version)
        $arch = [string]$identity.ProcessorArchitecture

        if ($name -ne $ExpectedName) {
            throw "Wrong VC framework identity: $name"
        }
        if ($version -lt $ExpectedVersion) {
            throw "VC120 version is too old: $version"
        }
        if ($arch -ne $ExpectedArchitecture) {
            throw "VC120 architecture must be x86, got: $arch"
        }

        [pscustomobject]@{
            Path = $resolved
            Name = $name
            Version = $version.ToString()
            Architecture = $arch
            Sha256 = (Get-FileHash $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
            Size = (Get-Item $resolved).Length
        }
    }
    finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$installed = Get-ExactInstalledFramework
if ($InstalledOnly) {
    if ($installed) {
        [pscustomobject]@{
            Installed = $true
            Name = $installed.Name
            Version = $installed.Version.ToString()
            Architecture = $installed.Architecture.ToString()
            PackageFullName = $installed.PackageFullName
        } | ConvertTo-Json -Depth 4
        exit 0
    }

    [pscustomobject]@{
        Installed = $false
        Name = $ExpectedName
        MinimumVersion = $ExpectedVersion.ToString()
        Architecture = $ExpectedArchitecture
    } | ConvertTo-Json -Depth 4
    exit 1
}

if (-not $Candidate) {
    throw "Pass -Candidate with the exact Microsoft.VCLibs.120.00 x86 APPX."
}

$validated = Test-ExactVCLibsAppx $Candidate
$validated | Add-Member NoteProperty InstalledOnThisMachine ([bool]$installed)
$validated | ConvertTo-Json -Depth 4
