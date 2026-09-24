param([string]$ProjectRoot="")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($ProjectRoot)){
  $ProjectRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}else{
  $ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
}

$manifest=Join-Path $ProjectRoot "_PACKAGE_PHASE5\AppxManifest.xml"
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){throw "Missing: $manifest"}

[xml]$mx=Get-Content -LiteralPath $manifest -Raw
$name=[string]$mx.Package.Identity.Name
$p=Get-AppxPackage -Name $name | Sort-Object Version -Descending | Select-Object -First 1
if(-not$p){throw "Package not registered: $name"}

$trace=Join-Path $env:LOCALAPPDATA ("Packages\"+$p.PackageFamilyName+"\LocalState\CampaignEdition\GarageTrace.bin")
if(-not(Test-Path -LiteralPath $trace -PathType Leaf)){
  Write-Host "[TRACE] GarageTrace.bin not found."
  Write-Host ("Expected: "+$trace)
  exit 2
}

[byte[]]$d=[IO.File]::ReadAllBytes($trace)
$recSize=44
if(($d.Length % $recSize)-ne0){
  throw "GarageTrace.bin length is not a multiple of $recSize bytes: $($d.Length)"
}

function U32([int]$o){[BitConverter]::ToUInt32($d,$o)}
function I32([int]$o){[BitConverter]::ToInt32($d,$o)}

$rows=@()
for($o=0;$o-lt$d.Length;$o+=$recSize){
  $magic=U32 $o
  if($magic-ne0x47545852){continue}
  $rows += [pscustomobject]@{
    Index=($o/$recSize)
    Version=(U32 ($o+4))
    Step=(U32 ($o+8))
    GS_Garage=("0x{0:X8}" -f (U32 ($o+12)))
    Holder=("0x{0:X8}" -f (U32 ($o+16)))
    Selected=("0x{0:X8}" -f (U32 ($o+20)))
    CarId=(I32 ($o+24))
    AcquireOk=(I32 ($o+28))
    Owned=(I32 ($o+32))
    CallbackStatus=(I32 ($o+36))
    Revision=(U32 ($o+40))
  }
}

if(-not$rows){
  Write-Host "[TRACE] No valid records."
  exit 3
}

Write-Host ""
Write-Host "============================================================"
Write-Host " CAMPAIGN GARAGE TRACE"
Write-Host "============================================================"
Write-Host ("File: "+$trace)
Write-Host ""
$rows | Format-Table -AutoSize

$last=$rows[-1]
Write-Host ""
Write-Host ("[LAST] step={0} car_id={1} acquire_ok={2} owned={3} callback_status={4} revision={5}" -f $last.Step,$last.CarId,$last.AcquireOk,$last.Owned,$last.CallbackStatus,$last.Revision)
