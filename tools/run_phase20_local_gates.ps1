param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Continue"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$tools=Join-Path $root "tools"
$backend=Join-Path $tools "rextreme_local_backend.ps1"
$launcherBackup=Join-Path $game "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$launcherLive=Join-Path $game "RUN-PACKAGE-PHASE5.cmd"
$logsRoot=Join-Path $game "_PHASE20_LOCAL_GATES_LOGS"
$session=Join-Path $logsRoot (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $session -Force|Out-Null
$log=Join-Path $session "phase20-runtime.log"
function L([string]$m){("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$m)|Tee-Object -FilePath $log -Append}

$launch=$null
if(Test-Path -LiteralPath $launcherBackup){$launch=$launcherBackup}
elseif(Test-Path -LiteralPath $launcherLive){$launch=$launcherLive}
if($null -eq $launch){throw "Game launcher not found."}
if(-not(Test-Path -LiteralPath $backend)){throw "Local backend missing."}

$bp=Start-Process powershell.exe -ArgumentList @("-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",$backend,"-OutputDir",$session) -PassThru -WindowStyle Hidden
L ("BackendPID="+$bp.Id)
Start-Sleep -Milliseconds 500

$existing=@(Get-Process AMS -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id)
$lp=Start-Process $env:ComSpec -ArgumentList @("/d","/c",('"{0}"' -f $launch)) -WorkingDirectory $game -PassThru
L ("LauncherPID="+$lp.Id)

$pid2=$null
$deadline=(Get-Date).AddSeconds(60)
while((Get-Date)-lt $deadline -and $null -eq $pid2){
  $p=@(Get-Process AMS -ErrorAction SilentlyContinue|Where-Object{$existing -notcontains $_.Id})
  if($p.Count){$pid2=($p|Sort-Object StartTime -Descending|Select-Object -First 1).Id}
  else{Start-Sleep -Milliseconds 250}
}
if($null -eq $pid2){L "AMS not detected."}
else{
  L ("GamePID="+$pid2)
  while($true){try{$null=Get-Process -Id $pid2 -ErrorAction Stop}catch{break};Start-Sleep -Milliseconds 500}
  L "AMS exited."
}

New-Item -ItemType File -Path (Join-Path $session "STOP") -Force|Out-Null
try{Wait-Process -Id $bp.Id -Timeout 4 -ErrorAction SilentlyContinue}catch{}
try{if(Get-Process -Id $bp.Id -ErrorAction SilentlyContinue){Stop-Process -Id $bp.Id -Force}}catch{}

$backendLog=Join-Path $session "local-backend.log"
$req=0
if(Test-Path $backendLog){$req=@(Get-Content $backendLog|Where-Object{$_ -match '\] (HTTP|TLS) '}).Count}

[ordered]@{
  Phase="20-local-online-gates"
  GamePid=$pid2
  RequestsObserved=$req
  AMS_SHA256=(Get-FileHash -LiteralPath (Join-Path $game "AMS.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $session "SUMMARY.json") -Encoding UTF8

$zip=Join-Path $logsRoot ("PHASE20-"+(Split-Path $session -Leaf)+".zip")
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $session "*") -DestinationPath $zip -Force
Copy-Item $zip (Join-Path $logsRoot "LATEST-PHASE20.zip") -Force
Write-Host ""
Write-Host ("Backend requests observed: {0}" -f $req) -ForegroundColor Green
Write-Host ("Log: "+(Join-Path $logsRoot "LATEST-PHASE20.zip"))
