param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $game "AMS.PRE-PHASE20-LOCAL-GATES.exe"
$report=Join-Path $game "PHASE20-LOCAL-ONLINE-GATES.json"

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found: $ams"}

function Stop-TargetAMS([string]$TargetPath){
  $targetFull=[IO.Path]::GetFullPath($TargetPath)
  $found=$false
  foreach($p in @(Get-Process -Name "AMS" -ErrorAction SilentlyContinue)){
    $path=$null
    try{$path=$p.Path}catch{}
    if($path -and ([IO.Path]::GetFullPath($path) -ieq $targetFull)){
      $found=$true
      Write-Host ("Closing running AMS.exe PID {0}..." -f $p.Id) -ForegroundColor Yellow
      try{$null=$p.CloseMainWindow()}catch{}
      try{Wait-Process -Id $p.Id -Timeout 3 -ErrorAction SilentlyContinue}catch{}
      if(Get-Process -Id $p.Id -ErrorAction SilentlyContinue){
        Write-Host ("Forcing AMS.exe PID {0} to exit..." -f $p.Id) -ForegroundColor Yellow
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
        try{Wait-Process -Id $p.Id -Timeout 5 -ErrorAction SilentlyContinue}catch{}
      }
    }
  }
  return $found
}

function Wait-FileWritable([string]$Path,[int]$Seconds=15){
  $deadline=(Get-Date).AddSeconds($Seconds)
  $last=$null
  do{
    try{
      $s=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
      $s.Dispose()
      return
    }catch{
      $last=$_.Exception.Message
      Start-Sleep -Milliseconds 400
    }
  }while((Get-Date)-lt $deadline)
  throw ("AMS.exe is still locked after {0}s. Last error: {1}" -f $Seconds,$last)
}

$null=Stop-TargetAMS $ams
Wait-FileWritable $ams 15

function ReadB([string]$Path,[int]$Offset,[int]$Count){
  $fs=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try{
    $fs.Position=$Offset
    [byte[]]$b=New-Object byte[] $Count
    if($fs.Read($b,0,$Count) -ne $Count){throw ("Short read at 0x{0:X8}" -f $Offset)}
    return $b
  }finally{$fs.Dispose()}
}
function Same([byte[]]$a,[byte[]]$b){
  if($a.Length -ne $b.Length){return $false}
  for($i=0;$i -lt $a.Length;$i++){if($a[$i] -ne $b[$i]){return $false}}
  return $true
}
function Hex([byte[]]$b){(($b|ForEach-Object{$_.ToString("X2")}) -join " ")}
function Apply([IO.FileStream]$fs,[int]$off,[byte[]]$expected,[byte[]]$patched,[string]$name){
  $cur=ReadB $ams $off $expected.Length
  if(Same $cur $patched){
    return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Status="already-patched";Before=(Hex $cur);After=(Hex $patched)}
  }
  if(-not(Same $cur $expected)){
    throw ("Unexpected bytes for {0} at 0x{1:X8}. Expected [{2}], patched [{3}], found [{4}]" -f $name,$off,(Hex $expected),(Hex $patched),(Hex $cur))
  }
  $fs.Position=$off
  $fs.Write($patched,0,$patched.Length)
  return [pscustomobject]@{Name=$name;Offset=("0x{0:X8}" -f $off);Status="patched";Before=(Hex $expected);After=(Hex $patched)}
}

if(-not(Test-Path -LiteralPath $backup)){Copy-Item -LiteralPath $ams -Destination $backup -Force}
$before=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()

$sites=@(
  [pscustomobject]@{Name="gate-00809EAC";Offset=0x00809EAC;Expected=[byte[]]@(0x0F,0x85,0x8A,0x00,0x00,0x00);Patch=[byte[]]@(0xE9,0x8B,0x00,0x00,0x00,0x90)},
  [pscustomobject]@{Name="gate-008B543B";Offset=0x008B543B;Expected=[byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00);Patch=[byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)},
  [pscustomobject]@{Name="gate-00B24D5B";Offset=0x00B24D5B;Expected=[byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00);Patch=[byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)},
  [pscustomobject]@{Name="gate-00B44E9B";Offset=0x00B44E9B;Expected=[byte[]]@(0x0F,0x85,0xEB,0x00,0x00,0x00);Patch=[byte[]]@(0xE9,0xEC,0x00,0x00,0x00,0x90)}
)

$results=New-Object System.Collections.Generic.List[object]
Wait-FileWritable $ams 15
$fs=[IO.File]::Open($ams,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try{
  foreach($s in $sites){
    $results.Add((Apply $fs $s.Offset $s.Expected $s.Patch $s.Name))
  }

  # Keep the Phase 19 localhost route active if it is still original.
  $routeOff=0x00BAEA4B
  [byte[]]$routeOriginal=@(0x22,0x68,0x50,0xA2,0x59,0x01)
  [byte[]]$routeLocal=@(0x1C,0x68,0x40,0xC3,0x57,0x01)
  $results.Add((Apply $fs $routeOff $routeOriginal $routeLocal "pjsmmm-to-localhost"))
  $fs.Flush($true)
}finally{$fs.Dispose()}

foreach($s in $sites){
  if(-not(Same (ReadB $ams $s.Offset $s.Patch.Length) $s.Patch)){throw ("Verification failed: "+$s.Name)}
}
if(-not(Same (ReadB $ams 0x00BAEA4B 6) ([byte[]]@(0x1C,0x68,0x40,0xC3,0x57,0x01)))){throw "Verification failed: pjsmmm route"}

$after=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
  Phase="20-local-online-gates"
  GlobalIsOnline="unchanged-false"
  BeforeSHA256=$before
  AfterSHA256=$after
  Backup=$backup
  Patches=$results.ToArray()
}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8

Write-Host "Phase 20 patches verified." -ForegroundColor Green
$results|Format-Table Name,Offset,Status -AutoSize
Write-Host ("AMS SHA256: "+$after)
