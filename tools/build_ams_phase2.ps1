param(
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedOriginal = "3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8"
$ExpectedPatched  = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

function HexToBytes([string]$Hex) {
    $clean = ($Hex -replace "\s", "")
    if (($clean.Length % 2) -ne 0) { throw "Invalid hex string length." }
    $bytes = New-Object byte[] ($clean.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($clean.Substring($i * 2, 2), 16)
    }
    return $bytes
}

$patches = @(
    [pscustomobject]@{ Name="Force central connectivity state offline"; Offset=12242384; Before="8A 81 B0 04 00 00 C3"; After="31 C0 C3 90 90 90 90" },
    [pscustomobject]@{ Name="Premium reward trampoline code cave"; Offset=10702759; Before="CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC CC"; After="55 89 E5 53 56 89 CE 8B 5D 08 53 89 F1 E8 97 67 00 00 8B 5D 08 85 DB 7E 15 D1 EB 74 11 89 F1 E8 F5 78 00 00 01 D8 50 89 F1 E8 6B BB 05 00 5E 5B 89 EC 5D C2 04 00" },
    [pscustomobject]@{ Name="Race payout hook 1"; Offset=5234689; Before="E8 4A D7 53 00"; After="E8 A1 6F 53 00" },
    [pscustomobject]@{ Name="Race payout hook 2"; Offset=7570178; Before="E8 49 34 30 00"; After="E8 A0 CC 2F 00" },
    [pscustomobject]@{ Name="Race payout hook 3"; Offset=7570596; Before="E8 A7 32 30 00"; After="E8 FE CA 2F 00" },
    [pscustomobject]@{ Name="Race payout hook 4"; Offset=8347037; Before="E8 AE 59 24 00"; After="E8 05 F2 23 00" },
    [pscustomobject]@{ Name="Race payout hook 5"; Offset=11611056; Before="E8 9B 8B F2 FF"; After="E8 F2 23 F2 FF" },
    [pscustomobject]@{ Name="Vungle manager: force ad availability unavailable"; Offset=13694832; Before="55 8B EC 6A FF 68 F0 EA"; After="B8 0A 00 00 00 C2 0C 00" },
    [pscustomobject]@{ Name="Vungle manager: configure stub without SDK activation"; Offset=13695376; Before="55 8B EC 6A FF 68 28 EB 49"; After="C6 41 09 01 33 C0 C2 10 00" },
    [pscustomobject]@{ Name="Vungle platform: force availability false"; Offset=13734752; Before="55 8B EC 6A FF"; After="33 C0 C2 08 00" },
    [pscustomobject]@{ Name="Windows CRM store purchase: fail locally without launching Store"; Offset=14937776; Before="55 8B EC 81 EC D4 04 00"; After="B8 1F D1 FF FF C2 1C 00" }
)

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$outDir = Join-Path $SourceDir "_AMS_PHASE2"
if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$candidates = @(Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Filter "AMS.exe" |
    Where-Object { -not $_.FullName.StartsWith($outDir, [StringComparison]::OrdinalIgnoreCase) })

$matching = @()
foreach ($c in $candidates) {
    $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $c.FullName).Hash.ToLowerInvariant()
    if ($h -eq $ExpectedOriginal) {
        $matching += $c
    }
}

if ($matching.Count -ne 1) {
    throw "Expected exactly one pristine AMS.exe with SHA-256 $ExpectedOriginal; found $($matching.Count)."
}

$src = $matching[0].FullName
$dst = Join-Path $outDir "AMS.exe"

Write-Host "Pristine AMS found:" -ForegroundColor Cyan
Write-Host "  $src"
Write-Host "SHA-256:"
Write-Host "  $ExpectedOriginal"
Write-Host ""

[byte[]]$data = [IO.File]::ReadAllBytes($src)
$results = @()

foreach ($p in $patches) {
    [byte[]]$before = HexToBytes $p.Before
    [byte[]]$after = HexToBytes $p.After
    if ($before.Length -ne $after.Length) {
        throw "$($p.Name): before/after sizes differ."
    }
    if (($p.Offset + $before.Length) -gt $data.Length) {
        throw "$($p.Name): offset outside AMS.exe."
    }

    for ($i = 0; $i -lt $before.Length; $i++) {
        if ($data[$p.Offset + $i] -ne $before[$i]) {
            $found = ($data[$p.Offset..($p.Offset + $before.Length - 1)] | ForEach-Object { $_.ToString("X2") }) -join " "
            throw "$($p.Name): byte mismatch at offset $($p.Offset). Found: $found"
        }
    }

    [Array]::Copy($after, 0, $data, $p.Offset, $after.Length)
    Write-Host ("[PATCH] 0x{0:X8}  {1}" -f $p.Offset, $p.Name)

    $results += [pscustomobject]@{
        Name = $p.Name
        Offset = [int64]$p.Offset
        Before = $p.Before
        After = $p.After
        Applied = $true
    }
}

[IO.File]::WriteAllBytes($dst, $data)
$final = (Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash.ToLowerInvariant()
if ($final -ne $ExpectedPatched) {
    Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    throw "Final AMS hash mismatch. Expected $ExpectedPatched but got $final"
}

@(
    "Original AMS.exe"
    "SHA256=$ExpectedOriginal"
    "Path=$src"
) | Set-Content -LiteralPath (Join-Path $outDir "AMS.original.sha256.txt") -Encoding ASCII

@(
    "Campaign Phase 2 AMS.exe"
    "SHA256=$final"
    "Expected=$ExpectedPatched"
) | Set-Content -LiteralPath (Join-Path $outDir "AMS.phase2.sha256.txt") -Encoding ASCII

$report = [ordered]@{
    Phase = "AMS Phase 2"
    SourcePath = $src
    OriginalSHA256 = $ExpectedOriginal
    OutputPath = $dst
    OutputSHA256 = $final
    ExpectedOutputSHA256 = $ExpectedPatched
    PatchCount = $patches.Count
    OutputVerified = ($final -eq $ExpectedPatched)
    OriginalUntouched = $true
    Patches = $results
}

$report | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $outDir "AMS-PHASE2-REPORT.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " AMS PHASE 2 VERIFIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Original untouched: True"
Write-Host "Patches applied:    $($patches.Count)"
Write-Host "Output SHA-256:     $final"
Write-Host "Output:             $dst"
Write-Host ""
