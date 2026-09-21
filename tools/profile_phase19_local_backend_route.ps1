param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams=Join-Path $GameRoot "AMS.exe"
$Backup=Join-Path $GameRoot "AMS.PRE-PHASE19-LOCAL-BACKEND.exe"
$Report=Join-Path $GameRoot "PHASE19-LOCAL-BACKEND-PATCH.json"

if(-not(Test-Path -LiteralPath $Ams -PathType Leaf)){throw "AMS.exe not found: $Ams"}

$off=0x00BAEA4B
[byte[]]$expected=@(0x22,0x68,0x50,0xA2,0x59,0x01)
[byte[]]$patched =@(0x1C,0x68,0x40,0xC3,0x57,0x01)

function Read-Bytes([string]$Path,[int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try{
    $fs.Position=$Offset
    [byte[]]$b=New-Object byte[] $Count
    $n=$fs.Read($b,0,$Count)
    if($n -ne $Count){throw "Short read at offset 0x$($Offset.ToString('X8'))"}
    return $b
  }finally{$fs.Dispose()}
}
function Hex([byte[]]$b){return (($b|ForEach-Object{$_.ToString("X2")}) -join " ")}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length -ne $b.Length){return $false}
  for($i=0;$i -lt $a.Length;$i++){if($a[$i] -ne $b[$i]){return $false}}
  return $true
}

$beforeHash=(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()
$cur=Read-Bytes $Ams $off $expected.Length

$status=""
if(Same $cur $patched){
  $status="already-patched"
}elseif(Same $cur $expected){
  if(-not(Test-Path -LiteralPath $Backup)){
    Copy-Item -LiteralPath $Ams -Destination $Backup -Force
  }
  $fs=[IO.File]::Open($Ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{
    $fs.Position=$off
    $fs.Write($patched,0,$patched.Length)
    $fs.Flush($true)
  }finally{$fs.Dispose()}
  $verify=Read-Bytes $Ams $off $patched.Length
  if(-not(Same $verify $patched)){throw "Patch verification failed."}
  $status="patched"
}else{
  throw ("Unexpected bytes at 0x{0:X8}. Expected [{1}] or patched [{2}], found [{3}]." -f $off,(Hex $expected),(Hex $patched),(Hex $cur))
}

$afterHash=(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()
$r=[ordered]@{
  Phase="19-local-backend-route"
  Status=$status
  Offset=("0x{0:X8}" -f $off)
  OriginalBytes=(Hex $expected)
  PatchedBytes=(Hex $patched)
  OriginalUrl="http://pjsmmm-legacy.gameloft.com/"
  OriginalLength=34
  LocalUrl="http://127.0.0.1/public/api/"
  LocalLength=28
  LocalStringVA="0x0157C340"
  OriginalStringVA="0x0159A250"
  BeforeSHA256=$beforeHash
  AfterSHA256=$afterHash
  Backup=$Backup
}
$r|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $Report -Encoding UTF8
Write-Host ("Phase 19 patch: {0}" -f $status) -ForegroundColor Green
Write-Host ("AMS SHA256: {0}" -f $afterHash)
