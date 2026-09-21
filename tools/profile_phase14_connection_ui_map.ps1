param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ExpectedPhase5="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"

function Get-Hash([string]$p){
    (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Hex([byte[]]$b){
    (($b|ForEach-Object{$_.ToString("X2")}) -join " ")
}
function Find-All([byte[]]$h,[byte[]]$n){
    $r=New-Object System.Collections.Generic.List[int]
    if($n.Length -eq 0 -or $n.Length -gt $h.Length){return $r}
    for($i=0;$i -le $h.Length-$n.Length;$i++){
        if($h[$i] -ne $n[0]){continue}
        $ok=$true
        for($j=1;$j -lt $n.Length;$j++){if($h[$i+$j] -ne $n[$j]){$ok=$false;break}}
        if($ok){$r.Add($i);$i += [Math]::Max(0,$n.Length-1)}
    }
    return $r
}
function Read-U16([byte[]]$b,[int]$o){[BitConverter]::ToUInt16($b,$o)}
function Read-U32([byte[]]$b,[int]$o){[BitConverter]::ToUInt32($b,$o)}

$candidates=@(
    (Join-Path $GameRoot "_PROFILE_PHASE13_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE12_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE11_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE10_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
    (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak"),
    (Join-Path $GameRoot "AMS.exe")
)
$Ams=$null
foreach($p in $candidates){
    if((Test-Path -LiteralPath $p -PathType Leaf) -and ((Get-Hash $p) -eq $ExpectedPhase5)){$Ams=$p;break}
}
if($null -eq $Ams){throw "Verified Phase 5 AMS not found."}

[byte[]]$d=[IO.File]::ReadAllBytes($Ams)

# Minimal PE32 mapping.
if([Text.Encoding]::ASCII.GetString($d,0,2) -ne "MZ"){throw "Not an MZ executable."}
$pe=[int](Read-U32 $d 0x3C)
if([Text.Encoding]::ASCII.GetString($d,$pe,4) -ne ("PE"+[char]0+[char]0)){throw "Invalid PE signature."}
$coff=$pe+4
$sections=[int](Read-U16 $d ($coff+2))
$optSize=[int](Read-U16 $d ($coff+16))
$opt=$coff+20
$magic=Read-U16 $d $opt
if($magic -ne 0x10B){throw "Expected PE32/x86."}
$imageBase=[uint32](Read-U32 $d ($opt+28))
$secBase=$opt+$optSize
$sec=@()
for($i=0;$i -lt $sections;$i++){
    $o=$secBase+40*$i
    $name=([Text.Encoding]::ASCII.GetString($d,$o,8)).Trim([char]0)
    $vsize=[uint32](Read-U32 $d ($o+8))
    $rva=[uint32](Read-U32 $d ($o+12))
    $rawSize=[uint32](Read-U32 $d ($o+16))
    $raw=[uint32](Read-U32 $d ($o+20))
    $sec += [pscustomobject]@{Name=$name;RVA=$rva;VSize=$vsize;Raw=$raw;RawSize=$rawSize}
}
function FileToRva([int]$fo){
    foreach($s in $sec){
        if($fo -ge $s.Raw -and $fo -lt ($s.Raw+$s.RawSize)){return [uint32]($s.RVA+($fo-$s.Raw))}
    }
    return $null
}
function RvaToFile([uint32]$rva){
    foreach($s in $sec){
        $span=[Math]::Max([uint32]$s.VSize,[uint32]$s.RawSize)
        if($rva -ge $s.RVA -and $rva -lt ($s.RVA+$span)){return [int]($s.Raw+($rva-$s.RVA))}
    }
    return $null
}

$out=Join-Path $GameRoot "_PROFILE_PHASE14_CONNECTION_UI_MAP"
if(Test-Path -LiteralPath $out){Remove-Item -LiteralPath $out -Recurse -Force}
New-Item -ItemType Directory -Path $out -Force|Out-Null

$terms=@(
"STR_POPUP_NO_INTERNET_DESCRIPTION","STR_POPUP_NO_INTERNET_TITLE",
"STR_NO_INTERNET","NO_INTERNET","INTERNET","NETWORK","CONNECTION",
"CONNECTIVITY","OFFLINE","RETRY","TRY_AGAIN","CONNECTION_FAILED",
"CONNECTION_LOST","CONNECTION_UNAVAILABLE","STR_POPUP_CONNECTION",
"STR_NETWORK","STR_OFFLINE"
)

$stringRows=@()
$xrefRows=@()
$pointerRows=@()
foreach($term in $terms){
    foreach($enc in @(
        [pscustomobject]@{Name="ASCII";Bytes=[Text.Encoding]::ASCII.GetBytes($term)},
        [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($term)}
    )){
        foreach($fo in @(Find-All $d $enc.Bytes)){
            $rva=FileToRva $fo
            if($null -eq $rva){continue}
            $va=[uint32]($imageBase+$rva)
            $stringRows += [pscustomobject]@{
                Term=$term;Encoding=$enc.Name;StringFileOffset=("0x{0:X8}" -f $fo)
                RVA=("0x{0:X8}" -f $rva);VA=("0x{0:X8}" -f $va)
            }

            $needle=[BitConverter]::GetBytes($va)
            foreach($pfo in @(Find-All $d $needle)){
                $prva=FileToRva $pfo
                if($null -eq $prva){continue}
                $pva=[uint32]($imageBase+$prva)
                $pointerRows += [pscustomobject]@{
                    Term=$term;Encoding=$enc.Name;StringVA=("0x{0:X8}" -f $va)
                    PointerFileOffset=("0x{0:X8}" -f $pfo);PointerVA=("0x{0:X8}" -f $pva)
                }

                # Direct code/data references to the pointer-table entry.
                $pneedle=[BitConverter]::GetBytes($pva)
                foreach($xfo in @(Find-All $d $pneedle)){
                    if($xfo -eq $pfo){continue}
                    $xrva=FileToRva $xfo
                    if($null -eq $xrva){continue}
                    $xrefRows += [pscustomobject]@{
                        Term=$term;Kind="PTR2";Encoding=$enc.Name
                        StringVA=("0x{0:X8}" -f $va);ViaVA=("0x{0:X8}" -f $pva)
                        XrefFileOffset=("0x{0:X8}" -f $xfo);XrefVA=("0x{0:X8}" -f ([uint32]($imageBase+$xrva)))
                    }
                }
            }

            # Direct references to string VA.
            foreach($xfo in @(Find-All $d ([BitConverter]::GetBytes($va)))){
                $xrva=FileToRva $xfo
                if($null -eq $xrva){continue}
                $xrefRows += [pscustomobject]@{
                    Term=$term;Kind="DIRECT";Encoding=$enc.Name
                    StringVA=("0x{0:X8}" -f $va);ViaVA=""
                    XrefFileOffset=("0x{0:X8}" -f $xfo);XrefVA=("0x{0:X8}" -f ([uint32]($imageBase+$xrva)))
                }
            }
        }
    }
}

$stringRows|Sort-Object Term,StringFileOffset -Unique|Export-Csv (Join-Path $out "ams-network-strings.csv") -NoTypeInformation -Encoding UTF8
$pointerRows|Sort-Object Term,PointerFileOffset -Unique|Export-Csv (Join-Path $out "ams-network-pointer-chain.csv") -NoTypeInformation -Encoding UTF8
$xrefRows|Sort-Object Term,XrefFileOffset -Unique|Export-Csv (Join-Path $out "ams-network-xrefs.csv") -NoTypeInformation -Encoding UTF8

# Context around every xref, capped to keep output focused.
$ctx=New-Object System.Collections.Generic.List[string]
foreach($x in @($xrefRows|Sort-Object XrefFileOffset -Unique)){
    $fo=[Convert]::ToInt32(($x.XrefFileOffset -replace '^0x',''),16)
    $start=[Math]::Max(0,$fo-192)
    $end=[Math]::Min($d.Length,$fo+320)
    $ctx.Add(("===== {0} {1} XREF={2} VA={3} =====" -f $x.Term,$x.Kind,$x.XrefFileOffset,$x.XrefVA))
    for($o=$start;$o -lt $end;$o+=16){
        $n=[Math]::Min(16,$end-$o)
        $ctx.Add(("0x{0:X8}: {1}" -f $o,(Hex $d[$o..($o+$n-1)])))
    }
    $ctx.Add("")
}
$ctx|Set-Content -LiteralPath (Join-Path $out "ams-network-xref-context.txt") -Encoding UTF8

# Known Phase 12 sites plus onboarding gates: capture enough context to compare shared popup builders.
$anchors=@(
0x004FBCF0,0x004FD6A5,0x0064A789,0x00689741,
0x006A1CE1,0x006A1CE7,0x006A1E03,0x006A1E09,
0x006A46DC,0x006A5EFC,0x006A6BCC,0x00809EB2,
0x008B5441,0x00B0CB4C,0x00B24D61,0x00B44EA1,0x00B6A0A0
)
$known=New-Object System.Collections.Generic.List[string]
foreach($a in $anchors){
    $known.Add(("===== ANCHOR 0x{0:X8} =====" -f $a))
    $start=[Math]::Max(0,$a-256);$end=[Math]::Min($d.Length,$a+384)
    for($o=$start;$o -lt $end;$o+=16){
        $n=[Math]::Min(16,$end-$o)
        $known.Add(("0x{0:X8}: {1}" -f $o,(Hex $d[$o..($o+$n-1)])))
    }
    $known.Add("")
}
$known|Set-Content -LiteralPath (Join-Path $out "known-network-sites-context.txt") -Encoding UTF8

# Search package resources for visible connection UI and likely localization keys.
$resTerms=@(
"SEM CONEXÃO","SEM CONEXAO","CONEXÃO INDISPONÍVEL","CONEXAO INDISPONIVEL",
"NOVAMENTE","FALHA DE CONEXÃO","FALHA DE CONEXAO","CONNECTION","NO_INTERNET",
"NETWORK","OFFLINE","RETRY","TRY AGAIN","TRY_AGAIN","INTERNET"
)
$resRows=@()
$files=Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Length -gt 0 -and $_.Length -le 128MB -and
        $_.FullName -notlike "$out*" -and
        ($_.Extension.ToLowerInvariant() -in @(".bin",".pri",".xbf",".xml",".json",".txt",".loc",".res",".dat"))
    }
foreach($f in $files){
    try{
        [byte[]]$b=[IO.File]::ReadAllBytes($f.FullName)
        foreach($term in $resTerms){
            foreach($enc in @(
                [pscustomobject]@{Name="UTF8";Bytes=[Text.Encoding]::UTF8.GetBytes($term)},
                [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($term)}
            )){
                foreach($hit in @(Find-All $b $enc.Bytes)){
                    $rel=$f.FullName.Substring($GameRoot.Length).TrimStart("\")
                    $resRows += [pscustomobject]@{File=$rel;Term=$term;Encoding=$enc.Name;Offset=("0x{0:X8}" -f $hit)}
                }
            }
        }
    }catch{}
}
$resRows|Sort-Object File,Offset,Term -Unique|Export-Csv (Join-Path $out "package-network-text-hits.csv") -NoTypeInformation -Encoding UTF8

# Persist current Phase13 hash/report if present.
$currentAms=Join-Path $GameRoot "AMS.exe"
$currentHash=if(Test-Path -LiteralPath $currentAms){Get-Hash $currentAms}else{""}
$phase13Report=Join-Path $GameRoot "PROFILE-PHASE13-LOCAL-ONBOARDING-REPORT.json"
if(Test-Path -LiteralPath $phase13Report){Copy-Item $phase13Report (Join-Path $out "PHASE13-REPORT.json") -Force}

$summary=[ordered]@{
    Phase="14-connection-ui-map"
    ReadOnly=$true
    SourceAMS=$Ams
    SourceAMS_SHA256=(Get-Hash $Ams)
    VerifiedPhase5=$true
    CurrentAMS_SHA256=$currentHash
    AMSNetworkStrings=@($stringRows).Count
    AMSNetworkPointerRefs=@($pointerRows).Count
    AMSNetworkXrefs=@($xrefRows).Count
    PackageNetworkTextHits=@($resRows).Count
    KnownAnchorsCaptured=$anchors.Count
    Goal="Find every connection-related popup family, including indirect string references, so Campaign Edition can suppress network-only UI without enabling obsolete remote services."
}
$summary|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $out "SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE14-CONNECTION-UI-MAP.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 14 - CONNECTION UI MAP COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Game modified: False"
Write-Host ("AMS network strings: {0}" -f @($stringRows).Count)
Write-Host ("AMS network xrefs: {0}" -f @($xrefRows).Count)
Write-Host ("Package network text hits: {0}" -f @($resRows).Count)
Write-Host ("Output: {0}" -f $zip)
Write-Host ""
