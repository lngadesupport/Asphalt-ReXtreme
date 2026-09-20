param(
    [string]$GameRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PackageName = "A278AB0D.AsphaltXtreme"
$ExpectedAMS = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
        Sort-Object Version -Descending |
        Select-Object -First 1
    $GameRoot = $pkg.InstallLocation
} else {
    $GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
}

$ams = Join-Path $GameRoot "AMS.exe"
if (-not (Test-Path -LiteralPath $ams -PathType Leaf)) { throw "AMS.exe not found: $ams" }

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ams).Hash.ToLowerInvariant()
if ($hash -ne $ExpectedAMS) { throw "Unexpected AMS.exe hash: $hash" }

$out = Join-Path $GameRoot "_PROFILE_PHASE6C_LOGIN_ERROR"
if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Recurse -Force }
New-Item -ItemType Directory -Path $out -Force | Out-Null

[byte[]]$data = [IO.File]::ReadAllBytes($ams)

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
public static class ReXtremeByteSearch6C {
    public static int[] FindAll(byte[] haystack, byte[] needle) {
        if (haystack == null || needle == null || needle.Length == 0 || needle.Length > haystack.Length)
            return new int[0];
        var hits = new List<int>();
        int start = 0;
        byte first = needle[0];
        while (start <= haystack.Length - needle.Length) {
            int pos = Array.IndexOf<byte>(haystack, first, start);
            if (pos < 0 || pos > haystack.Length - needle.Length) break;
            bool match = true;
            for (int j = 1; j < needle.Length; j++) {
                if (haystack[pos+j] != needle[j]) { match = false; break; }
            }
            if (match) hits.Add(pos);
            start = pos + 1;
        }
        return hits.ToArray();
    }
}
"@

function Read-U16([int]$o) { [BitConverter]::ToUInt16($data,$o) }
function Read-U32([int]$o) { [BitConverter]::ToUInt32($data,$o) }

$pe=[int](Read-U32 0x3C)
$num=[int](Read-U16 ($pe+6))
$optSize=[int](Read-U16 ($pe+20))
$opt=$pe+24
$imageBase=[uint32](Read-U32 ($opt+28))
$sectionTable=$opt+$optSize
$sections=@()
for($i=0;$i -lt $num;$i++){
    $s=$sectionTable+40*$i
    $name=([Text.Encoding]::ASCII.GetString($data[$s..($s+7)])).Trim([char]0)
    $sections += [pscustomobject]@{
        Name=$name
        VA=[uint32](Read-U32 ($s+12))
        VSize=[uint32](Read-U32 ($s+8))
        Raw=[uint32](Read-U32 ($s+20))
        RawSize=[uint32](Read-U32 ($s+16))
    }
}

function File-To-VA([int]$off) {
    foreach($s in $sections){
        if($off -ge $s.Raw -and $off -lt ($s.Raw+$s.RawSize)){
            return [uint32]($imageBase + $s.VA + ($off-$s.Raw))
        }
    }
    return $null
}

function HexWindow([int]$off,[int]$before=320,[int]$after=512) {
    $a=[Math]::Max(0,$off-$before)
    $b=[Math]::Min($data.Length-1,$off+$after)
    (($data[$a..$b] | ForEach-Object { $_.ToString("X2") }) -join " ")
}

function Find-Nearest-Prologue([int]$off) {
    $start=[Math]::Max(0,$off-1024)
    for($i=$off;$i -ge $start;$i--){
        if($i+2 -lt $data.Length -and $data[$i] -eq 0x55 -and $data[$i+1] -eq 0x8B -and $data[$i+2] -eq 0xEC){
            return $i
        }
    }
    return -1
}

function Get-JccCandidates([int]$off) {
    $a=[Math]::Max(0,$off-128)
    $b=[Math]::Min($data.Length-6,$off+128)
    $rows=@()
    for($i=$a;$i -le $b;$i++){
        $op=$data[$i]
        if($op -ge 0x70 -and $op -le 0x7F){
            $rel=[sbyte]$data[$i+1]
            $dest=$i+2+$rel
            $rows += [pscustomobject]@{
                FileOffset=("0x{0:X8}" -f $i)
                VA=if($null -ne (File-To-VA $i)){("0x{0:X8}" -f (File-To-VA $i))}else{""}
                Opcode=("0x{0:X2}" -f $op)
                Type="Jcc-short"
                DestinationFileOffset=("0x{0:X8}" -f $dest)
                DestinationVA=if($null -ne (File-To-VA $dest)){("0x{0:X8}" -f (File-To-VA $dest))}else{""}
                DistanceFromXref=$i-$off
            }
            $i++
        } elseif($op -eq 0x0F -and $data[$i+1] -ge 0x80 -and $data[$i+1] -le 0x8F) {
            $rel=[BitConverter]::ToInt32($data,$i+2)
            $dest=$i+6+$rel
            $rows += [pscustomobject]@{
                FileOffset=("0x{0:X8}" -f $i)
                VA=if($null -ne (File-To-VA $i)){("0x{0:X8}" -f (File-To-VA $i))}else{""}
                Opcode=("0x0F{0:X2}" -f $data[$i+1])
                Type="Jcc-near"
                DestinationFileOffset=("0x{0:X8}" -f $dest)
                DestinationVA=if($null -ne (File-To-VA $dest)){("0x{0:X8}" -f (File-To-VA $dest))}else{""}
                DistanceFromXref=$i-$off
            }
            $i += 5
        }
    }
    return $rows
}

$targets=@(
    [pscustomobject]@{Name="STR_OUT_OF_SYNC_ISSUE_BODY"; VA=[uint32]0x01550D40},
    [pscustomobject]@{Name="STR_OUT_OF_SYNC_ISSUE_TITLE"; VA=[uint32]0x01550D5C},
    [pscustomobject]@{Name="STR_MENU_SYNC_LOADING"; VA=[uint32]0x01551B88},
    [pscustomobject]@{Name="STR_POPUP_LOGIN_ERROR_DESCRIPTION"; VA=[uint32]0x01551BB0},
    [pscustomobject]@{Name="STR_POPUP_LOGIN_ERROR_TITLE"; VA=[uint32]0x01551BD4}
)

$refs=@()
$details=@()
foreach($t in $targets){
    $needle=[BitConverter]::GetBytes([uint32]$t.VA)
    $hits=[ReXtremeByteSearch6C]::FindAll($data,$needle)
    foreach($h in $hits){
        $pro=Find-Nearest-Prologue $h
        $refs += [pscustomobject]@{
            String=$t.Name
            StringVA=("0x{0:X8}" -f $t.VA)
            XrefFileOffset=("0x{0:X8}" -f $h)
            XrefVA=if($null -ne (File-To-VA $h)){("0x{0:X8}" -f (File-To-VA $h))}else{""}
            NearestPrologueFileOffset=if($pro -ge 0){("0x{0:X8}" -f $pro)}else{""}
            NearestPrologueVA=if($pro -ge 0 -and $null -ne (File-To-VA $pro)){("0x{0:X8}" -f (File-To-VA $pro))}else{""}
        }
        $details += "===== $($t.Name) XREF_FILE=0x$('{0:X8}' -f $h) XREF_VA=$((if($null -ne (File-To-VA $h)){ '0x{0:X8}' -f (File-To-VA $h) } else { '' })) ====="
        $details += "NearestPrologueFileOffset=" + $(if($pro -ge 0){"0x{0:X8}" -f $pro}else{""})
        $details += "HEX[-320,+512]"
        $details += HexWindow $h
        $details += "JCC[-128,+128]"
        $jcc=Get-JccCandidates $h
        if($jcc.Count -eq 0){ $details += "(none)" } else {
            foreach($j in $jcc){
                $details += ("{0} {1} {2} -> {3} ({4}) delta={5}" -f $j.FileOffset,$j.VA,$j.Opcode,$j.DestinationFileOffset,$j.DestinationVA,$j.DistanceFromXref)
            }
        }
        $details += "------------------------------------------------------------"
    }
}

$refs | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "login-sync-string-xrefs.csv")
$details | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $out "login-sync-xref-context.txt")

$summary=[ordered]@{
    Phase="Profile Phase 6C Login Error"
    AMS_SHA256=$hash
    TotalXrefs=$refs.Count
    ByString=@{}
}
foreach($t in $targets){
    $summary.ByString[$t.Name]=@($refs | Where-Object {$_.String -eq $t.Name}).Count
}
$summary | ConvertTo-Json -Depth 6 |
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $out "PROFILE-PHASE6C-SUMMARY.json")

$zip=Join-Path $GameRoot "PROFILE-PHASE6C-LOGIN-ERROR.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 6C COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("AMS hash verified: True")
Write-Host ("Total login/sync xrefs: {0}" -f $refs.Count)
Write-Host ("ZIP: {0}" -f $zip)
Write-Host ""
