param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams=Join-Path $GameRoot "AMS.exe"
if(-not(Test-Path -LiteralPath $Ams)){throw "AMS.exe not found: $Ams"}

[byte[]]$d=[IO.File]::ReadAllBytes($Ams)
$fs=[IO.File]::OpenRead($Ams)
$br=New-Object IO.BinaryReader($fs)
try{
  $fs.Position=0x3C
  $pe=$br.ReadInt32()
  $fs.Position=$pe
  $sig=$br.ReadUInt32()
  if($sig -ne 0x00004550){throw ("Invalid PE signature at 0x{0:X8}" -f $pe)}

  $fs.Position=$pe+4
  $machine=$br.ReadUInt16()
  $sections=$br.ReadUInt16()

  $fs.Position=$pe+20
  $optSize=$br.ReadUInt16()

  $fs.Position=$pe+24
  $optMagic=$br.ReadUInt16()
  if($optMagic -ne 0x10B){
    throw ("Expected PE32 optional-header magic 0x10B, got 0x{0:X} (Machine=0x{1:X4}, PE=0x{2:X8})" -f $optMagic,$machine,$pe)
  }
  if($machine -ne 0x014C){
    throw ("Expected x86 Machine=0x014C, got 0x{0:X4}" -f $machine)
  }

  $fs.Position=$pe+24+28
  $imageBase=$br.ReadUInt32()

  $secOff=$pe+24+$optSize
  $sec=@()
  for($i=0;$i -lt $sections;$i++){
    $fs.Position=$secOff+40*$i
    $name=[Text.Encoding]::ASCII.GetString($br.ReadBytes(8)).Trim([char]0)
    $vsize=$br.ReadUInt32()
    $vaddr=$br.ReadUInt32()
    $rawSize=$br.ReadUInt32()
    $rawPtr=$br.ReadUInt32()
    $sec += [pscustomobject]@{Name=$name;VirtualSize=$vsize;VirtualAddress=$vaddr;RawSize=$rawSize;RawPointer=$rawPtr}
  }
}finally{$br.Dispose();$fs.Dispose()}

function FileToVA([int]$off){
  foreach($s in $sec){
    if($off -ge $s.RawPointer -and $off -lt ($s.RawPointer+$s.RawSize)){
      return [uint32]($imageBase+$s.VirtualAddress+($off-$s.RawPointer))
    }
  }
  return [uint32]0
}
function VAtoFile([uint32]$va){
  $rva=[uint32]($va-$imageBase)
  foreach($s in $sec){
    if($rva -ge $s.VirtualAddress -and $rva -lt ($s.VirtualAddress+$s.RawSize)){
      return [int]($s.RawPointer+($rva-$s.VirtualAddress))
    }
  }
  return -1
}
$latin1=[Text.Encoding]::GetEncoding(28591)
$raw1to1=$latin1.GetString($d)

function Find-BytePattern([byte[]]$needle){
  $hits=New-Object System.Collections.Generic.List[int]
  if($needle.Length -eq 0){return $hits.ToArray()}
  $pattern=$latin1.GetString($needle)
  $pos=0
  while($pos -le ($raw1to1.Length-$pattern.Length)){
    $idx=$raw1to1.IndexOf($pattern,$pos,[StringComparison]::Ordinal)
    if($idx -lt 0){break}
    $hits.Add($idx)
    $pos=$idx+1
  }
  return $hits.ToArray()
}

function HexWindow([int]$center,[int]$before=96,[int]$after=160){
  $start=[Math]::Max(0,$center-$before)
  $end=[Math]::Min($d.Length,$center+$after)
  $lines=New-Object System.Collections.Generic.List[string]
  for($o=$start;$o -lt $end;$o+=16){
    $n=[Math]::Min(16,$end-$o)
    $lines.Add(("0x{0:X8}: {1}" -f $o,(($d[$o..($o+$n-1)]|ForEach-Object{$_.ToString("X2")}) -join " ")))
  }
  return ($lines -join [Environment]::NewLine)
}

$targets=@(
  "http://127.0.0.1/public/api/",
  "http://pjsmmm-legacy.gameloft.com/",
  "http://201205igp.gameloft.com/",
  "gameoptions.gameloft.com",
  "gameoptions-staging.gameloft.com",
  "gllive.gameloft.com",
  "vbeta.gameloft.com"
)

$outDir=Join-Path $GameRoot "_PROFILE_PHASE18_BACKEND_URL_MAP"
if(Test-Path $outDir){Remove-Item $outDir -Recurse -Force}
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
$report=New-Object System.Collections.Generic.List[object]
$txt=New-Object System.Collections.Generic.List[string]

$txt.Add("MapperVersion: phase18-v5-safe-finalize")
$txt.Add(("AMS SHA256: "+(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()))
$txt.Add(("PEOffset: 0x{0:X8}" -f $pe))
$txt.Add(("Machine: 0x{0:X4}" -f $machine))
$txt.Add(("OptionalMagic: 0x{0:X}" -f $optMagic))
$txt.Add(("ImageBase: 0x{0:X8}" -f $imageBase))
$txt.Add("")

foreach($t in $targets){
  Write-Host ("Scanning: {0}" -f $t) -ForegroundColor Cyan
  $needle=[Text.Encoding]::ASCII.GetBytes($t+[char]0)
  $hits=@(Find-BytePattern $needle)
  Write-Host ("  string hits: {0}" -f $hits.Count)
  foreach($off in $hits){
    $va=FileToVA $off
    $ptr=[BitConverter]::GetBytes([uint32]$va)
    $refs=@(Find-BytePattern $ptr)
    Write-Host ("  xrefs for 0x{0:X8}: {1}" -f $va,$refs.Count)
    $txt.Add(("===== STRING {0}" -f $t))
    $txt.Add(("FileOffset=0x{0:X8} VA=0x{1:X8} DirectRefs={2}" -f $off,$va,$refs.Count))
    $txt.Add("")
    foreach($r in $refs){
      $txt.Add(("--- REF file=0x{0:X8} va=0x{1:X8}" -f $r,(FileToVA $r)))
      $txt.Add((HexWindow $r 96 160))
      $txt.Add("")
      $report.Add([pscustomobject]@{
        String=$t
        StringFileOffset=("0x{0:X8}" -f $off)
        StringVA=("0x{0:X8}" -f $va)
        RefFileOffset=("0x{0:X8}" -f $r)
        RefVA=("0x{0:X8}" -f (FileToVA $r))
      })
    }
    $txt.Add("")
  }
}

$txt.ToArray()|Set-Content -LiteralPath (Join-Path $outDir "BACKEND-URL-XREFS.txt") -Encoding UTF8
$report.ToArray()|Export-Csv -LiteralPath (Join-Path $outDir "BACKEND-URL-XREFS.csv") -NoTypeInformation -Encoding UTF8
$summary=[ordered]@{
  Phase="18-backend-url-map"
  MapperVersion="phase18-v5-safe-finalize"
  AMS_SHA256=(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()
  PEOffset=("0x{0:X8}" -f $pe)
  Machine=("0x{0:X4}" -f $machine)
  OptionalMagic=("0x{0:X}" -f $optMagic)
  ImageBase=("0x{0:X8}" -f $imageBase)
  TargetCount=$targets.Count
  XrefCount=$report.Count
}
$summary|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $outDir "SUMMARY.json") -Encoding UTF8
$zip=Join-Path $GameRoot "PROFILE-PHASE18-BACKEND-URL-MAP.zip"
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 18 BACKEND URL MAP COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Xrefs: {0}" -f $report.Count)
Write-Host ("ZIP: {0}" -f $zip)
