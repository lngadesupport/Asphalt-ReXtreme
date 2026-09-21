param([string]$GameRoot = "")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$pkg = Get-AppxPackage -Name "A278AB0D.AsphaltXtreme" -ErrorAction Stop |
    Sort-Object Version -Descending |
    Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($GameRoot)) { $GameRoot = $pkg.InstallLocation }

$ams = Join-Path $GameRoot "AMS.exe"
$expected = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$hash = (Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $expected) { throw "Phase 5 AMS hash required. Current: $hash" }

[byte[]]$d = [IO.File]::ReadAllBytes($ams)
$out = Join-Path $GameRoot "_PROFILE_PHASE7_CALLBACK_MAP"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path $out -Force | Out-Null

function Hex([int]$o,[int]$before=48,[int]$after=64) {
    $a=[Math]::Max(0,$o-$before)
    $b=[Math]::Min($d.Length-1,$o+$after)
    (($d[$a..$b] | ForEach-Object { $_.ToString("X2") }) -join " ")
}

$hits=@()
for($i=0;$i -le $d.Length-13;$i++){
    if($d[$i] -eq 0x8B -and $d[$i+1] -eq 0x8E -and
       $d[$i+2] -eq 0x70 -and $d[$i+3] -eq 0x01 -and
       $d[$i+4] -eq 0x00 -and $d[$i+5] -eq 0x00 -and
       $d[$i+6] -eq 0x6A -and
       $d[$i+8] -eq 0x8B -and $d[$i+9] -eq 0x01 -and
       $d[$i+10] -eq 0xFF -and $d[$i+11] -eq 0x50 -and
       ($d[$i+12] -eq 0x10 -or $d[$i+12] -eq 0x14)) {
        $hits += [pscustomobject]@{
            FileOffset=("0x{0:X8}" -f $i)
            Action=[int]$d[$i+7]
            VirtualSlot=("0x{0:X2}" -f $d[$i+12])
            NearbyHex=(Hex $i)
        }
    }
}

$hits | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "profile-action-callbacks.csv")

$focus = @($hits | Where-Object {
    $off=[Convert]::ToInt32($_.FileOffset.Substring(2),16)
    $off -ge 0x00740000 -and $off -lt 0x00742000
})
$focus | Format-List * | Out-String -Width 260 |
    Set-Content -LiteralPath (Join-Path $out "profile-action-callbacks-focus.txt") -Encoding UTF8

$summary=[ordered]@{
    Phase="Profile Phase 7 callback map"
    AMS_SHA256=$hash
    TotalMatches=$hits.Count
    FocusMatches=$focus.Count
    Actions=@()
}
foreach($g in ($hits | Group-Object Action)){
    $summary.Actions += [ordered]@{Action=[int]$g.Name;Count=$g.Count}
}
$summary | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $out "PROFILE-PHASE7-CALLBACK-SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE7-CALLBACK-MAP.zip"
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "PROFILE PHASE 7 CALLBACK MAP COMPLETE" -ForegroundColor Green
Write-Host ("Total callback patterns: {0}" -f $hits.Count)
Write-Host ("Focus 0x740xxx matches: {0}" -f $focus.Count)
Write-Host ("ZIP: {0}" -f $zip)
