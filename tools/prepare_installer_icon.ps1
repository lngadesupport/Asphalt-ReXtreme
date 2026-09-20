[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$IconPng,
    [string]$Ffmpeg = "ffmpeg"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectDir = Join-Path $repoRoot "installer\AsphaltReXtreme.Setup"
$resources = Join-Path $projectDir "Resources"
$output = Join-Path $resources "app.ico"
New-Item -ItemType Directory -Force -Path $resources | Out-Null

$source = (Resolve-Path $IconPng).Path
$ffmpegCommand = Get-Command $Ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegCommand) {
    throw "ffmpeg was not found. Pass -Ffmpeg with its executable path."
}

$args = @(
    "-y",
    "-i", $source,
    "-vf", "scale=256:256:force_original_aspect_ratio=decrease,pad=256:256:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
    "-frames:v", "1",
    $output
)
& $ffmpegCommand.Source @args

if ($LASTEXITCODE -ne 0 -or -not (Test-Path $output)) {
    throw "Could not create the installer ICO."
}

Write-Host "RX executable icon ready: $output"
