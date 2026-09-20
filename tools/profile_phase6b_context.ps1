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

$hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $ams).Hash.ToLowerInvariant()
if($hash -ne $ExpectedAMS){ throw "Unexpected AMS.exe SHA-256: $hash" }

$out=Join-Path $GameRoot "_PROFILE_PHASE6B_CONTEXT"
if(Test-Path -LiteralPath $out){Remove-Item -LiteralPath $out -Recurse -Force}
New-Item -ItemType Directory -Path $out -Force | Out-Null

[byte[]]$data=[IO.File]::ReadAllBytes($ams)

function U16([int]$o){[BitConverter]::ToUInt16($data,$o)}
function U32([int]$o){[BitConverter]::ToUInt32($data,$o)}
function HexWindow([int]$o,[int]$before,[int]$after){
    $s=[Math]::Max(0,$o-$before)
    $e=[Math]::Min($data.Length-1,$o+$after)
    return (($data[$s..$e] | ForEach-Object {$_.ToString("X2")}) -join " ")
}

$pe=[int](U32 0x3C)
$num=[int](U16 ($pe+6))
$sizeOpt=[int](U16 ($pe+20))
$opt=$pe+24
$imageBase=[uint32](U32 ($opt+28))
$secBase=$opt+$sizeOpt
$secs=@()
for($i=0;$i -lt $num;$i++){
    $s=$secBase+$i*40
    $name=([Text.Encoding]::ASCII.GetString($data[$s..($s+7)])).Trim([char]0)
    $secs += [pscustomobject]@{
        Name=$name
        VA=[uint32](U32 ($s+12))
        VSize=[uint32](U32 ($s+8))
        Raw=[uint32](U32 ($s+20))
        RawSize=[uint32](U32 ($s+16))
    }
}

function VaToFile([uint32]$va){
    $rva=[uint32]($va-$imageBase)
    foreach($s in $secs){
        $size=[Math]::Max([uint32]$s.VSize,[uint32]$s.RawSize)
        if($rva -ge $s.VA -and $rva -lt ($s.VA+$size)){
            return [int]($s.Raw+($rva-$s.VA))
        }
    }
    return -1
}

function ExtractAscii([int]$start,[int]$end,[int]$minLen=4){
    $rows=@()
    $i=[Math]::Max(0,$start)
    $end=[Math]::Min($data.Length-1,$end)
    while($i -le $end){
        if($data[$i] -ge 0x20 -and $data[$i] -le 0x7E){
            $j=$i
            while($j -le $end -and $data[$j] -ge 0x20 -and $data[$j] -le 0x7E){$j++}
            $len=$j-$i
            if($len -ge $minLen){
                $txt=[Text.Encoding]::ASCII.GetString($data,$i,$len)
                $rows += [pscustomobject]@{
                    FileOffset=("0x{0:X8}" -f $i)
                    Text=$txt
                }
            }
            $i=$j+1
        } else {$i++}
    }
    return $rows
}

# Exact known string VAs from Phase 6 xref evidence.
$stringVAs=@(
    [pscustomobject]@{Name="localprofile";VA=[uint32]0x0154FBF8},
    [pscustomobject]@{Name="/localprofile";VA=[uint32]0x0154FC08}
)

$stringContext=@()
foreach($s in $stringVAs){
    $fo=VaToFile $s.VA
    if($fo -lt 0){continue}
    $stringContext += "===== $($s.Name) VA=0x$($s.VA.ToString('X8')) FileOffset=0x$($fo.ToString('X8')) ====="
    $near=ExtractAscii ($fo-8192) ($fo+8192) 4 |
        Where-Object {$_.Text -match '(?i)profile|local|http|https|sync|login|account|user|server|save|cloud|auth|offline|online|session|device'}
    foreach($r in $near){
        $stringContext += "$($r.FileOffset)  $($r.Text)"
    }
    $stringContext += ""
}
$stringContext | Set-Content -LiteralPath (Join-Path $out "localprofile-neighbor-strings.txt") -Encoding UTF8

$xrefs=@(
    [pscustomobject]@{Name="/localprofile";Offset=0x0068FEA1},
    [pscustomobject]@{Name="localprofile-A";Offset=0x0069B961},
    [pscustomobject]@{Name="localprofile-B";Offset=0x006BADC5}
)
$xrefOut=@()
foreach($x in $xrefs){
    $xrefOut += "===== $($x.Name) XREF=0x$($x.Offset.ToString('X8')) ====="
    $xrefOut += "HEX[-512,+1024]"
    $xrefOut += HexWindow $x.Offset 512 1024
    $xrefOut += ""
}
$xrefOut | Set-Content -LiteralPath (Join-Path $out "localprofile-xref-large-windows.txt") -Encoding UTF8

# Tiny configuration lookup: only lines that explicitly mention localprofile.
$config=@()
Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {$_.Extension -match '^\.(json|xml|txt|ini|cfg|csv|manifest)$' -and $_.Length -lt 10MB} |
    ForEach-Object {
        try{
            $m=Select-String -LiteralPath $_.FullName -Pattern 'localprofile|/localprofile' -AllMatches -ErrorAction Stop
            foreach($hit in $m){
                $config += [pscustomobject]@{
                    File=$_.FullName.Substring($GameRoot.Length).TrimStart("\")
                    Line=$hit.LineNumber
                    Text=$hit.Line.Trim()
                }
            }
        }catch{}
    }
$config | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $out "localprofile-config-hits.csv")

$summary=[ordered]@{
    Phase="Profile Phase 6B Context"
    AMS_SHA256=$hash
    LocalprofileStringVA="0x0154FBF8"
    SlashLocalprofileStringVA="0x0154FC08"
    Xrefs=@("0x0068FEA1","0x0069B961","0x006BADC5")
    ConfigHits=$config.Count
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out "PROFILE-PHASE6B-SUMMARY.json") -Encoding UTF8

$zip=Join-Path $GameRoot "PROFILE-PHASE6B-CONTEXT.zip"
if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PROFILE PHASE 6B CONTEXT COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "AMS hash verified: True"
Write-Host "localprofile xrefs: 3"
Write-Host ("Config hits: {0}" -f $config.Count)
Write-Host ("ZIP: {0}" -f $zip)
Write-Host ""
