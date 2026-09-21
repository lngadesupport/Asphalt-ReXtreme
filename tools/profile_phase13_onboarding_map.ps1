param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedPhase5 = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
if(-not (Test-Path -LiteralPath $GameRoot -PathType Container)){
    throw "Game root not found: $GameRoot"
}

function Get-Hash([string]$Path){
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$amsCandidates = @(
    (Join-Path $GameRoot "AMS.exe"),
    (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
    (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak")
)

$Ams = $null
foreach($candidate in $amsCandidates){
    if(-not (Test-Path -LiteralPath $candidate -PathType Leaf)){ continue }
    if((Get-Hash $candidate) -eq $ExpectedPhase5){
        $Ams = $candidate
        break
    }
}

if($null -eq $Ams){
    throw "Verified Phase 5 AMS not found. Refusing to analyze an unknown binary."
}

$Out = Join-Path $GameRoot "_PROFILE_PHASE13_ONBOARDING_MAP"
if(Test-Path -LiteralPath $Out){
    Remove-Item -LiteralPath $Out -Recurse -Force
}
New-Item -ItemType Directory -Path $Out -Force | Out-Null

[byte[]]$Data = [IO.File]::ReadAllBytes($Ams)

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
public static class ReXtremePhase13Search {
    public static int[] FindAll(byte[] haystack, byte[] needle) {
        if (haystack == null || needle == null || needle.Length == 0 || needle.Length > haystack.Length)
            return new int[0];
        var hits = new List<int>();
        int start = 0;
        byte first = needle[0];
        while (start <= haystack.Length - needle.Length) {
            int pos = Array.IndexOf<byte>(haystack, first, start);
            if (pos < 0 || pos > haystack.Length - needle.Length)
                break;
            bool ok = true;
            for (int j = 1; j < needle.Length; j++) {
                if (haystack[pos + j] != needle[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok)
                hits.Add(pos);
            start = pos + 1;
        }
        return hits.ToArray();
    }
}
"@

function Find-Bytes([byte[]]$Haystack,[byte[]]$Needle){
    [ReXtremePhase13Search]::FindAll($Haystack,$Needle)
}

function U16([int]$Offset){
    [BitConverter]::ToUInt16($Data,$Offset)
}

function U32([int]$Offset){
    [BitConverter]::ToUInt32($Data,$Offset)
}

function Hex-Window([int]$Offset,[int]$Before=256,[int]$After=384){
    $start = [Math]::Max(0,$Offset-$Before)
    $end = [Math]::Min($Data.Length-1,$Offset+$After)
    (($Data[$start..$end] | ForEach-Object {$_.ToString("X2")}) -join " ")
}

function Find-Nearest-Prologue([int]$Offset){
    $start = [Math]::Max(0,$Offset-1536)
    for($i=$Offset;$i -ge $start;$i--){
        if($i+2 -lt $Data.Length -and
           $Data[$i] -eq 0x55 -and
           $Data[$i+1] -eq 0x8B -and
           $Data[$i+2] -eq 0xEC){
            return $i
        }
    }
    return -1
}

function Get-ControlFlow([int]$Center,[int]$Radius=192){
    $start = [Math]::Max(0,$Center-$Radius)
    $end = [Math]::Min($Data.Length-6,$Center+$Radius)
    $rows = @()

    for($i=$start;$i -le $end;$i++){
        $op = $Data[$i]

        if($op -ge 0x70 -and $op -le 0x7F){
            $rel = [int]$Data[$i+1]
            if($rel -ge 0x80){ $rel -= 0x100 }
            $dest = $i + 2 + $rel
            $rows += [pscustomobject]@{
                Offset = $i
                Kind = ("Jcc-{0:X2}" -f $op)
                Destination = $dest
                Delta = $i-$Center
            }
            $i++
            continue
        }

        if($op -eq 0x0F -and $Data[$i+1] -ge 0x80 -and $Data[$i+1] -le 0x8F){
            $rel = [BitConverter]::ToInt32($Data,$i+2)
            $dest = $i + 6 + $rel
            $rows += [pscustomobject]@{
                Offset = $i
                Kind = ("Jcc-0F{0:X2}" -f $Data[$i+1])
                Destination = $dest
                Delta = $i-$Center
            }
            $i += 5
            continue
        }

        if($op -eq 0xE8 -or $op -eq 0xE9){
            $rel = [BitConverter]::ToInt32($Data,$i+1)
            $dest = $i + 5 + $rel
            $rows += [pscustomobject]@{
                Offset = $i
                Kind = $(if($op -eq 0xE8){"CALL"}else{"JMP"})
                Destination = $dest
                Delta = $i-$Center
            }
            $i += 4
        }
    }

    return $rows
}

if($Data.Length -lt 0x200 -or $Data[0] -ne 0x4D -or $Data[1] -ne 0x5A){
    throw "AMS is not a valid MZ image."
}

$pe = [int](U32 0x3C)
if($Data[$pe] -ne 0x50 -or $Data[$pe+1] -ne 0x45){
    throw "PE signature missing."
}

$numSections = [int](U16 ($pe+6))
$sizeOpt = [int](U16 ($pe+20))
$opt = $pe+24
if((U16 $opt) -ne 0x10B){
    throw "Expected PE32/x86 AMS."
}

$imageBase = [uint32](U32 ($opt+28))
$sectionTable = $opt+$sizeOpt
$sections = @()

for($i=0;$i -lt $numSections;$i++){
    $s = $sectionTable + 40*$i
    $name = ([Text.Encoding]::ASCII.GetString($Data[$s..($s+7)])).Trim([char]0)
    $sections += [pscustomobject]@{
        Name = $name
        VA = [uint32](U32 ($s+12))
        VSize = [uint32](U32 ($s+8))
        Raw = [uint32](U32 ($s+20))
        RawSize = [uint32](U32 ($s+16))
    }
}

function File-To-Rva([int]$Offset){
    foreach($section in $sections){
        if($Offset -ge $section.Raw -and $Offset -lt ($section.Raw+$section.RawSize)){
            return [uint32]($section.VA + ($Offset-$section.Raw))
        }
    }
    return $null
}

function File-To-Va([int]$Offset){
    $rva = File-To-Rva $Offset
    if($null -eq $rva){ return $null }
    return [uint32]($imageBase+$rva)
}

$terms = @(
    "AGE",
    "GENDER",
    "PRIVACY",
    "EULA",
    "TERMS",
    "CONSENT",
    "BIRTH",
    "DATE_OF_BIRTH",
    "BIRTHDATE",
    "FIRST_RUN",
    "FIRST RUN",
    "ONBOARD",
    "PROFILE_INITIALIZED",
    "PROFILE SETUP",
    "STR_AGE",
    "STR_GENDER",
    "STR_PRIVACY",
    "STR_EULA",
    "STR_TERMS",
    "STR_CONSENT",
    "STR_ACCEPT",
    "STR_BUTTON_ACCEPT"
)

$rows = @()
$context = @()

foreach($term in $terms){
    foreach($encoding in @(
        [pscustomobject]@{Name="ASCII";Bytes=[Text.Encoding]::ASCII.GetBytes($term)},
        [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($term)}
    )){
        foreach($hit in @(Find-Bytes $Data $encoding.Bytes)){
            $rva = File-To-Rva $hit
            $va = File-To-Va $hit
            $xrefHits = @()

            if($null -ne $va){
                $xrefHits += @(Find-Bytes $Data ([BitConverter]::GetBytes([uint32]$va)))
            }
            if($null -ne $rva){
                $xrefHits += @(Find-Bytes $Data ([BitConverter]::GetBytes([uint32]$rva)))
            }
            $xrefHits = @($xrefHits | Sort-Object -Unique)

            $rows += [pscustomobject]@{
                Term = $term
                Encoding = $encoding.Name
                StringFileOffset = ("0x{0:X8}" -f $hit)
                RVA = $(if($null -ne $rva){("0x{0:X8}" -f $rva)}else{""})
                VA = $(if($null -ne $va){("0x{0:X8}" -f $va)}else{""})
                Xrefs = (($xrefHits | ForEach-Object {"0x{0:X8}" -f $_}) -join ";")
            }

            foreach($xref in $xrefHits){
                $prologue = Find-Nearest-Prologue $xref
                $context += "===== TERM=$term ENC=$($encoding.Name) XREF=0x$($xref.ToString('X8')) ====="
                $context += ("NearestPrologue={0}" -f $(if($prologue -ge 0){("0x{0:X8}" -f $prologue)}else{"(none)"}))
                $context += "HEX[-256,+384]"
                $context += Hex-Window $xref 256 384
                $context += "CONTROL-FLOW[-192,+192]"
                foreach($cf in @(Get-ControlFlow $xref 192)){
                    $context += ("0x{0:X8} {1} -> 0x{2:X8} delta={3}" -f $cf.Offset,$cf.Kind,$cf.Destination,$cf.Delta)
                }
                $context += "------------------------------------------------------------"
            }
        }
    }
}

$rows | Sort-Object Term,Encoding,StringFileOffset -Unique |
    Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $Out "ams-onboarding-string-xrefs.csv")

$context |
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Out "ams-onboarding-xref-context.txt")

$known = @(
    [pscustomobject]@{
        Name = "Native profile constructor"
        Offset = [Convert]::ToInt32("0069B7A0",16)
        Before = 512
        After = 3072
    },
    [pscustomobject]@{
        Name = "Startup profile state machine"
        Offset = [Convert]::ToInt32("0092B82A",16)
        Before = 512
        After = 2048
    }
)

$knownOut = @()
foreach($item in $known){
    $knownOut += "===== $($item.Name) FILE=0x$($item.Offset.ToString('X8')) ====="
    $knownOut += "HEX"
    $knownOut += Hex-Window $item.Offset $item.Before $item.After
    $knownOut += "CONTROL-FLOW"
    foreach($cf in @(Get-ControlFlow $item.Offset 1024)){
        $knownOut += ("0x{0:X8} {1} -> 0x{2:X8} delta={3}" -f $cf.Offset,$cf.Kind,$cf.Destination,$cf.Delta)
    }
    $knownOut += "------------------------------------------------------------"
}

$knownOut |
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Out "known-profile-state-windows.txt")

$resourceTerms = @(
    "ANTES DE COME",
    "PRECISAMOS SABER",
    "SUA IDADE",
    "ACEITAR",
    "HOMEM",
    "MULHER",
    "privacy",
    "consent",
    "gender",
    "birth",
    "EULA",
    "terms",
    "STR_AGE",
    "STR_GENDER",
    "STR_PRIVACY",
    "STR_EULA",
    "STR_TERMS",
    "STR_CONSENT"
)

$allowedExtensions = @(".pri",".xbf",".xml",".json",".txt",".bin",".dat",".loc",".res")
$resourceHits = @()

Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notlike "$Out*" -and
        $_.Length -gt 0 -and
        $_.Length -le 64MB -and
        ($allowedExtensions -contains $_.Extension.ToLowerInvariant())
    } |
    ForEach-Object {
        $file = $_
        try{
            [byte[]]$bytes = [IO.File]::ReadAllBytes($file.FullName)
            foreach($term in $resourceTerms){
                foreach($encoding in @(
                    [pscustomobject]@{Name="UTF8";Bytes=[Text.Encoding]::UTF8.GetBytes($term)},
                    [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($term)}
                )){
                    foreach($hit in @(Find-Bytes $bytes $encoding.Bytes)){
                        $resourceHits += [pscustomobject]@{
                            File = $file.FullName.Substring($GameRoot.Length).TrimStart("\")
                            Term = $term
                            Encoding = $encoding.Name
                            Offset = ("0x{0:X8}" -f $hit)
                        }
                    }
                }
            }
        }catch{}
    }

$resourceHits |
    Sort-Object File,Term,Encoding,Offset -Unique |
    Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $Out "package-onboarding-text-hits.csv")

$uniqueRows = @($rows | Sort-Object Term,Encoding,StringFileOffset -Unique)
$xrefCount = 0
foreach($row in $uniqueRows){
    if(-not [string]::IsNullOrWhiteSpace($row.Xrefs)){
        $xrefCount += @($row.Xrefs.Split(";") | Where-Object {$_}).Count
    }
}

$summary = [ordered]@{
    Phase = "13-onboarding-map"
    Mode = "read-only-targeted-analysis"
    SourceAMS = $Ams
    SourceAMS_SHA256 = Get-Hash $Ams
    VerifiedPhase5 = $true
    CandidateAMSStrings = $uniqueRows.Count
    DirectAMSXrefs = $xrefCount
    PackageTextHits = @($resourceHits).Count
    KnownWindows = @(
        "0x0069B7A0 native profile constructor",
        "0x0092B82A startup/profile state machine"
    )
    NextStep = "Patch only a confirmed configured-profile success state; do not hide onboarding UI."
}

$summary |
    ConvertTo-Json -Depth 6 |
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Out "PROFILE-PHASE13-ONBOARDING-MAP-SUMMARY.json")

$zip = Join-Path $GameRoot "PROFILE-PHASE13-ONBOARDING-MAP.zip"
if(Test-Path -LiteralPath $zip){
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 13 ONBOARDING MAP COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Read-only: True"
Write-Host "Verified Phase 5 source: True"
Write-Host ("Candidate AMS strings: {0}" -f $uniqueRows.Count)
Write-Host ("Direct AMS xrefs: {0}" -f $xrefCount)
Write-Host ("Package text hits: {0}" -f @($resourceHits).Count)
Write-Host ("ZIP: {0}" -f $zip)
Write-Host ""
