[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$Source,

    [string]$OutDir = ".artifacts\1.0-rc1",

    [string]$VCLibsPath = "",

    [string]$BrandingDir = "",

    [switch]$Install
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Find-WindowsSdkTool([string]$Name) {
    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $roots) {
        $tool = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "x64\$Name" } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if ($tool) { return $tool }
    }

    throw "Windows SDK tool not found: $Name"
}

function Invoke-PythonBuilder([string[]]$BuilderArgs) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3 @BuilderArgs
        return $LASTEXITCODE
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source @BuilderArgs
        return $LASTEXITCODE
    }

    throw "Python 3 was not found."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = (Resolve-Path $Source).Path
$out = Join-Path $repoRoot $OutDir
$stage = Join-Path $out "stage"
$payload = Join-Path $out "installer-payload"
$appx = Join-Path $payload "Asphalt-ReXtreme-1.0.0.0-x86.appx"
$cer = Join-Path $payload "ReXtreme-Publisher.cer"
$pfx = Join-Path $out "ReXtreme-Publisher-RC.pfx"

New-Item -ItemType Directory -Force -Path $out, $payload | Out-Null

$builderArgs = @(
    (Join-Path $repoRoot "tools\build_full_repack.py"),
    $sourcePath,
    $stage,
    "--patch-manifest", (Join-Path $repoRoot "patches\1.7.3.8-x86.json"),
    "--config", (Join-Path $repoRoot "config\ReXtreme-1.0.ini")
)

if ($BrandingDir) {
    $builderArgs += @("--branding-dir", (Resolve-Path $BrandingDir).Path)
}

Write-Host "=== ReXtreme 1.0 RC1: staging ==="
$exitCode = Invoke-PythonBuilder $builderArgs
if ($exitCode -ne 0) { throw "Full repack builder failed." }

$buildMeta = Get-Content (Join-Path $stage "ReXtremeBuild.json") -Raw | ConvertFrom-Json
if (-not $buildMeta.release_eligible) {
    Write-Warning "This build is diagnostic only: Premium XML overrides were not applied."
}

$makeappx = Find-WindowsSdkTool "makeappx.exe"
$signtool = Find-WindowsSdkTool "signtool.exe"

Write-Host "=== Packaging APPX ==="
if (Test-Path $appx) { Remove-Item $appx -Force }
& $makeappx pack /o /d $stage /p $appx
if ($LASTEXITCODE -ne 0) { throw "MakeAppx failed." }

Write-Host "=== Creating RC publisher certificate ==="
$cert = New-SelfSignedCertificate `
    -Type Custom `
    -Subject "CN=ReXtreme" `
    -FriendlyName "Asphalt ReXtreme RC Publisher" `
    -KeyUsage DigitalSignature `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -TextExtension @(
        "2.5.29.37={text}1.3.6.1.5.5.7.3.3",
        "2.5.29.19={text}"
    )

$passwordText = [Guid]::NewGuid().ToString("N")
$password = ConvertTo-SecureString -String $passwordText -Force -AsPlainText

Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $password | Out-Null
Export-Certificate -Cert $cert -FilePath $cer | Out-Null

Write-Host "=== Signing APPX ==="
& $signtool sign /fd SHA256 /a /f $pfx /p $passwordText $appx
if ($LASTEXITCODE -ne 0) { throw "SignTool signing failed." }

Write-Host "=== Verifying signature ==="
$temporaryTrust = Import-Certificate -FilePath $cer -CertStoreLocation "Cert:\CurrentUser\TrustedPeople"
try {
    & $signtool verify /pa /v $appx
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed." }
}
finally {
    if ($temporaryTrust) {
        Remove-Item ("Cert:\CurrentUser\TrustedPeople\" + $temporaryTrust.Thumbprint) -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item $pfx -Force -ErrorAction SilentlyContinue
Remove-Item ("Cert:\CurrentUser\My\" + $cert.Thumbprint) -Force -ErrorAction SilentlyContinue

$dependencyName = $null
if ($VCLibsPath) {
    $vc = (Resolve-Path $VCLibsPath).Path
    $dependencyName = Split-Path $vc -Leaf
    Copy-Item $vc (Join-Path $payload $dependencyName) -Force
}

$installManifest = @{
    product = "Asphalt ReXtreme"
    version = "1.0.0-rc1"
    package = (Split-Path $appx -Leaf)
    certificate = (Split-Path $cer -Leaf)
    dependency = $dependencyName
    packageSha256 = (Get-FileHash $appx -Algorithm SHA256).Hash.ToLowerInvariant()
    certificateSha256 = (Get-FileHash $cer -Algorithm SHA256).Hash.ToLowerInvariant()
    releaseEligible = [bool]$buildMeta.release_eligible -and [bool]$dependencyName
}

$installManifest |
    ConvertTo-Json -Depth 4 |
    Set-Content (Join-Path $payload "install-manifest.json") -Encoding UTF8

Write-Host ""
Write-Host "RC1 payload ready:"
Write-Host "  $payload"
Write-Host ("Release eligible: " + $installManifest.releaseEligible)

if ($Install) {
    Write-Host "=== Installing local RC ==="
    Import-Certificate -FilePath $cer -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" | Out-Null

    if ($VCLibsPath) {
        Add-AppxPackage -Path $appx -DependencyPath (Resolve-Path $VCLibsPath).Path -ForceApplicationShutdown -RetainFilesOnFailure
    } else {
        Add-AppxPackage -Path $appx -ForceApplicationShutdown -RetainFilesOnFailure
    }

    Write-Host "Installed."
}
