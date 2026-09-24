param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($ProjectRoot)){
  $ProjectRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}else{
  $ProjectRoot=$ProjectRoot.Trim().Trim('"').TrimEnd('\')
  $ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
}

$manifest=Join-Path $ProjectRoot "_PACKAGE_PHASE5\AppxManifest.xml"
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){throw "Missing: $manifest"}

[xml]$mx=Get-Content -LiteralPath $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$p=Get-AppxPackage -Name $name | Sort-Object Version -Descending | Select-Object -First 1
if(-not$p){throw "Package not registered: $name"}

$trace=Join-Path $env:LOCALAPPDATA ("Packages\"+$p.PackageFamilyName+"\LocalState\CampaignEdition\GarageUiTrace.bin")
if(-not(Test-Path -LiteralPath $trace -PathType Leaf)){
  Write-Host "[TRACE] GarageUiTrace.bin not found."
  Write-Host ("Expected: "+$trace)
  exit 2
}

[byte[]]$d=[IO.File]::ReadAllBytes($trace)
$recSize=448
if(($d.Length % $recSize)-ne0){
  throw "GarageUiTrace.bin length is not a multiple of $recSize bytes: $($d.Length)"
}

function U32([int]$o){[BitConverter]::ToUInt32($d,$o)}
function H([uint32]$v){("0x{0:X8}" -f $v)}

$records=@()
for($o=0;$o-lt$d.Length;$o+=$recSize){
  if((U32 $o)-ne0x49555847){continue}
  $gs=@()
  for($i=0;$i-lt32;$i++){$gs += U32 ($o+32+$i*4)}
  $widget=@()
  $widgetStart=$o+32+32*4
  for($i=0;$i-lt40;$i++){$widget += U32 ($widgetStart+$i*4)}
  $button=@()
  $buttonStart=$widgetStart+40*4
  for($i=0;$i-lt32;$i++){$button += U32 ($buttonStart+$i*4)}

  $records += [pscustomobject]@{
    Index=($o/$recSize)
    Version=(U32 ($o+4))
    Step=(U32 ($o+8))
    GS=(U32 ($o+12))
    Widget=(U32 ($o+16))
    GSCompanion=(U32 ($o+20))
    BuildButton=(U32 ($o+24))
    BuildButtonControl=(U32 ($o+28))
    GSWords=$gs
    WidgetWords=$widget
    ButtonWords=$button
  }
}

if(-not$records){
  Write-Host "[TRACE] No valid Garage UI records."
  exit 3
}

Write-Host ""
Write-Host "================================================================"
Write-Host " CAMPAIGN GARAGE UI TRACE"
Write-Host "================================================================"
Write-Host ("File: "+$trace)
Write-Host ""

foreach($r in $records){
  Write-Host ("[SNAP] index={0} step={1} GS={2} GBBW={3} GS+360={4} Button={5} ButtonCtl={6}" -f $r.Index,$r.Step,(H $r.GS),(H $r.Widget),(H $r.GSCompanion),(H $r.BuildButton),(H $r.BuildButtonControl))
}

function ShowDiff($a,$b){
  Write-Host ""
  Write-Host ("--- DIFF step {0} -> {1} ---" -f $a.Step,$b.Step)

  $count=0
  for($i=0;$i-lt32;$i++){
    $av=[uint32]$a.GSWords[$i]
    $bv=[uint32]$b.GSWords[$i]
    if($av-ne$bv){
      $off=0x340+$i*4
      Write-Host ("GS   +0x{0:X3}: {1} -> {2}" -f $off,(H $av),(H $bv))
      $count++
    }
  }

  for($i=0;$i-lt40;$i++){
    $av=[uint32]$a.WidgetWords[$i]
    $bv=[uint32]$b.WidgetWords[$i]
    if($av-ne$bv){
      $off=$i*4
      $tag=""
      if($off-eq0x04){$tag="  [owner.object]"}
      elseif($off-eq0x08){$tag="  [owner.control]"}
      elseif($off-eq0x44){$tag="  [build-signal.object]"}
      elseif($off-eq0x48){$tag="  [build-signal.control]"}
      elseif($off-eq0x90){$tag="  [known build-area field]"}
      elseif($off-eq0x94){$tag="  [known build-area field]"}
      Write-Host ("GBBW +0x{0:X2}: {1} -> {2}{3}" -f $off,(H $av),(H $bv),$tag)
      $count++
    }
  }

  for($i=0;$i-lt32;$i++){
    $av=[uint32]$a.ButtonWords[$i]
    $bv=[uint32]$b.ButtonWords[$i]
    if($av-ne$bv){
      $off=$i*4
      Write-Host ("BUTTON+0x{0:X2}: {1} -> {2}" -f $off,(H $av),(H $bv))
      $count++
    }
  }

  if($count-eq0){Write-Host "(no dword changes in captured ranges)"}
}

for($i=1;$i-lt$records.Count;$i++){
  ShowDiff $records[$i-1] $records[$i]
}

Write-Host ""
Write-Host "Known steps:"
Write-Host "  10 = patched GBBW build callback entered"
Write-Host "  11 = GS_Garage owner resolved"
Write-Host "  20 = local build completion, before UI latch clear"
Write-Host "  21 = after GS/GBBW latch clear"
Write-Host "  22 = after explicit local frontend refresh"
Write-Host ""
