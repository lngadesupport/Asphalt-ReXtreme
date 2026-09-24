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

# Current-chain guards.
$guards = @(
    @{ Name="Phase36Popup"; Offset=0x009168B0; Bytes=[byte[]](0x31,0xC0,0xC2,0x18,0x00) },
    @{ Name="GlobalIsOnlineFALSE"; Offset=0x00BACDD0; Bytes=[byte[]](0x31,0xC0,0xC3,0x90,0x90,0x90,0x90) },
    @{ Name="Phase53"; Offset=0x00574FA7; Bytes=[byte[]](0x6A,0x01,0x90) },
    @{ Name="Phase54"; Offset=0x0059F3F2; Bytes=[byte[]](0xB8,0x02,0x00,0x00,0x00,0x90) },
    @{ Name="Phase55"; Offset=0x00573C45; Bytes=[byte[]](0x90,0x90,0x90,0x90,0x90,0x90) }
)

$patchOffset = 0x00573CF4
$expected = [byte[]](0x74,0x0B)   # je skip GarageBottomBarWidget::+0x14
$patched  = [byte[]](0x90,0x90)   # always fall through to virtual +0x14

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

$outDir = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$backup = Join-Path $outDir "AMS.PRE-PHASE63-FORCE-GARAGE-SLOT14.exe"
$report = Join-Path $outDir "PHASE63-FORCE-GARAGE-SLOT14.json"

if ((Hex $curPatch) -eq (Hex $patched)) {
    Write-Host "PHASE 63 already active."
    Write-Host "AMS SHA256: $(Sha256 $ams)"
    exit 0
}

if ((Hex $curPatch) -ne (Hex $expected)) {
    throw "Patch guard failed at 0x$('{0:X8}' -f $patchOffset): got $(Hex $curPatch), expected $(Hex $expected)"
}

if (!(Test-Path -LiteralPath $backup)) {
    Copy-Item -LiteralPath $ams -Destination $backup -Force
}

$beforeHash = Sha256 $ams
[Array]::Copy($patched, 0, $bytes, $patchOffset, $patched.Length)

$tmp = "$ams.phase63.tmp"
[System.IO.File]::WriteAllBytes($tmp, $bytes)

# Verify written temp before replacing.
$verify = [System.IO.File]::ReadAllBytes($tmp)
$v = New-Object byte[] $patched.Length
[Array]::Copy($verify, $patchOffset, $v, 0, $v.Length)
if ((Hex $v) -ne (Hex $patched)) {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    throw "Temp verification failed."
}

Move-Item -LiteralPath $tmp -Destination $ams -Force
$afterHash = Sha256 $ams

$obj = [ordered]@{
    Phase = "63-force-garage-slot14"
    Mode = "binary-patch"
    AMS = $ams
    AMS_SHA256_Before = $beforeHash
    AMS_SHA256 = $afterHash
    Backup = $backup
    GlobalIsOnline = "FALSE"
    Phase36PopupBypass = $true
    Phase53 = $true
    Phase54 = $true
    Phase55 = $true
    Patch = [ordered]@{
        FileOffset = ('0x{0:X8}' -f $patchOffset)
        PreferredVA = "0x009748F4"
        Before = Hex $expected
        After = Hex $patched
        Meaning = "Force GarageBottomBarWidget click router to fall through into virtual slot +0x14 instead of skipping it when local DF flag is zero."
        TargetForGarageBottomBarWidget = "0x009740D0"
    }
    Test = "Launch package, reach the garage, click MONTAR once, and observe whether spinner/build flow starts."
}
$obj | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 63 OK - FORCE GARAGE CLICK -> SLOT +0x14"
Write-Host "============================================================"
Write-Host "Before SHA256: $beforeHash"
Write-Host "After  SHA256: $afterHash"
Write-Host "Patch: 0x$('{0:X8}' -f $patchOffset)  $(Hex $expected) -> $(Hex $patched)"
Write-Host "Backup: $backup"
Write-Host "Report: $report"
Write-Host ""
Write-Host "Global IsOnline remains FALSE."
Write-Host "Click MONTAR once after launching."
