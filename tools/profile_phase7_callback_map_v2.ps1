param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$ams = Join-Path $GameRoot "AMS.exe"

if (-not (Test-Path -LiteralPath $ams -PathType Leaf)) {
    throw "Phase 5 AMS.exe not found: $ams"
}

$expected = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$hash = (Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

if ($hash -ne $expected) {
    throw "Phase 5 AMS hash required. Current: $hash"
}

[byte[]]$d = [IO.File]::ReadAllBytes($ams)

$out = Join-Path $GameRoot "_PROFILE_PHASE7_CALLBACK_MAP_V2"
if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Path $out -Force | Out-Null

function Get-HexWindow([int]$Offset,[int]$Before=48,[int]$After=64) {
    $a=[Math]::Max(0,$Offset-$Before)
    $b=[Math]::Min($d.Length-1,$Offset+$After)
    (($d[$a..$b] | ForEach-Object { $_.ToString("X2") }) -join " ")
}

$hits=@()

for($i=0; $i -le $d.Length-13; $i++) {
    if(
        $d[$i]   -eq 0x8B -and
        $d[$i+1] -eq 0x8E -and
        $d[$i+2] -eq 0x70 -and
        $d[$i+3] -eq 0x01 -and
        $d[$i+4] -eq 0x00 -and
        $d[$i+5] -eq 0x00 -and
        $d[$i+6] -eq 0x6A -and
        $d[$i+8] -eq 0x8B -and
        $d[$i+9] -eq 0x01 -and
        $d[$i+10] -eq 0xFF -and
        $d[$i+11] -eq 0x50 -and
        ($d[$i+12] -eq 0x10 -or $d[$i+12] -eq 0x14)
    ) {
        $hits += [pscustomobject]@{
            FileOffset = ("0x{0:X8}" -f $i)
            Action = [int]$d[$i+7]
            VirtualSlot = ("0x{0:X2}" -f $d[$i+12])
            NearbyHex = Get-HexWindow $i
        }
    }
}

$hits | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "profile-action-callbacks.csv")

$focus=@()
foreach($h in $hits) {
    $off=[Convert]::ToInt32($h.FileOffset.Substring(2),16)
    if($off -ge 0x00740000 -and $off -lt 0x00742000) {
        $focus += $h
    }
}

$focus | Format-List * | Out-String -Width 260 |
    Set-Content -LiteralPath (Join-Path $out "profile-action-callbacks-focus.txt") -Encoding UTF8

$actions=@()
foreach($g in ($hits | Group-Object Action)) {
    $actions += [ordered]@{
        Action=[int]$g.Name
        Count=$g.Count
    }
}

$summary=[ordered]@{
    Phase="Profile Phase 7 Callback Map V2"
    GameRoot=$GameRoot
    AMS_SHA256=$hash
    TotalMatches=$hits.Count
    FocusMatches=$focus.Count
    Actions=$actions
}

$summary | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $out "PROFILE-PHASE7-CALLBACK-SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE7-CALLBACK-MAP-V2.zip"
if(Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}

Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 7 CALLBACK MAP V2 COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("GameRoot:                {0}" -f $GameRoot)
Write-Host ("AMS hash verified:       True")
Write-Host ("Total callback patterns: {0}" -f $hits.Count)
Write-Host ("Focus 0x740xxx matches:  {0}" -f $focus.Count)
Write-Host ("ZIP:                     {0}" -f $zip)
Write-Host ""
