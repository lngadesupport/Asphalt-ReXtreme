param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$outDir=Join-Path $game "_PHASE22_POPUP_TRACE"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $outDir "AMS.PRE-TRAPS.exe"
$mapFile=Join-Path $outDir "TRAPS.json"
$trace=Join-Path $outDir "LATEST-PHASE22-TRACE.txt"
$launcherBackup=Join-Path $game "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$launcherLive=Join-Path $game "RUN-PACKAGE-PHASE5.cmd"

if(-not(Test-Path $mapFile)){throw "TRAPS.json missing."}
if(-not(Test-Path $backup)){throw "Pre-trap backup missing."}
if([IntPtr]::Size -ne 8){throw "Phase 22 debugger requires 64-bit PowerShell."}

$map=Get-Content -LiteralPath $mapFile -Raw | ConvertFrom-Json
$launch=if(Test-Path $launcherBackup){$launcherBackup}else{$launcherLive}
if(-not(Test-Path $launch)){throw "Game launcher not found."}

$src=@'
using System;
using System.Runtime.InteropServices;

public static class ReXDebug {
  public const uint EXCEPTION_DEBUG_EVENT = 1;
  public const uint EXIT_PROCESS_DEBUG_EVENT = 5;
  public const uint DBG_CONTINUE = 0x00010002;
  public const uint DBG_EXCEPTION_NOT_HANDLED = 0x80010001;

  [StructLayout(LayoutKind.Sequential)]
  public struct EXCEPTION_RECORD {
    public uint ExceptionCode;
    public uint ExceptionFlags;
    public IntPtr ExceptionRecord;
    public IntPtr ExceptionAddress;
    public uint NumberParameters;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=15)]
    public UIntPtr[] ExceptionInformation;
  }

  [StructLayout(LayoutKind.Sequential)]
  public struct EXCEPTION_DEBUG_INFO {
    public EXCEPTION_RECORD ExceptionRecord;
    public uint dwFirstChance;
  }

  [StructLayout(LayoutKind.Explicit, Size=176)]
  public struct DEBUG_EVENT {
    [FieldOffset(0)] public uint dwDebugEventCode;
    [FieldOffset(4)] public uint dwProcessId;
    [FieldOffset(8)] public uint dwThreadId;
    [FieldOffset(16)] public EXCEPTION_DEBUG_INFO Exception;
  }

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool DebugActiveProcess(uint dwProcessId);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool DebugActiveProcessStop(uint dwProcessId);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool DebugSetProcessKillOnExit(bool KillOnExit);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool WaitForDebugEvent(out DEBUG_EVENT lpDebugEvent, uint dwMilliseconds);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ContinueDebugEvent(uint dwProcessId, uint dwThreadId, uint dwContinueStatus);

  public static int LastError() { return Marshal.GetLastWin32Error(); }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$sb=New-Object Text.StringBuilder
function L([string]$s){
  $line=("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$s)
  Write-Host $line
  [void]$sb.AppendLine($line)
}

$existing=@(Get-Process -Name AMS -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$eventStart=Get-Date
$lp=Start-Process -FilePath $env:ComSpec -ArgumentList @("/d","/c",('"{0}"' -f $launch)) -WorkingDirectory $game -PassThru
L ("LauncherPID="+$lp.Id)

$proc=$null
$deadline=(Get-Date).AddSeconds(60)
while((Get-Date)-lt $deadline -and $null -eq $proc){
  $p=@(Get-Process -Name AMS -ErrorAction SilentlyContinue | Where-Object {$existing -notcontains $_.Id})
  if($p.Count -gt 0){$proc=$p|Sort-Object StartTime -Descending|Select-Object -First 1;break}
  Start-Sleep -Milliseconds 100
}
if($null -eq $proc){throw "AMS.exe was not detected."}

$pid2=[uint32]$proc.Id
$base=[uint64]$proc.MainModule.BaseAddress.ToInt64()
L ("GamePID="+$pid2)
L ("RuntimeBase=0x{0:X8}" -f $base)

$lookup=@{}
foreach($t in $map.Traps){
  $addr=$base+[uint64]$t.RVA
  $lookup[("0x{0:X}" -f $addr)]=[pscustomobject]@{
    Address=$addr
    Kind=$t.Kind
    FileOffsetHex=$t.FileOffsetHex
    RVAHex=$t.RVAHex
  }
}

$attached=[ReXDebug]::DebugActiveProcess($pid2)
if(-not $attached){
  L ("DebugActiveProcess failed Win32="+[ReXDebug]::LastError())
  L "Falling back to Windows Application Error event log."
}else{
  [void][ReXDebug]::DebugSetProcessKillOnExit($false)
  L "Debugger attached."
}

$matched=$null
try{
  if($attached){
    while($true){
      $ev=New-Object ReXDebug+DEBUG_EVENT
      if(-not [ReXDebug]::WaitForDebugEvent([ref]$ev,1000)){
        if(-not(Get-Process -Id $pid2 -ErrorAction SilentlyContinue)){break}
        continue
      }

      $status=[ReXDebug]::DBG_CONTINUE
      if($ev.dwDebugEventCode -eq [ReXDebug]::EXCEPTION_DEBUG_EVENT){
        $code=$ev.Exception.ExceptionRecord.ExceptionCode
        $addr=[uint64]$ev.Exception.ExceptionRecord.ExceptionAddress.ToInt64()
        $first=$ev.Exception.dwFirstChance
        $key=("0x{0:X}" -f $addr)
        if($lookup.ContainsKey($key)){
          $matched=$lookup[$key]
          L ("TRIPWIRE HIT kind={0} runtime=0x{1:X8} RVA={2} file={3} firstChance={4} exception=0x{5:X8}" -f $matched.Kind,$addr,$matched.RVAHex,$matched.FileOffsetHex,$first,$code)
          $status=[ReXDebug]::DBG_EXCEPTION_NOT_HANDLED
        }elseif($code -eq 0x80000003){
          # Initial debugger breakpoint or unrelated INT3.
          $status=[ReXDebug]::DBG_CONTINUE
        }else{
          L ("Exception code=0x{0:X8} runtime=0x{1:X8} firstChance={2}" -f $code,$addr,$first)
          $status=[ReXDebug]::DBG_EXCEPTION_NOT_HANDLED
        }
      }
      [void][ReXDebug]::ContinueDebugEvent($ev.dwProcessId,$ev.dwThreadId,$status)
      if($ev.dwDebugEventCode -eq [ReXDebug]::EXIT_PROCESS_DEBUG_EVENT){break}
      if($null -ne $matched -and -not(Get-Process -Id $pid2 -ErrorAction SilentlyContinue)){break}
    }
  }else{
    while(Get-Process -Id $pid2 -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 300}
  }
}finally{
  if($attached){try{[void][ReXDebug]::DebugActiveProcessStop($pid2)}catch{}}
}

Start-Sleep -Milliseconds 500
L "AMS.exe exited."

try{
  $events=Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000;StartTime=$eventStart} -ErrorAction SilentlyContinue |
    Where-Object {$_.Message -match '(?i)AMS\.exe'} |
    Select-Object -First 5
  foreach($e in $events){
    L ("EVENT1000: "+(($e.Message -replace "\r?\n"," | ")))
  }
}catch{}

if($null -eq $matched){
  L "RESULT: No NO_INTERNET tripwire was hit."
}else{
  L ("RESULT: Active NO_INTERNET construction site = {0} / {1}" -f $matched.RVAHex,$matched.FileOffsetHex)
}

$sb.ToString()|Set-Content -LiteralPath $trace -Encoding UTF8

# Remove all INT3 tripwires immediately; preserve the exact pre-Phase22 AMS state.
Copy-Item -LiteralPath $backup -Destination $ams -Force
L "AMS.exe restored to pre-Phase22 state."
$sb.ToString()|Set-Content -LiteralPath $trace -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 22 TRACE COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Trace: "+$trace)
