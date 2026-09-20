[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$PublishedInstallerDir,
    [Parameter(Mandatory=$true)]
    [string]$PayloadDir,
    [Parameter(Mandatory=$true)]
    [string]$AssetsDir,
    [string]$OutDir = ".artifacts\\setup-rc1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$published = (Resolve-Path $PublishedInstallerDir).Path
$payload = (Resolve-Path $PayloadDir).Path
$assets = (Resolve-Path $AssetsDir).Path
$out = Join-Path $repoRoot $OutDir

$exe = Join-Path $published "AsphaltReXtreme.Setup.exe"
$manifest = Join-Path $payload "install-manifest.json"
$logo = Join-Path $assets "logo.png"
$trailer = Join-Path $assets "trailer-vertical.mp4"

foreach ($required in @($exe, $manifest, $logo, $trailer)) {
    if (-not (Test-Path $required)) {
        throw "Required Setup input is missing: $required"
    }
}

if (Test-Path $out) {
    Remove-Item $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
Copy-Item (Join-Path $published "*") $out -Recurse -Force

$assetsOut = Join-Path $out "assets"
$payloadOut = Join-Path $out "payload"
New-Item -ItemType Directory -Force -Path $assetsOut, $payloadOut | Out-Null
Copy-Item (Join-Path $assets "*") $assetsOut -Recurse -Force
Copy-Item (Join-Path $payload "*") $payloadOut -Recurse -Force

$setupManifest = @{
    product = "Asphalt ReXtreme Offline Edition"
    version = "1.0.0-rc1"
    executable = "AsphaltReXtreme.Setup.exe"
    assets = @{
        logo = "assets\\logo.png"
        trailer = "assets\\trailer-vertical.mp4"
    }
    payloadManifest = "payload\\install-manifest.json"
}
$setupManifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $out "setup-layout.json") -Encoding UTF8

Write-Host "RC1 Setup layout ready:"
Write-Host "  $out"
