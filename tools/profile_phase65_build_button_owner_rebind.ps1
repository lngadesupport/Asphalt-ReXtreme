param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

function Hex([byte[]]$b) { ($b | ForEach-Object { $_.ToString("X2") }) -join " " }
function Sha256([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() }

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$ams = Join-Path $ProjectRoot "_PACKAGE_PHASE5\AMS.exe"
if (!(Test-Path -LiteralPath $ams)) { throw "AMS.exe not found: $ams" }

# Stable chain after Phase64 reverted Phase63.
$guards = @(
    @{ Name="Phase36Popup"; Offset=0x009168B0; Bytes=[byte[]](0x31,0xC0,0xC2,0x18,0x00) },
    @{ Name="GlobalIsOnlineFALSE"; Offset=0x00BACDD0; Bytes=[byte[]](0x31,0xC0,0xC3,0x90,0x90,0x90,0x90) },
    @{ Name="Phase53"; Offset=0x00574FA7; Bytes=[byte[]](0x6A,0x01,0x90) },
    @{ Name="Phase54"; Offset=0x0059F3F2; Bytes=[byte[]](0xB8,0x02,0x00,0x00,0x00,0x90) },
    @{ Name="Phase55"; Offset=0x00573C45; Bytes=[byte[]](0x90,0x90,0x90,0x90,0x90,0x90) },
    @{ Name="Phase63Reverted"; Offset=0x00573CF4; Bytes=[byte[]](0x74,0x0B) }
)

# template_build_button_builder:
# owner->vtable+0xBC(&build_button_pair)
# cmp eax,-1
# sete [ebp-0x1D]
# ...
# if true -> owner->+0xDC(); owner->+0xD0(&build_button_pair)
#
# We force the local "not registered" flag to 1 so the current build_button
# is always rebound through the screen owner. This keeps the screen's own
# dispatch mechanism and does NOT fake global connectivity or call CraftCar
# directly.
$patchOffset = 0x0056E9CE
$expected = [byte[]](0x0F,0x94,0x45,0xE3)   # sete byte ptr [ebp-1Dh]
$patched  = [byte[]](0xC6,0x45,0xE3,0x01)   # mov  byte ptr [ebp-1Dh],1

$expectedCurrentSha = "7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

$bytes = [System.IO.File]::ReadAllBytes($ams)

foreach ($g in $guards) {
    $cur = New-Object byte[] $g.Bytes.Length
    [Array]::Copy($bytes, [int]$g.Offset, $cur, 0, $cur.Length)
    if ((Hex $cur) -ne (Hex $g.Bytes)) {
        throw "$($g.Name) guard failed at 0x$('{0:X8}' -f $g.Offset): got $(Hex $cur), expected $(Hex $g.Bytes)"
    }
}

$curPatch = New-Object byte[] $expected.Length
[Array]::Copy($bytes, $patchOffset, $curPatch, 0, $curPatch.Length)

$currentSha = Sha256 $ams

if ((Hex $curPatch) -eq (Hex $patched)) {
    Write-Host ""
    Write-Host "PHASE 65 already active."
    Write-Host "AMS SHA256: $currentSha"
    exit 0
}

if ((Hex $curPatch) -ne (Hex $expected)) {
    throw "Phase65 patch guard failed at 0x$('{0:X8}' -f $patchOffset): got $(Hex $curPatch), expected $(Hex $expected)"
}

if ($currentSha -ne $expectedCurrentSha) {
    throw "Unexpected AMS SHA256 before Phase65: $currentSha (expected $expectedCurrentSha). Nothing changed."
}

$outDir = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$backup = Join-Path $outDir "AMS.PRE-PHASE65-BUILD-BUTTON-REBIND.exe"
$report = Join-Path $outDir "PHASE65-BUILD-BUTTON-REBIND.json"

if (!(Test-Path -LiteralPath $backup)) {
    Copy-Item -LiteralPath $ams -Destination $backup -Force
}

$beforeHash = $currentSha
[Array]::Copy($patched, 0, $bytes, $patchOffset, $patched.Length)

$tmp = "$ams.phase65.tmp"
[System.IO.File]::WriteAllBytes($tmp, $bytes)

$verify = [System.IO.File]::ReadAllBytes($tmp)
$v = New-Object byte[] $patched.Length
[Array]::Copy($verify, $patchOffset, $v, 0, $v.Length)
if ((Hex $v) -ne (Hex $patched)) {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    throw "Temporary-file verification failed."
}

Move-Item -LiteralPath $tmp -Destination $ams -Force
$afterHash = Sha256 $ams

$obj = [ordered]@{
    Phase = "65-build-button-owner-rebind"
    Mode = "binary-patch"
    AMS_SHA256_Before = $beforeHash
    AMS_SHA256 = $afterHash
    Backup = $backup
    GlobalIsOnline = "FALSE"
    Phase36PopupBypass = $true
    Phase53 = $true
    Phase54 = $true
    Phase55 = $true
    Phase63 = "REVERTED"
    Root = [ordered]@{
        BuilderVA = "0x0096F3B0"
        BuilderFile = "0x0056E7B0"
        BuildButtonPair = "GarageBottomBarWidget +0x90/+0x94"
        OwnerLookupSlot = "+0xBC"
        OwnerEnsureSlot = "+0xDC"
        OwnerRegisterSlot = "+0xD0"
        GarageBuildSlot = "+0x110"
        GarageBuildHandler = "0x00A87960"
        CraftCarCaller = "0x0099FF50"
        CraftCar = "0x009A4BA0"
    }
    Patch = [ordered]@{
        FileOffset = ('0x{0:X8}' -f $patchOffset)
        PreferredVA = "0x0096F5CE"
        Before = Hex $expected
        After = Hex $patched
        Meaning = "Force template_build_button to run the existing owner rebind/register path (+0xDC/+0xD0), instead of skipping it when +0xBC reports an existing entry."
    }
    Test = @(
        "Launch RUN-PACKAGE-PHASE5.cmd",
        "Reach the garage",
        "Verify there is only one MONTAR button",
        "Click MONTAR once",
        "Report whether it builds/advances, spins, duplicates UI, errors, crashes, or remains click-sound-only"
    )
}

$obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "================================================================"
Write-Host " PHASE 65 OK - BUILD BUTTON OWNER REBIND"
Write-Host "================================================================"
Write-Host "Before SHA256: $beforeHash"
Write-Host "After  SHA256: $afterHash"
Write-Host "Patch: 0x$('{0:X8}' -f $patchOffset)  $(Hex $expected) -> $(Hex $patched)"
Write-Host "Backup: $backup"
Write-Host "Report: $report"
Write-Host ""
Write-Host "Global IsOnline remains FALSE."
Write-Host "The patch does NOT call CraftCar directly."
