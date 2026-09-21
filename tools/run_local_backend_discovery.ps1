param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Continue"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Tools=Join-Path $ProjectRoot "tools"
$Ams=Join-Path $GameRoot "AMS.exe"
$Live=Join-Path $GameRoot "RUN-PACKAGE-PHASE5.cmd"
$Backup=Join-Path $GameRoot "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$Scanner=Join-Path $Tools "scan_backend_endpoints.ps1"
$Backend=Join-Path $Tools "rextreme_local_backend.ps1"
$Root=Join-Path $GameRoot "_LOCAL_BACKEND_DISCOVERY"
$Session=Join-Path $Root (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $Session -Force|Out-Null
$RunLog=Join-Path $Session "discovery-runtime.log"

function Log([string]$m){("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$m)|Tee-Object -FilePath $RunLog -Append}
function DnsRows{
  try{return @(Get-DnsClientCache -ErrorAction Stop | Select-Object Entry,Name,Data,Type,Status,Section,TimeToLive)}catch{return @()}
}

if(-not(Test-Path -LiteralPath $Ams)){throw "AMS.exe not found."}
if(-not(Test-Path -LiteralPath $Scanner)){throw "Scanner missing: $Scanner"}
if(-not(Test-Path -LiteralPath $Backend)){throw "Backend missing: $Backend"}

$Original=$null
if(Test-Path -LiteralPath $Backup){$Original=$Backup}
elseif(Test-Path -LiteralPath $Live){
  $txt=Get-Content -LiteralPath $Live -Raw -ErrorAction SilentlyContinue
  if($txt -notmatch "REXTREME_RUNTIME_LOGGER_WRAPPER"){$Original=$Live}
}
if($null -eq $Original){throw "Original package launcher not found."}

Log "ReXtreme Local Backend discovery starting."
Log ("AMS_SHA256="+(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant())
Log ("OriginalLauncher="+$Original)

$dnsBefore=DnsRows
$dnsBefore|Export-Csv -LiteralPath (Join-Path $Session "DNS-BEFORE.csv") -NoTypeInformation -Encoding UTF8
$beforeNames=@{}
foreach($r in $dnsBefore){if($r.Entry){$beforeNames[$r.Entry.ToLowerInvariant()]=$true};if($r.Name){$beforeNames[$r.Name.ToLowerInvariant()]=$true}}

Log "Scanning package for URLs/domains..."
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Scanner -ProjectRoot $ProjectRoot -OutputDir $Session
Log "Static scan complete."

$backendOut=Join-Path $Session "backend-stdout.log"
$backendErr=Join-Path $Session "backend-stderr.log"
$bp=Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",$Backend,"-OutputDir",$Session) -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
Log ("BackendPID="+$bp.Id)
Start-Sleep -Milliseconds 500

$existing=@(Get-Process -Name "AMS" -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id)
$launcherOut=Join-Path $Session "launcher-stdout.log"
$launcherErr=Join-Path $Session "launcher-stderr.log"
$lp=Start-Process -FilePath $env:ComSpec -ArgumentList @("/d","/c",('"{0}"' -f $Original)) -WorkingDirectory $GameRoot -RedirectStandardOutput $launcherOut -RedirectStandardError $launcherErr -PassThru
Log ("LauncherPID="+$lp.Id)

$gamePid=$null
$deadline=(Get-Date).AddSeconds(60)
while((Get-Date)-lt $deadline -and $null -eq $gamePid){
  $p=@(Get-Process -Name "AMS" -ErrorAction SilentlyContinue|Where-Object{$existing -notcontains $_.Id})
  if($p.Count -gt 0){$gamePid=($p|Sort-Object StartTime -Descending|Select-Object -First 1).Id;break}
  Start-Sleep -Milliseconds 250
}
if($null -eq $gamePid){
  $p=@(Get-Process -Name "AMS" -ErrorAction SilentlyContinue|Sort-Object StartTime -Descending)
  if($p.Count -gt 0){$gamePid=$p[0].Id}
}
if($null -eq $gamePid){Log "ERROR: AMS.exe was not detected."}
else{
  Log ("GamePID="+$gamePid)
  $seenNet=@{}
  $newDns=@{}
  while($true){
    try{$gp=Get-Process -Id $gamePid -ErrorAction Stop}catch{break}
    try{
      foreach($n in @(Get-NetTCPConnection -OwningProcess $gamePid -ErrorAction SilentlyContinue)){
        $k=("TCP|{0}|{1}|{2}" -f $n.RemoteAddress,$n.RemotePort,$n.State)
        if(-not $seenNet.ContainsKey($k)){
          $seenNet[$k]=$true
          Log ("NET "+$k)
        }
      }
      foreach($n in @(Get-NetUDPEndpoint -OwningProcess $gamePid -ErrorAction SilentlyContinue)){
        $k=("UDP|{0}|{1}" -f $n.LocalAddress,$n.LocalPort)
        if(-not $seenNet.ContainsKey($k)){
          $seenNet[$k]=$true
          Log ("NET "+$k)
        }
      }
    }catch{}
    foreach($r in (DnsRows)){
      foreach($nm in @($r.Entry,$r.Name)){
        if([string]::IsNullOrWhiteSpace($nm)){continue}
        $x=$nm.ToLowerInvariant()
        if(-not $beforeNames.ContainsKey($x) -and -not $newDns.ContainsKey($x)){
          $newDns[$x]=$true
          Log ("DNS-NEW "+$x)
        }
      }
    }
    Start-Sleep -Milliseconds 750
  }
  Log "AMS.exe exited."
}

New-Item -ItemType File -Path (Join-Path $Session "STOP") -Force|Out-Null
try{Wait-Process -Id $bp.Id -Timeout 5 -ErrorAction SilentlyContinue}catch{}
try{if(Get-Process -Id $bp.Id -ErrorAction SilentlyContinue){Stop-Process -Id $bp.Id -Force}}catch{}

$dnsAfter=DnsRows
$dnsAfter|Export-Csv -LiteralPath (Join-Path $Session "DNS-AFTER.csv") -NoTypeInformation -Encoding UTF8

$candidates=New-Object System.Collections.Generic.HashSet[string]([StringComparer]::OrdinalIgnoreCase)
foreach($r in $dnsAfter){
  foreach($nm in @($r.Entry,$r.Name)){
    if([string]::IsNullOrWhiteSpace($nm)){continue}
    $x=$nm.ToLowerInvariant().TrimEnd('.')
    if(-not $beforeNames.ContainsKey($x) -and $x -match '^[a-z0-9.-]+\.[a-z]{2,}$'){[void]$candidates.Add($x)}
  }
}
$static=Join-Path $Session "STATIC-NETWORK-STRINGS.csv"
if(Test-Path $static){
  foreach($r in (Import-Csv -LiteralPath $static)){
    $v=[string]$r.Value
    foreach($m in [regex]::Matches($v,'(?i)(?:[a-z0-9-]+\.)+[a-z]{2,}')){
      [void]$candidates.Add($m.Value.ToLowerInvariant())
    }
  }
}
$candidates|Sort-Object|Set-Content -LiteralPath (Join-Path $Session "CANDIDATE-HOSTS.txt") -Encoding UTF8

$summary=[ordered]@{
  Phase="17-local-backend-discovery"
  Session=$Session
  GamePid=$gamePid
  CandidateHostCount=$candidates.Count
  BackendLog=(Join-Path $Session "local-backend.log")
  CandidateHosts=(Join-Path $Session "CANDIDATE-HOSTS.txt")
  StaticStrings=(Join-Path $Session "STATIC-NETWORK-STRINGS.csv")
}
$summary|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $Session "SUMMARY.json") -Encoding UTF8

$zip=Join-Path $Root ("LOCAL-BACKEND-DISCOVERY-"+(Split-Path $Session -Leaf)+".zip")
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $Session "*") -DestinationPath $zip -Force
Copy-Item -LiteralPath $zip -Destination (Join-Path $Root "LATEST-LOCAL-BACKEND-DISCOVERY.zip") -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " ReXtreme Local Backend discovery complete" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Candidates: {0}" -f $candidates.Count)
Write-Host ("ZIP: {0}" -f $zip)
Write-Host ("Latest: {0}" -f (Join-Path $Root "LATEST-LOCAL-BACKEND-DISCOVERY.zip"))
