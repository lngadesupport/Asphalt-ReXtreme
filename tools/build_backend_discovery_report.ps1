param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$Root=Join-Path $ProjectRoot "_PACKAGE_PHASE5\_LOCAL_BACKEND_DISCOVERY"
if(-not(Test-Path -LiteralPath $Root -PathType Container)){
  throw "Discovery root not found: $Root"
}

$session=Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$temp=$null
if($null -eq $session){
  $zip=Join-Path $Root "LATEST-LOCAL-BACKEND-DISCOVERY.zip"
  if(-not(Test-Path -LiteralPath $zip -PathType Leaf)){
    throw "No discovery session folder or latest ZIP was found."
  }
  $temp=Join-Path $Root "_REPORT_EXTRACT"
  if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Recurse -Force}
  New-Item -ItemType Directory -Path $temp -Force|Out-Null
  Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force
  $session=Get-Item -LiteralPath $temp
}

$out=Join-Path $Root "LATEST-LOCAL-BACKEND-DISCOVERY-REPORT.txt"
$utf8=New-Object System.Text.UTF8Encoding($true)
$sw=New-Object System.IO.StreamWriter($out,$false,$utf8)

function W([string]$s=""){ $sw.WriteLine($s) }

try{
  W "============================================================"
  W " ReXtreme Local Backend Discovery - Consolidated Report"
  W "============================================================"
  W ("Generated: "+(Get-Date).ToString("o"))
  W ("Source: "+$session.FullName)
  W ""

  $order=@(
    "SUMMARY.json",
    "CANDIDATE-HOSTS.txt",
    "discovery-runtime.log",
    "local-backend.log",
    "backend-stdout.log",
    "backend-stderr.log",
    "launcher-stdout.log",
    "launcher-stderr.log",
    "STATIC-NETWORK-STRINGS.csv",
    "DNS-BEFORE.csv",
    "DNS-AFTER.csv"
  )

  $zero=@()
  $missing=@()

  foreach($name in $order){
    $p=Join-Path $session.FullName $name
    if(-not(Test-Path -LiteralPath $p -PathType Leaf)){
      $missing += $name
      continue
    }

    $fi=Get-Item -LiteralPath $p
    if($fi.Length -eq 0){
      $zero += $name
      continue
    }

    W ""
    W ("==================== "+$name+" ====================")
    W ("SIZE="+$fi.Length)
    W ""
    try{
      $content=Get-Content -LiteralPath $p -Raw -ErrorAction Stop
      W $content
    }catch{
      W ("[READ-ERROR] "+$_.Exception.Message)
    }
  }

  W ""
  W "==================== EMPTY FILES ===================="
  if($zero.Count -eq 0){W "(none)"}else{$zero|ForEach-Object{W $_}}

  W ""
  W "==================== MISSING FILES =================="
  if($missing.Count -eq 0){W "(none)"}else{$missing|ForEach-Object{W $_}}

  W ""
  W "==================== ALL FILE SIZES ================="
  Get-ChildItem -LiteralPath $session.FullName -File -ErrorAction SilentlyContinue |
    Sort-Object Name |
    ForEach-Object { W ("{0}    {1} bytes" -f $_.Name,$_.Length) }
}
finally{
  $sw.Dispose()
  if($temp -and (Test-Path -LiteralPath $temp)){
    Remove-Item -LiteralPath $temp -Recurse -Force
  }
}

$size=(Get-Item -LiteralPath $out).Length
Write-Host ""
Write-Host "============================================================"
Write-Host " CONSOLIDATED REPORT READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Report: {0}" -f $out)
Write-Host ("Size:   {0} bytes" -f $size)
Write-Host ""
