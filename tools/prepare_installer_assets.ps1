[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$Trailer,
    [Parameter(Mandatory=$true)]
    [string]$Logo,
    [string]$OutDir = ".artifacts\\installer-assets",
    [string]$Ffmpeg = "ffmpeg"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$out = Join-Path $repoRoot $OutDir
New-Item -ItemType Directory -Force -Path $out | Out-Null

$trailerPath = (Resolve-Path $Trailer).Path
$logoPath = (Resolve-Path $Logo).Path
$logoOut = Join-Path $out "logo.png"
$videoOut = Join-Path $out "trailer-vertical.mp4"

Copy-Item $logoPath $logoOut -Force

$ffmpegCommand = Get-Command $Ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegCommand) {
    throw "ffmpeg was not found. Install ffmpeg or pass -Ffmpeg with its executable path."
}

# 9:16 panel with approximately 1.06x overscale before centered crop.
$filter = "scale=-2:1018,crop=540:960:(iw-ow)/2:(ih-oh)/2,fps=30,format=yuv420p"
$ffmpegArgs = @(
    "-y",
    "-i", $trailerPath,
    "-vf", $filter,
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "22",
    "-c:a", "aac",
    "-b:a", "128k",
    "-movflags", "+faststart",
    $videoOut
)
& $ffmpegCommand.Source @ffmpegArgs

if ($LASTEXITCODE -ne 0 -or -not (Test-Path $videoOut)) {
    throw "ffmpeg failed to create the vertical installer trailer."
}

Write-Host "Installer assets ready:"
Write-Host "  Logo:    $logoOut"
Write-Host "  Trailer: $videoOut"
