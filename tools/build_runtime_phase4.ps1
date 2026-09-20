param(
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$ExpectedWcp = "ca67dd62c599d00868b230e4e536bb1ad4ad3c19f3e62293e42cd297b44b60a5"

function Get-PeDllCharacteristicsOffset([byte[]]$Data) {
    if ($Data.Length -lt 0x200) { throw "PE image too small." }
    if ($Data[0] -ne 0x4D -or $Data[1] -ne 0x5A) { throw "Missing MZ header." }
    $pe = [BitConverter]::ToInt32($Data, 0x3C)
    if ($Data[$pe] -ne 0x50 -or $Data[$pe+1] -ne 0x45) { throw "Missing PE header." }
    $opt = $pe + 24
    $magic = [BitConverter]::ToUInt16($Data, $opt)
    if ($magic -ne 0x10B) { throw ("Expected PE32/x86, found 0x{0:X4}" -f $magic) }
    return ($opt + 0x46)
}

function Clear-AppContainer([string]$Path) {
    [byte[]]$d = [IO.File]::ReadAllBytes($Path)
    $off = Get-PeDllCharacteristicsOffset $d
    $before = [BitConverter]::ToUInt16($d, $off)
    $after = [UInt16]($before -band 0xEFFF)
    $b = [BitConverter]::GetBytes($after)
    $d[$off] = $b[0]; $d[$off+1] = $b[1]
    [IO.File]::WriteAllBytes($Path, $d)
    return [pscustomobject]@{ Before=$before; After=$after; Offset=$off }
}

function Patch-Bytes([byte[]]$Data, [int]$Offset, [byte[]]$Before, [byte[]]$After, [string]$Name) {
    if ($Before.Length -ne $After.Length) { throw "$Name length mismatch." }
    for ($i=0; $i -lt $Before.Length; $i++) {
        if ($Data[$Offset+$i] -ne $Before[$i]) {
            throw "$Name byte mismatch at offset $Offset."
        }
    }
    [Array]::Copy($After,0,$Data,$Offset,$After.Length)
}

function Hex([string]$s) {
    $clean = ($s -replace "\s","")
    $o = New-Object byte[] ($clean.Length/2)
    for ($i=0;$i -lt $o.Length;$i++) { $o[$i]=[Convert]::ToByte($clean.Substring($i*2,2),16) }
    return $o
}

# Locate clean game root
$cleanBase = Join-Path $SourceDir "CLEAN-1.7.3.8-EXTRACTED"
$amsOriginal = @(Get-ChildItem -LiteralPath $cleanBase -Recurse -File -Filter "AMS.exe")
if ($amsOriginal.Count -ne 1) { throw "Could not resolve unique clean game root." }
$gameRoot = $amsOriginal[0].Directory.FullName

$phase3 = Join-Path $SourceDir "_AMS_PHASE3_NO_APPCONTAINER\AMS.exe"
if (-not (Test-Path -LiteralPath $phase3 -PathType Leaf)) { throw "Missing Phase 3 AMS: $phase3" }

$stubsDir = Join-Path $SourceDir "RUNTIME_STUBS"
$igpStub = Join-Path $stubsDir "IGPLib_x86.dll"
$iapStub = Join-Path $stubsDir "InAppPurchaseComponentW8.dll"
if (-not (Test-Path -LiteralPath $igpStub)) { throw "Missing runtime stub: $igpStub" }
if (-not (Test-Path -LiteralPath $iapStub)) { throw "Missing runtime stub: $iapStub" }

$out = Join-Path $SourceDir "_RUNTIME_PHASE4"
if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Recurse -Force }
Write-Host "Copying clean game tree..." -ForegroundColor Cyan
Copy-Item -LiteralPath $gameRoot -Destination $out -Recurse -Force

Copy-Item -LiteralPath $phase3 -Destination (Join-Path $out "AMS.exe") -Force
Copy-Item -LiteralPath $igpStub -Destination (Join-Path $out "IGPLib_x86.dll") -Force
Copy-Item -LiteralPath $iapStub -Destination (Join-Path $out "InAppPurchaseComponentW8.dll") -Force

# Patch WCPToolkit local paths and clear AppContainer
$wcp = Join-Path $out "WCPToolkit.dll"
$wcpHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $wcp).Hash.ToLowerInvariant()
if ($wcpHash -ne $ExpectedWcp) { throw "Unexpected WCPToolkit.dll SHA-256: $wcpHash" }

[byte[]]$wd = [IO.File]::ReadAllBytes($wcp)
Patch-Bytes $wd 186992 (Hex "55 8B EC 83 E4 F8 6A FF 68 C8 97 0A 10 64 A1 00 00 00 00 50 83") (Hex "8B 4C 24 04 6A 01 68 FE 90 0B 10 E8 E0 B3 FF FF 8B 44 24 04 C3") "WCP GetAppInstalledFolderPath"
Patch-Bytes $wd 187504 (Hex "55 8B EC 83 E4 F8 6A FF 68 C8 97 0A 10 64 A1 00 00 00 00 50 83") (Hex "8B 4C 24 04 6A 01 68 FE 90 0B 10 E8 E0 B1 FF FF 8B 44 24 04 C3") "WCP GetAppLocalFolderPath"
[IO.File]::WriteAllBytes($wcp,$wd)
$wcpFlags = Clear-AppContainer $wcp

# Extract local VCLibs runtime
$vclibsArchive = @(Get-ChildItem -LiteralPath $SourceDir -File | Where-Object { $_.Name -like "Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe*.rar" } | Select-Object -First 1)
if (-not $vclibsArchive) { throw "VCLibs x86 RAR not found in $SourceDir" }

$archiver = $null
$kind = $null
foreach ($c in @(
    @{K="7z"; P=(Join-Path ([Environment]::GetFolderPath("ProgramFiles")) "7-Zip\7z.exe")},
    @{K="unrar"; P=(Join-Path ([Environment]::GetFolderPath("ProgramFiles")) "WinRAR\UnRAR.exe")},
    @{K="winrar"; P=(Join-Path ([Environment]::GetFolderPath("ProgramFiles")) "WinRAR\WinRAR.exe")}
)) {
    if ($c.P -and (Test-Path -LiteralPath $c.P)) { $archiver=$c.P; $kind=$c.K; break }
}
if (-not $archiver) {
    $pf86=[Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    foreach ($c in @(
        @{K="7z"; P=(Join-Path $pf86 "7-Zip\7z.exe")},
        @{K="unrar"; P=(Join-Path $pf86 "WinRAR\UnRAR.exe")},
        @{K="winrar"; P=(Join-Path $pf86 "WinRAR\WinRAR.exe")}
    )) {
        if ($c.P -and (Test-Path -LiteralPath $c.P)) { $archiver=$c.P; $kind=$c.K; break }
    }
}
if (-not $archiver) { throw "7-Zip/WinRAR/UnRAR not found." }

$tmp = Join-Path $SourceDir "_VCLIBS_TMP"
if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

if ($kind -eq "7z") {
    & $archiver x -y -bso0 -bsp0 ("-o{0}" -f $tmp) $vclibsArchive.FullName
} elseif ($kind -eq "unrar") {
    & $archiver x -y -idq $vclibsArchive.FullName ($tmp + "\")
} else {
    & $archiver x -y -ibck $vclibsArchive.FullName ($tmp + "\")
}
if ($LASTEXITCODE -ne 0) { throw "Failed to extract VCLibs archive." }

$runtimeNames = @("vccorlib120_app.dll","msvcp120_app.dll","msvcr120_app.dll","vcamp120_app.dll","vcomp120_app.dll")
$runtimeRows=@()
foreach ($n in $runtimeNames) {
    $f = @(Get-ChildItem -LiteralPath $tmp -Recurse -File -Filter $n | Select-Object -First 1)
    if (-not $f) { throw "Missing VCLibs runtime file: $n" }
    Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $out $n) -Force
    $runtimeRows += [pscustomobject]@{ File=$n; SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out $n)).Hash.ToLowerInvariant() }
}
Remove-Item -LiteralPath $tmp -Recurse -Force

# Build launch wrapper
$launch = @'
@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Asphalt ReXtreme - Runtime Phase 4
echo ============================================================
echo.
echo Launching AMS.exe from full clean game tree...
echo.
AMS.exe
set RC=%ERRORLEVEL%
echo.
echo AMS.exe exit code: %RC%
echo %RC%>_PHASE4-LAST-EXIT.txt
pause
exit /b %RC%
'@
Set-Content -LiteralPath (Join-Path $out "RUN-PHASE4.cmd") -Value $launch -Encoding ASCII

$summary=[ordered]@{
    Phase="Runtime Phase 4"
    CleanGameRoot=$gameRoot
    Output=$out
    AMS_SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out "AMS.exe")).Hash.ToLowerInvariant()
    WCP_SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath $wcp).Hash.ToLowerInvariant()
    WCP_DllCharacteristicsBefore=("0x{0:X4}" -f $wcpFlags.Before)
    WCP_DllCharacteristicsAfter=("0x{0:X4}" -f $wcpFlags.After)
    IGPStub_SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out "IGPLib_x86.dll")).Hash.ToLowerInvariant()
    IAPStub_SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $out "InAppPurchaseComponentW8.dll")).Hash.ToLowerInvariant()
    VCLibs=$runtimeRows
    BaselineUntouched=$true
    AMSPhase3Untouched=$true
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out "RUNTIME-PHASE4-REPORT.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " RUNTIME PHASE 4 BUILT" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Output: $out"
Write-Host "WCP AppContainer cleared: True"
Write-Host "IGP stub installed:       True"
Write-Host "IAP stub installed:       True"
Write-Host "VCLibs x86 installed:     True"
Write-Host "Baseline untouched:       True"
Write-Host ""
Write-Host "Next: run _RUNTIME_PHASE4\RUN-PHASE4.cmd"
