param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$logs=Join-Path $root "_PACKAGE_PHASE5\_PHASE19_LOCAL_BACKEND_LOGS"
$zip=Join-Path $logs "LATEST-PHASE19-LOCAL-BACKEND.zip"
$out=Join-Path $logs "LATEST-PHASE19-LOCAL-BACKEND-REPORT.txt"

if(-not(Test-Path -LiteralPath $zip -PathType Leaf)){throw "Phase 19 ZIP not found: $zip"}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$z=[IO.Compression.ZipFile]::OpenRead($zip)
$utf8=New-Object Text.UTF8Encoding($true)
$sw=New-Object IO.StreamWriter($out,$false,$utf8)

try{
  $sw.WriteLine("============================================================")
  $sw.WriteLine(" ReXtreme Phase 19 Local Backend - Consolidated Report")
  $sw.WriteLine("============================================================")
  $sw.WriteLine(("Generated: "+(Get-Date).ToString("o")))
  $sw.WriteLine(("ZIP: "+$zip))
  $sw.WriteLine("")
  foreach($e in ($z.Entries | Sort-Object FullName)){
    $sw.WriteLine("")
    $sw.WriteLine(("==================== "+$e.FullName+" ===================="))
    $sw.WriteLine(("SIZE="+$e.Length))
    $sw.WriteLine("")
    if($e.Length -eq 0){
      $sw.WriteLine("[EMPTY]")
      continue
    }
    $s=$e.Open()
    $sr=New-Object IO.StreamReader($s,[Text.Encoding]::UTF8,$true)
    try{$sw.WriteLine($sr.ReadToEnd())}
    finally{$sr.Dispose();$s.Dispose()}
  }
}finally{
  $sw.Dispose()
  $z.Dispose()
}
Write-Host ""
Write-Host "PHASE 19 REPORT READY" -ForegroundColor Green
Write-Host $out
