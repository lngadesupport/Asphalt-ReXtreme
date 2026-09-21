param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [Parameter(Mandatory=$true)][string]$OriginalLauncher
)

$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams = Join-Path $GameRoot "AMS.exe"
$OriginalLauncher = (Resolve-Path -LiteralPath $OriginalLauncher).Path
$LogsRoot = Join-Path $GameRoot "_RUNTIME_LOGS"
$SessionId = Get-Date -Format "yyyyMMdd-HHmmss"
$SessionDir = Join-Path $LogsRoot $SessionId
$MainLog = Join-Path $SessionDir "runtime.log"
$LauncherOut = Join-Path $SessionDir "launcher-stdout.log"
$LauncherErr = Join-Path $SessionDir "launcher-stderr.log"
$EventsLog = Join-Path $SessionDir "windows-events.log"
$SummaryPath = Join-Path $SessionDir "SUMMARY.json"

New-Item -ItemType Directory -Path $SessionDir -Force | Out-Null
$script:Writer = New-Object System.IO.StreamWriter($MainLog,$false,[Text.UTF8Encoding]::new($true))
$script:Writer.AutoFlush = $true

function Write-Log([string]$Category,[string]$Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $line = "[{0}] [{1}] {2}" -f $ts,$Category,$Message
    $script:Writer.WriteLine($line)
    Write-Host $line
}

function Get-SafeHash([string]$Path) {
    try {
        if(Test-Path -LiteralPath $Path -PathType Leaf) {
            return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } catch {}
    return ""
}

function Resolve-LocalState {
    $packages = Join-Path $env:LOCALAPPDATA "Packages"
    if(-not (Test-Path -LiteralPath $packages)){ return $null }
    $dirs = Get-ChildItem -LiteralPath $packages -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*AsphaltXtreme*" -or $_.Name -like "A278AB0D.AsphaltXtreme*" }
    foreach($d in $dirs) {
        $ls = Join-Path $d.FullName "LocalState"
        if(Test-Path -LiteralPath $ls -PathType Container){ return $ls }
    }
    return $null
}

function Get-LocalStateSnapshot([string]$Root) {
    $map = @{}
    if([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root)){ return $map }
    Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($Root.Length).TrimStart('\')
        $map[$rel] = [pscustomobject]@{ Size=$_.Length; LastWriteUtc=$_.LastWriteTimeUtc.ToString("o") }
    }
    return $map
}

function Compare-LocalState($Old,$New) {
    foreach($k in @($New.Keys)) {
        if(-not $Old.ContainsKey($k)) {
            Write-Log "FILE" ("CREATED LocalState\{0} size={1}" -f $k,$New[$k].Size)
        } elseif($Old[$k].Size -ne $New[$k].Size -or $Old[$k].LastWriteUtc -ne $New[$k].LastWriteUtc) {
            Write-Log "FILE" ("CHANGED LocalState\{0} size={1}" -f $k,$New[$k].Size)
        }
    }
    foreach($k in @($Old.Keys)) {
        if(-not $New.ContainsKey($k)) { Write-Log "FILE" ("DELETED LocalState\{0}" -f $k) }
    }
}

function Get-NetworkState([int]$Pid) {
    $items = New-Object System.Collections.Generic.List[string]
    try {
        Get-NetTCPConnection -OwningProcess $Pid -ErrorAction SilentlyContinue | ForEach-Object {
            $items.Add(("TCP {0}:{1} -> {2}:{3} state={4}" -f $_.LocalAddress,$_.LocalPort,$_.RemoteAddress,$_.RemotePort,$_.State))
        }
    } catch {}
    try {
        Get-NetUDPEndpoint -OwningProcess $Pid -ErrorAction SilentlyContinue | ForEach-Object {
            $items.Add(("UDP {0}:{1}" -f $_.LocalAddress,$_.LocalPort))
        }
    } catch {}
    return @($items | Sort-Object -Unique)
}

function Write-ModuleSnapshot([int]$Pid) {
    try {
        $p = Get-Process -Id $Pid -ErrorAction Stop
        foreach($m in @($p.Modules)) {
            try { Write-Log "MODULE" ("{0} | {1}" -f $m.ModuleName,$m.FileName) } catch {}
        }
    } catch {
        Write-Log "MODULE" ("Module enumeration unavailable: {0}" -f $_.Exception.Message)
    }
}

function Collect-WindowsEvents([datetime]$StartTime) {
    $end = Get-Date
    $logs = @("Application","Microsoft-Windows-AppModel-Runtime/Admin","Microsoft-Windows-TWinUI/Operational")
    $sw = New-Object System.IO.StreamWriter($EventsLog,$false,[Text.UTF8Encoding]::new($true))
    try {
        foreach($logName in $logs) {
            try {
                $events = Get-WinEvent -FilterHashtable @{LogName=$logName;StartTime=$StartTime;EndTime=$end} -ErrorAction Stop | Where-Object {
                    ($_.Message -match "(?i)AMS\.exe|Asphalt.?Xtreme|A278AB0D\.AsphaltXtreme") -or
                    ($_.ProviderName -match "(?i)Application Error|Windows Error Reporting|AppModel|TWinUI")
                } | Select-Object -First 500
                foreach($ev in $events) {
                    $msg = ($ev.Message -replace [Environment]::NewLine," | ")
                    $sw.WriteLine(("[{0:o}] [{1}] ID={2} Level={3} {4}" -f $ev.TimeCreated,$ev.ProviderName,$ev.Id,$ev.LevelDisplayName,$msg))
                }
            } catch {
                $sw.WriteLine(("[EVENTLOG-ERROR] {0}: {1}" -f $logName,$_.Exception.Message))
            }
        }
    } finally {
        $sw.Dispose()
    }
}

$startTime = Get-Date
$localState = Resolve-LocalState
$initialSnapshot = Get-LocalStateSnapshot $localState
$lastSnapshot = $initialSnapshot
$lastNetwork = @()
$gamePid = $null

try {
    Write-Log "SESSION" ("SessionId={0}" -f $SessionId)
    Write-Log "SESSION" ("ProjectRoot={0}" -f $ProjectRoot)
    Write-Log "SESSION" ("GameRoot={0}" -f $GameRoot)
    Write-Log "SESSION" ("OriginalLauncher={0}" -f $OriginalLauncher)
    Write-Log "SESSION" ("AMS_SHA256={0}" -f (Get-SafeHash $Ams))
    Write-Log "SESSION" ("OS={0}" -f [Environment]::OSVersion.VersionString)
    Write-Log "SESSION" ("PowerShell={0}" -f $PSVersionTable.PSVersion)
    Write-Log "SESSION" ("LocalState={0}" -f $(if($localState){$localState}else{"NOT_FOUND"}))
    Write-Log "SESSION" ("InitialLocalStateFiles={0}" -f $initialSnapshot.Count)

    $existing = @(Get-Process -Name "AMS" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    Write-Log "LAUNCH" ("Preexisting AMS PIDs={0}" -f (($existing -join ",") -replace '^$','none'))

    $launchArgs = '/d /c ""{0}""' -f $OriginalLauncher
    $launcherProcess = Start-Process -FilePath $env:ComSpec -ArgumentList $launchArgs -WorkingDirectory $GameRoot -RedirectStandardOutput $LauncherOut -RedirectStandardError $LauncherErr -PassThru
    Write-Log "LAUNCH" ("Launcher cmd PID={0}" -f $launcherProcess.Id)

    $deadline = (Get-Date).AddSeconds(45)
    while((Get-Date) -lt $deadline -and $null -eq $gamePid) {
        $candidates = @(Get-Process -Name "AMS" -ErrorAction SilentlyContinue | Where-Object { $existing -notcontains $_.Id })
        if($candidates.Count -gt 0) {
            $gamePid = ($candidates | Sort-Object StartTime -Descending | Select-Object -First 1).Id
            break
        }
        Start-Sleep -Milliseconds 250
    }

    if($null -eq $gamePid) {
        $fallback = @(Get-Process -Name "AMS" -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending)
        if($fallback.Count -gt 0){ $gamePid = $fallback[0].Id }
    }

    if($null -eq $gamePid) {
        Write-Log "ERROR" "AMS.exe was not detected within the launch window."
    } else {
        Write-Log "PROCESS" ("AMS started PID={0}" -f $gamePid)
        try {
            $p = Get-Process -Id $gamePid -ErrorAction Stop
            Write-Log "PROCESS" ("StartTime={0:o} Path={1}" -f $p.StartTime,$p.Path)
        } catch {}
        Write-ModuleSnapshot $gamePid

        $tick=0
        while($true) {
            try { $p = Get-Process -Id $gamePid -ErrorAction Stop } catch { break }

            if(($tick % 2) -eq 0) {
                try {
                    Write-Log "PROCESS" ("pid={0} cpu={1:N2}s ws={2:N1}MB private={3:N1}MB handles={4} threads={5}" -f $gamePid,$p.CPU,($p.WorkingSet64/1MB),($p.PrivateMemorySize64/1MB),$p.HandleCount,$p.Threads.Count)
                } catch {}
            }

            $network = @(Get-NetworkState $gamePid)
            $netKey = $network -join "|"
            $oldNetKey = $lastNetwork -join "|"
            if($netKey -ne $oldNetKey) {
                foreach($n in $network){ Write-Log "NETWORK" $n }
                if($network.Count -eq 0 -and $lastNetwork.Count -gt 0){ Write-Log "NETWORK" "No active sockets." }
                $lastNetwork = $network
            }

            if($localState) {
                $snap = Get-LocalStateSnapshot $localState
                Compare-LocalState $lastSnapshot $snap
                $lastSnapshot = $snap
            }

            $tick++
            Start-Sleep -Seconds 1
        }
        Write-Log "PROCESS" ("AMS PID={0} exited." -f $gamePid)
    }

    if($localState) {
        $finalSnapshot = Get-LocalStateSnapshot $localState
        Compare-LocalState $lastSnapshot $finalSnapshot
        foreach($rel in @($finalSnapshot.Keys | Sort-Object)) {
            $full = Join-Path $localState $rel
            Write-Log "FINALFILE" ("LocalState\{0} size={1} sha256={2}" -f $rel,$finalSnapshot[$rel].Size,(Get-SafeHash $full))
        }
    }

    Write-Log "EVENT" "Collecting Windows event logs..."
    Collect-WindowsEvents $startTime
    $endTime = Get-Date
    $summary = [ordered]@{
        SessionId=$SessionId
        StartTime=$startTime.ToString("o")
        EndTime=$endTime.ToString("o")
        DurationSeconds=[Math]::Round(($endTime-$startTime).TotalSeconds,3)
        GamePid=$gamePid
        AMS_SHA256=(Get-SafeHash $Ams)
        LocalState=$localState
        InitialLocalStateFiles=$initialSnapshot.Count
        FinalLocalStateFiles=$(if($localState){(Get-LocalStateSnapshot $localState).Count}else{0})
        RuntimeLog=$MainLog
        LauncherStdout=$LauncherOut
        LauncherStderr=$LauncherErr
        WindowsEvents=$EventsLog
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
    Write-Log "SESSION" ("Completed. Duration={0:N1}s" -f ($endTime-$startTime).TotalSeconds)
}
catch {
    Write-Log "FATAL" $_.Exception.ToString()
}
finally {
    try { $script:Writer.Dispose() } catch {}
    try {
        $zip = Join-Path $LogsRoot ("RUNTIME-{0}.zip" -f $SessionId)
        if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
        Compress-Archive -Path (Join-Path $SessionDir "*") -DestinationPath $zip -Force
        Copy-Item -LiteralPath $zip -Destination (Join-Path $LogsRoot "LATEST-RUNTIME-LOG.zip") -Force
        Write-Host ""
        Write-Host "============================================================"
        Write-Host " RUNTIME LOG COMPLETE" -ForegroundColor Green
        Write-Host "============================================================"
        Write-Host ("Session: {0}" -f $SessionDir)
        Write-Host ("Latest:  {0}" -f (Join-Path $LogsRoot "LATEST-RUNTIME-LOG.zip"))
        Write-Host ""
    } catch {
        Write-Host ("Failed to package runtime log: {0}" -f $_.Exception.Message) -ForegroundColor Red
    }
}
