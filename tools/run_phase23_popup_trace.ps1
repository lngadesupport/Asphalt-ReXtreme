param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$outDir=Join-Path $game "_PHASE23_POPUP_TRACE"
$ams=Join-Path $game "AMS.exe"
$backup=Join-Path $outDir "AMS.PRE-TRAPS.exe"
$mapFile=Join-Path $outDir "TRAPS.json"
$trace=Join-Path $outDir "LATEST-PHASE23-TRACE.txt"
$launcherBackup=Join-Path $game "RUN-PACKAGE-PHASE5-ORIGINAL.cmd"
$launcherLive=Join-Path $game "RUN-PACKAGE-PHASE5.cmd"

if(-not(Test-Path $mapFile)){throw "TRAPS.json missing."}
if(-not(Test-Path $backup)){throw "Pre-trap backup missing."}
if([IntPtr]::Size -ne 8){throw "Phase 23 debugger requires 64-bit PowerShell."}

$map=Get-Content -LiteralPath $mapFile -Raw | ConvertFrom-Json
$launch=if(Test-Path $launcherBackup){$launcherBackup}else{$launcherLive}
if(-not(Test-Path $launch)){throw "Game launcher not found."}

$src=@'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class ReXDebug {
  public const uint EXCEPTION_DEBUG_EVENT = 1;
  public const uint EXIT_PROCESS_DEBUG_EVENT = 5;
  public const uint DBG_CONTINUE = 0x00010002;
  public const uint DBG_EXCEPTION_NOT_HANDLED = 0x80010001;

  public const uint THREAD_GET_CONTEXT = 0x0008;
  public const uint THREAD_QUERY_INFORMATION = 0x0040;
  public const uint WOW64_CONTEXT_CONTROL = 0x00010001;
  public const uint WOW64_CONTEXT_INTEGER = 0x00010002;

  [StructLayout(LayoutKind.Sequential, Pack=4)]
  public struct WOW64_FLOATING_SAVE_AREA {
    public uint ControlWord;
    public uint StatusWord;
    public uint TagWord;
    public uint ErrorOffset;
    public uint ErrorSelector;
    public uint DataOffset;
    public uint DataSelector;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=80)]
    public byte[] RegisterArea;
    public uint Cr0NpxState;
  }

  [StructLayout(LayoutKind.Sequential, Pack=4)]
  public struct WOW64_CONTEXT {
    public uint ContextFlags;
    public uint Dr0;
    public uint Dr1;
    public uint Dr2;
    public uint Dr3;
    public uint Dr6;
    public uint Dr7;
    public WOW64_FLOATING_SAVE_AREA FloatSave;
    public uint SegGs;
    public uint SegFs;
    public uint SegEs;
    public uint SegDs;
    public uint Edi;
    public uint Esi;
    public uint Ebx;
    public uint Edx;
    public uint Ecx;
    public uint Eax;
    public uint Ebp;
    public uint Eip;
    public uint SegCs;
    public uint EFlags;
    public uint Esp;
    public uint SegSs;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=512)]
    public byte[] ExtendedRegisters;
  }

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenThread(uint dwDesiredAccess, bool bInheritHandle, uint dwThreadId);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool CloseHandle(IntPtr hObject);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool Wow64GetThreadContext(IntPtr hThread, ref WOW64_CONTEXT lpContext);

  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int dwSize, out IntPtr lpNumberOfBytesRead);

  public static string CaptureWow64Stack(uint threadId, IntPtr processHandle, ulong moduleBase, uint moduleSize) {
    var sb = new StringBuilder();
    IntPtr hThread = OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, false, threadId);
    if (hThread == IntPtr.Zero) {
      sb.AppendFormat("STACK: OpenThread failed Win32={0}", Marshal.GetLastWin32Error());
      return sb.ToString();
    }
    try {
      WOW64_CONTEXT ctx = new WOW64_CONTEXT();
      ctx.ContextFlags = WOW64_CONTEXT_CONTROL | WOW64_CONTEXT_INTEGER;
      ctx.FloatSave.RegisterArea = new byte[80];
      ctx.ExtendedRegisters = new byte[512];
      if (!Wow64GetThreadContext(hThread, ref ctx)) {
        sb.AppendFormat("STACK: Wow64GetThreadContext failed Win32={0}", Marshal.GetLastWin32Error());
        return sb.ToString();
      }

      sb.AppendFormat("CTX EIP=0x{0:X8} ESP=0x{1:X8} EBP=0x{2:X8}", ctx.Eip, ctx.Esp, ctx.Ebp);
      byte[] stack = new byte[1024];
      IntPtr read;
      if (!ReadProcessMemory(processHandle, new IntPtr((long)ctx.Esp), stack, stack.Length, out read)) {
        sb.AppendFormat("\nSTACK: ReadProcessMemory failed Win32={0}", Marshal.GetLastWin32Error());
        return sb.ToString();
      }

      int n = Math.Min(stack.Length, read.ToInt32());
      ulong moduleEnd = moduleBase + moduleSize;
      int emitted = 0;
      for (int i = 0; i + 4 <= n && emitted < 48; i += 4) {
        uint v = BitConverter.ToUInt32(stack, i);
        ulong vv = v;
        if (vv >= moduleBase && vv < moduleEnd) {
          ulong rva = vv - moduleBase;
          sb.AppendFormat("\nSTACK_CANDIDATE slot=+0x{0:X3} runtime=0x{1:X8} RVA=0x{2:X8}", i, v, rva);
          emitted++;
        }
      }
      if (emitted == 0) sb.Append("\nSTACK: no in-module return-address candidates in first 1024 bytes");
      return sb.ToString();
    } finally {
      CloseHandle(hThread);
    }
  }

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
$moduleSize=[uint32]$proc.MainModule.ModuleMemorySize
L ("RuntimeBase=0x{0:X8} ModuleSize=0x{1:X8}" -f $base,$moduleSize)

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
          try{
            $stackText=[ReXDebug]::CaptureWow64Stack($ev.dwThreadId,$proc.Handle,$base,$moduleSize)
            foreach($sl in ($stackText -split "\r?\n")){if($sl){L $sl}}
          }catch{L ("STACK-CAPTURE-ERROR: "+$_.Exception.Message)}
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
Write-Host " PHASE 23 TRACE COMPLETE" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Trace: "+$trace)
