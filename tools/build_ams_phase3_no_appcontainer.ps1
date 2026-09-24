param(
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedPhase2 = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$AppContainerFlag = 0x1000

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$phase2 = Join-Path $SourceDir "_AMS_PHASE2\AMS.exe"
if (-not (Test-Path -LiteralPath $phase2 -PathType Leaf)) {
    throw "Phase 2 AMS.exe not found: $phase2"
}

$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $phase2).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedPhase2) {
    throw "Unexpected Phase 2 AMS hash. Expected $ExpectedPhase2 but got $actual"
}

[byte[]]$data = [IO.File]::ReadAllBytes($phase2)

if ($data.Length -lt 0x200) {
    throw "AMS.exe is too small to be a valid PE image."
}
if ($data[0] -ne 0x4D -or $data[1] -ne 0x5A) {
    throw "AMS.exe does not start with MZ."
}

$peOffset = [BitConverter]::ToInt32($data, 0x3C)
if ($peOffset -lt 0 -or ($peOffset + 0x100) -ge $data.Length) {
    throw "Invalid PE header offset."
}
if ($data[$peOffset] -ne 0x50 -or $data[$peOffset+1] -ne 0x45 -or $data[$peOffset+2] -ne 0 -or $data[$peOffset+3] -ne 0) {
    throw "PE signature not found."
}

$optionalHeader = $peOffset + 24
$magic = [BitConverter]::ToUInt16($data, $optionalHeader)
if ($magic -ne 0x10B) {
    throw ("Expected PE32/x86 optional header (0x10B), found 0x{0:X4}" -f $magic)
}

$dllCharOffset = $optionalHeader + 0x46
$dllCharsBefore = [BitConverter]::ToUInt16($data, $dllCharOffset)
if (($dllCharsBefore -band $AppContainerFlag) -eq 0) {
    throw ("AppContainer flag is already clear. DllCharacteristics=0x{0:X4}" -f $dllCharsBefore)
}

$dllCharsAfter = [UInt16]($dllCharsBefore -band (-bnot $AppContainerFlag))
$bytes = [BitConverter]::GetBytes($dllCharsAfter)
$data[$dllCharOffset] = $bytes[0]
$data[$dllCharOffset + 1] = $bytes[1]

$outDir = Join-Path $SourceDir "_AMS_PHASE3_NO_APPCONTAINER"
if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$outFile = Join-Path $outDir "AMS.exe"
[IO.File]::WriteAllBytes($outFile, $data)

$final = (Get-FileHash -Algorithm SHA256 -LiteralPath $outFile).Hash.ToLowerInvariant()

# Verify written PE flag.
[byte[]]$check = [IO.File]::ReadAllBytes($outFile)
$written = [BitConverter]::ToUInt16($check, $dllCharOffset)
if (($written -band $AppContainerFlag) -ne 0) {
    throw "Post-write verification failed: AppContainer flag is still set."
}

$report = [ordered]@{
    Phase = "AMS Phase 3 - No AppContainer"
    InputPath = $phase2
    InputSHA256 = $actual
    PEHeaderOffset = $peOffset
    OptionalHeaderMagic = ("0x{0:X4}" -f $magic)
    DllCharacteristicsOffset = $dllCharOffset
    DllCharacteristicsBefore = ("0x{0:X4}" -f $dllCharsBefore)
    DllCharacteristicsAfter = ("0x{0:X4}" -f $dllCharsAfter)
    AppContainerBefore = $true
    AppContainerAfter = $false
    OutputPath = $outFile
    OutputSHA256 = $final
    Phase2Untouched = $true
}

$report | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $outDir "AMS-PHASE3-REPORT.json") -Encoding UTF8

@(
    "AMS Phase 3 - No AppContainer",
    "InputSHA256=$actual",
    "OutputSHA256=$final",
    ("DllCharacteristicsBefore=0x{0:X4}" -f $dllCharsBefore),
    ("DllCharacteristicsAfter=0x{0:X4}" -f $dllCharsAfter),
    "Phase2Untouched=True"
) | Set-Content -LiteralPath (Join-Path $outDir "AMS.phase3.sha256.txt") -Encoding ASCII

Write-Host ""
Write-Host "============================================================"
Write-Host " AMS PHASE 3 VERIFIED - APPCONTAINER CLEARED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Input SHA-256:        {0}" -f $actual)
Write-Host ("DllCharacteristics:   0x{0:X4} -> 0x{1:X4}" -f $dllCharsBefore, $dllCharsAfter)
Write-Host ("AppContainer after:   False")
Write-Host ("Phase 2 untouched:    True")
Write-Host ("Output SHA-256:       {0}" -f $final)
Write-Host ("Output:               {0}" -f $outFile)
Write-Host ""
