param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$outDir=Join-Path $game "_PHASE24_POPUP_CALL_TRACE"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $outDir "AMS.PRE-CALL-TRAPS.exe"
$mapFile=Join-Path $outDir "TRAPS.json"
$trace=Join-Path $outDir "LATEST-PHASE24-TRACE.txt"
$launcherBackup=Join-Path $game "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$launcherLive=Join-Path $game "RUN-PACKAGE-PHASE5.cmd"

if(-not(Test-Path $mapFile)){throw "TRAPS.json missing."}
if(-not(Test-Path $backup)){throw "Pre-trap backup missing."}
$map=Get-Content -LiteralPath $mapFile -Raw|ConvertFrom-Json
$launch=if(Test-Path $launcherBackup){$launcherBackup}else{$launcherLive}
if(-not(Test-Path $launch)){throw "Game launcher not found."}

$src=@'
using System;
using System.Runtime.InteropServices;
public static class ReXDbg24 {
 public const uint EXCEPTION_DEBUG_EVENT=1, EXIT_PROCESS_DEBUG_EVENT=5;
 public const uint DBG_CONTINUE=0x00010002, DBG_EXCEPTION_NOT_HANDLED=0x80010001;
 [StructLayout(LayoutKind.Sequential)] public struct ER {
  public uint Code,Flags; public IntPtr Record,Address; public uint Count;
  [MarshalAs(UnmanagedType.ByValArray,SizeConst=15)] public UIntPtr[] Info;
 }
 [StructLayout(LayoutKind.Sequential)] public struct EI { public ER ExceptionRecord; public uint FirstChance; }
 [StructLayout(LayoutKind.Explicit,Size=176)] public struct DE {
  [FieldOffset(0)] public uint Code; [FieldOffset(4)] public uint Pid;
  [FieldOffset(8)] public uint Tid; [FieldOffset(16)] public EI Exception;
 }
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool DebugActiveProcess(uint p);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool DebugActiveProcessStop(uint p);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool DebugSetProcessKillOnExit(bool b);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool WaitForDebugEvent(out DE e,uint ms);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool ContinueDebugEvent(uint p,uint t,uint s);
 public static int LastError(){return Marshal.GetLastWin32Error();}
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$sb=New-Object Text.StringBuilder
function L([string]$s){
  $line=("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$s)
  Write-Host $line
  [void]$sb.AppendLine($line)
}

$existing=@(Get-Process AMS -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id)
$lp=Start-Process $env:ComSpec -ArgumentList @("/d","/c",('"{0}"' -f $launch)) -WorkingDirectory $game -PassThru
L ("LauncherPID="+$lp.Id)

$proc=$null
$deadline=(Get-Date).AddSeconds(60)
while((Get-Date)-lt $deadline -and $null -eq $proc){
 $p=@(Get-Process AMS -ErrorAction SilentlyContinue|Where-Object{$existing -notcontains $_.Id})
 if($p.Count){$proc=$p|Sort-Object StartTime -Descending|Select-Object -First 1}else{Start-Sleep -Milliseconds 100}
}
if($null -eq $proc){throw "AMS.exe not detected."}

$pid2=[uint32]$proc.Id
$base=[uint64]$proc.MainModule.BaseAddress.ToInt64()
L ("GamePID="+$pid2)
L ("RuntimeBase=0x{0:X8}" -f $base)

$lookup=@{}
foreach($t in $map.Traps){
 $addr=$base+[uint64]$t.RVA
 $lookup[("0x{0:X}" -f $addr)]=$t
}

if(-not [ReXDbg24]::DebugActiveProcess($pid2)){throw ("DebugActiveProcess failed Win32="+[ReXDbg24]::LastError())}
[void][ReXDbg24]::DebugSetProcessKillOnExit($false)
L "Debugger attached."

$hit=$null
try{
 while($true){
  $ev=New-Object ReXDbg24+DE
  if(-not [ReXDbg24]::WaitForDebugEvent([ref]$ev,1000)){
   if(-not(Get-Process -Id $pid2 -ErrorAction SilentlyContinue)){break}
   continue
  }
  $status=[ReXDbg24]::DBG_CONTINUE
  if($ev.Code -eq [ReXDbg24]::EXCEPTION_DEBUG_EVENT){
   $code=$ev.Exception.ExceptionRecord.Code
   $addr=[uint64]$ev.Exception.ExceptionRecord.Address.ToInt64()
   $key=("0x{0:X}" -f $addr)
   if($lookup.ContainsKey($key)){
    $hit=$lookup[$key]
    L ("POPUP CALLSITE HIT runtime=0x{0:X8} RVA={1} file={2} preferredVA={3}" -f $addr,$hit.RVAHex,$hit.FileOffsetHex,$hit.PreferredVA)
    L ("Original CALL bytes: "+$hit.OriginalBytes)
    $status=[ReXDbg24]::DBG_EXCEPTION_NOT_HANDLED
   }elseif($code -eq 0x80000003){
    $status=[ReXDbg24]::DBG_CONTINUE
   }else{
    L ("Exception code=0x{0:X8} runtime=0x{1:X8} firstChance={2}" -f $code,$addr,$ev.Exception.FirstChance)
    $status=[ReXDbg24]::DBG_EXCEPTION_NOT_HANDLED
   }
  }
  [void][ReXDbg24]::ContinueDebugEvent($ev.Pid,$ev.Tid,$status)
  if($ev.Code -eq [ReXDbg24]::EXIT_PROCESS_DEBUG_EVENT){break}
 }
}finally{
 try{[void][ReXDbg24]::DebugActiveProcessStop($pid2)}catch{}
}

L "AMS.exe exited."
if($null -eq $hit){L "RESULT: No direct call to popup function 0x00870510 was hit."}
else{L ("RESULT: Active popup caller = {0} / {1}" -f $hit.PreferredVA,$hit.FileOffsetHex)}

Copy-Item -LiteralPath $backup -Destination $ams -Force
L "AMS.exe restored to pre-Phase24 state."
$sb.ToString()|Set-Content -LiteralPath $trace -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 24 TRACE COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Trace: "+$trace)
