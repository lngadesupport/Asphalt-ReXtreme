param(
    [string]$GameRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PackageName = "A278AB0D.AsphaltXtreme"

if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
        Sort-Object Version -Descending |
        Select-Object -First 1
    $GameRoot = $pkg.InstallLocation
} else {
    $GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1
}

$ams = Join-Path $GameRoot "AMS.exe"
if (-not (Test-Path -LiteralPath $ams -PathType Leaf)) {
    throw "AMS.exe not found: $ams"
}

$out = Join-Path $GameRoot "_PROFILE_PHASE6_PROBE"
if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Path $out -Force | Out-Null

[byte[]]$data = [IO.File]::ReadAllBytes($ams)

function Read-U16([int]$Offset) {
    return [BitConverter]::ToUInt16($data,$Offset)
}
function Read-U32([int]$Offset) {
    return [BitConverter]::ToUInt32($data,$Offset)
}
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;

public static class ReXtremeByteSearch
{
    public static int[] FindAll(byte[] haystack, byte[] needle)
    {
        if (haystack == null || needle == null || needle.Length == 0 || needle.Length > haystack.Length)
            return new int[0];

        var hits = new List<int>();
        int start = 0;
        byte first = needle[0];

        while (start <= haystack.Length - needle.Length)
        {
            int pos = Array.IndexOf<byte>(haystack, first, start);
            if (pos < 0 || pos > haystack.Length - needle.Length)
                break;

            bool match = true;
            for (int j = 1; j < needle.Length; j++)
            {
                if (haystack[pos + j] != needle[j])
                {
                    match = false;
                    break;
                }
            }

            if (match)
                hits.Add(pos);

            start = pos + 1;
        }

        return hits.ToArray();
    }
}
"@

function Find-Bytes([byte[]]$Haystack,[byte[]]$Needle) {
    return [ReXtremeByteSearch]::FindAll($Haystack,$Needle)
}
function Hex-Window([int]$Offset,[int]$Before=32,[int]$After=48) {
    $start=[Math]::Max(0,$Offset-$Before)
    $end=[Math]::Min($data.Length-1,$Offset+$After)
    return (($data[$start..$end] | ForEach-Object { $_.ToString("X2") }) -join " ")
}

if ($data.Length -lt 0x200 -or $data[0] -ne 0x4D -or $data[1] -ne 0x5A) {
    throw "AMS.exe is not a valid MZ image."
}
$pe = [int](Read-U32 0x3C)
if ($data[$pe] -ne 0x50 -or $data[$pe+1] -ne 0x45) { throw "PE signature missing." }
$numSections = [int](Read-U16 ($pe+6))
$sizeOpt = [int](Read-U16 ($pe+20))
$opt = $pe + 24
$magic = Read-U16 $opt
if ($magic -ne 0x10B) { throw ("Expected PE32/x86, found 0x{0:X4}" -f $magic) }
$imageBase = [uint32](Read-U32 ($opt+28))
$sectionTable = $opt + $sizeOpt

$sections=@()
for($i=0;$i -lt $numSections;$i++){
    $s=$sectionTable+($i*40)
    $nameBytes=$data[$s..($s+7)]
    $name=([Text.Encoding]::ASCII.GetString($nameBytes)).Trim([char]0)
    $sections += [pscustomobject]@{
        Name=$name
        VirtualSize=[uint32](Read-U32 ($s+8))
        VirtualAddress=[uint32](Read-U32 ($s+12))
        RawSize=[uint32](Read-U32 ($s+16))
        RawOffset=[uint32](Read-U32 ($s+20))
    }
}

function FileOffset-To-Rva([int]$FileOffset) {
    foreach($s in $sections){
        $start=[int64]$s.RawOffset
        $end=$start+[int64]$s.RawSize
        if($FileOffset -ge $start -and $FileOffset -lt $end){
            return [uint32]($s.VirtualAddress + ($FileOffset - $s.RawOffset))
        }
    }
    return $null
}

$targets=@(
    "/localprofile",
    "localprofile",
    "credits_full_sync",
    "credits_partial_sync",
    "hardcurrency_full_sync",
    "hardcurrency_partial_sync",
    "playerCachedHardCurrency",
    "creditsEarnedToday"
)

Write-Host "Mapping high-value profile/sync strings in AMS.exe..." -ForegroundColor Cyan

$rows=@()
foreach($target in $targets){
    $encodings=@(
        [pscustomobject]@{Name="ASCII";Bytes=[Text.Encoding]::ASCII.GetBytes($target)},
        [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($target)}
    )
    foreach($enc in $encodings){
        $hits=Find-Bytes $data $enc.Bytes
        foreach($hit in $hits){
            $rva=FileOffset-To-Rva $hit
            $va=$null
            $absRefs=@()
            $rvaRefs=@()
            if($null -ne $rva){
                $va=[uint32]($imageBase+$rva)
                $absRefs=Find-Bytes $data ([BitConverter]::GetBytes([uint32]$va))
                $rvaRefs=Find-Bytes $data ([BitConverter]::GetBytes([uint32]$rva))
            }
            $rows += [pscustomobject]@{
                String=$target
                Encoding=$enc.Name
                StringFileOffset=("0x{0:X8}" -f $hit)
                RVA=if($null -ne $rva){("0x{0:X8}" -f $rva)}else{""}
                VA=if($null -ne $va){("0x{0:X8}" -f $va)}else{""}
                AbsoluteXrefs=(($absRefs | ForEach-Object { "0x{0:X8}" -f $_ }) -join ";")
                RvaXrefs=(($rvaRefs | ForEach-Object { "0x{0:X8}" -f $_ }) -join ";")
                StringHexWindow=Hex-Window $hit 16 64
            }
        }
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "ams-profile-string-xrefs.csv")
Write-Host ("AMS mapping complete: {0} string hits." -f $rows.Count) -ForegroundColor Green

# Write compact candidate windows around xrefs.
$xrefLines=@()
foreach($r in $rows){
    foreach($cell in @($r.AbsoluteXrefs,$r.RvaXrefs)){
        if([string]::IsNullOrWhiteSpace($cell)){continue}
        foreach($x in $cell.Split(";")){
            if([string]::IsNullOrWhiteSpace($x)){continue}
            $off=[Convert]::ToInt32($x.Substring(2),16)
            $xrefLines += "String=$($r.String) Encoding=$($r.Encoding) Xref=$x"
            $xrefLines += "Hex=" + (Hex-Window $off 48 96)
            $xrefLines += "------------------------------------------------------------"
        }
    }
}
$xrefLines | Set-Content -LiteralPath (Join-Path $out "ams-profile-xref-windows.txt") -Encoding UTF8

Write-Host "Scanning small text/config files..." -ForegroundColor Cyan

# Profile-related plain-text config hits from the registered package tree.
$textExt=@(".json",".xml",".txt",".ini",".cfg",".csv",".manifest")
$configHits=@()
Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $textExt -contains $_.Extension.ToLowerInvariant() -and $_.Length -lt 10MB } |
    ForEach-Object {
        $f=$_
        try {
            $matches=Select-String -LiteralPath $f.FullName -Pattern "localprofile|profile|login|account|sync|online|offline" -AllMatches -ErrorAction Stop
            foreach($m in $matches){
                $configHits += [pscustomobject]@{
                    File=$f.FullName.Substring($GameRoot.Length).TrimStart("\")
                    Line=$m.LineNumber
                    Text=$m.Line.Trim()
                }
            }
        } catch {}
    }
$configHits | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "package-profile-config-hits.csv")

Write-Host ("Config scan complete: {0} hits." -f $configHits.Count) -ForegroundColor Green
Write-Host "Inventorying package-local storage..." -ForegroundColor Cyan

# Inspect actual package-local storage created by the successful packaged boot.
$localStateRows=@()
if($pkg){
    $localRoot=Join-Path $env:LOCALAPPDATA ("Packages\"+$pkg.PackageFamilyName)
    if(Test-Path -LiteralPath $localRoot -PathType Container){
        Get-ChildItem -LiteralPath $localRoot -Recurse -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                $relative=$_.FullName.Substring($localRoot.Length).TrimStart("\")
                $localStateRows += [pscustomobject]@{
                    Path=$relative
                    Size=$_.Length
                    LastWriteTime=$_.LastWriteTime.ToString("o")
                    SHA256=if($_.Length -le 64MB){(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()}else{""}
                }
            }
        $localStateRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "package-local-storage-inventory.csv")
    }
}

Write-Host ("Local storage inventory complete: {0} files." -f $localStateRows.Count) -ForegroundColor Green

$summary=[ordered]@{
    Phase="Profile Phase 6 Probe"
    GameRoot=$GameRoot
    PackageFamilyName=if($pkg){$pkg.PackageFamilyName}else{""}
    AMS_SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath $ams).Hash.ToLowerInvariant()
    ProfileStringHits=$rows.Count
    ConfigHits=$configHits.Count
    PackageLocalFiles=$localStateRows.Count
}
$summary | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $out "PROFILE-PHASE6-SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE6-PROBE.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 6 PROBE COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("String/xref hits: {0}" -f $rows.Count)
Write-Host ("Config hits:      {0}" -f $configHits.Count)
Write-Host ("Local files:      {0}" -f $localStateRows.Count)
Write-Host ("ZIP:              {0}" -f $zip)
Write-Host ""
