param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$OutDir=Join-Path $GameRoot "_PROFILE_PHASE18_BACKEND_URL_MAP"
$Txt=Join-Path $OutDir "BACKEND-URL-XREFS.txt"
$Csv=Join-Path $OutDir "BACKEND-URL-XREFS.csv"
$Summary=Join-Path $OutDir "SUMMARY.json"
$Zip=Join-Path $GameRoot "PROFILE-PHASE18-BACKEND-URL-MAP.zip"

if(-not(Test-Path -LiteralPath $Txt -PathType Leaf)){
  throw "BACKEND-URL-XREFS.txt not found. Run the corrected Phase 18 mapper."
}
if(-not(Test-Path -LiteralPath $Csv -PathType Leaf)){
  throw "BACKEND-URL-XREFS.csv not found. Run the corrected Phase 18 mapper."
}

$rows=@(Import-Csv -LiteralPath $Csv)
$ams=Join-Path $GameRoot "AMS.exe"
$sha=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$summary=[ordered]@{
  Phase="18-backend-url-map"
  MapperVersion="phase18-recovered-finalize"
  AMS_SHA256=$sha
  XrefCount=$rows.Count
  RecoveredFromExistingFiles=$true
  TextFile=$Txt
  CsvFile=$Csv
}
$summary|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $Summary -Encoding UTF8

if(Test-Path -LiteralPath $Zip){Remove-Item -LiteralPath $Zip -Force}
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $Zip -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 18 RECOVERED AND PACKAGED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Xrefs: {0}" -f $rows.Count)
Write-Host ("ZIP: {0}" -f $Zip)
Write-Host ""
