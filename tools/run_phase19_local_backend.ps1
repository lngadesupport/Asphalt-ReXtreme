param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Continue"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Tools=Join-Path $ProjectRoot "tools"
$Backend=Join-Path $Tools "rextreme_local_backend.ps1"
$Live=Join-Path $GameRoot "RUN-PACKAGE-PHASE5.cmd"
$BackupLauncher=Join-Path $GameRoot "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$LogsRoot=Join-Path $GameRoot "_PHASE19_LOCAL_BACKEND_LOGS"
$Session=Join-Path $LogsRoot (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $Session -Force|Out-Null
$main=Join-Path $Session "phase19-runtime.log"
function L([string]$m){("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$m)|Tee-Object -FilePath $main -Append}

$Original=$null
if(Test-Path -LiteralPath $BackupLauncher){$Original=$BackupLauncher}
elseif(Test-Path -LiteralPath $Live){
  $x=Get-Content -LiteralPath $Live -Raw -ErrorAction SilentlyContinue
  if($x -notmatch "REXTREME_RUNTIME_LOGGER_WRAPPER"){$Original=$Live}
}
if($null -eq $Original){throw "Original package launcher not found."}
if(-not(Test-Path -LiteralPath $Backend)){throw "Local backend script not found."}

$backendOut=Join-Path $Session "backend-stdout.log"
$backendErr=Join-Path $Session "backend-stderr.log"
$bp=Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",$Backend,"-OutputDir",$Session) -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
L ("BackendPID="+$bp.Id)
Start-Sleep -Milliseconds 600

$existing=@(Get-Process -Name "AMS" -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id)
$lp=Start-Process -FilePath $env:ComSpec -ArgumentList @("/d","/c",('"{0}"' -f $Original)) -WorkingDirectory $GameRoot -PassThru
L ("LauncherPID="+$lp.Id)

$gamePid=$null
$deadline=(Get-Date).AddSeconds(60)
while((Get-Date)-lt $deadline -and $null -eq $gamePid){
  $p=@(Get-Process -Name "AMS" -ErrorAction SilentlyContinue|Where-Object{$existing -notcontains $_.Id})
  if($p.Count -gt 0){$gamePid=($p|Sort-Object StartTime -Descending|Select-Object -First 1).Id;break}
  Start-Sleep -Milliseconds 250
}
if($null -eq $gamePid){
  L "ERROR AMS.exe not detected."
}else{
  L ("GamePID="+$gamePid)
  while($true){
    try{$null=Get-Process -Id $gamePid -ErrorAction Stop}catch{break}
    Start-Sleep -Milliseconds 500
  }
  L "AMS.exe exited."
}

New-Item -ItemType File -Path (Join-Path $Session "STOP") -Force|Out-Null
try{Wait-Process -Id $bp.Id -Timeout 4 -ErrorAction SilentlyContinue}catch{}
try{if(Get-Process -Id $bp.Id -ErrorAction SilentlyContinue){Stop-Process -Id $bp.Id -Force}}catch{}

$backendLog=Join-Path $Session "local-backend.log"
$requestCount=0
if(Test-Path $backendLog){
  $requestCount=@(Get-Content $backendLog|Where-Object{$_ -match '\] (HTTP|TLS) '}).Count
}
$summary=[ordered]@{
  Phase="19-local-backend-route"
  GamePid=$gamePid
  RequestsObserved=$requestCount
  BackendLog=$backendLog
  AMS_SHA256=(Get-FileHash -LiteralPath (Join-Path $GameRoot "AMS.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
}
$summary|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $Session "SUMMARY.json") -Encoding UTF8

$zip=Join-Path $LogsRoot ("PHASE19-LOCAL-BACKEND-"+(Split-Path $Session -Leaf)+".zip")
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $Session "*") -DestinationPath $zip -Force
Copy-Item -LiteralPath $zip -Destination (Join-Path $LogsRoot "LATEST-PHASE19-LOCAL-BACKEND.zip") -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 19 COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Backend requests observed: {0}" -f $requestCount)
Write-Host ("Latest log: {0}" -f (Join-Path $LogsRoot "LATEST-PHASE19-LOCAL-BACKEND.zip"))
