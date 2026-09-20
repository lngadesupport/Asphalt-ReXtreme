@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo Asphalt ReXtreme - Unified Diagnostic
echo ============================================================
echo.
echo Este e o diagnostico unico. Ele coleta analise estatica + crash.
echo Nenhum arquivo do jogo sera modificado.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$raw=Get-Content -Raw -LiteralPath '%~f0';" ^
  "$mark=':__POWERSHELL_BELOW__';" ^
  "$idx=$raw.IndexOf($mark);" ^
  "if($idx -lt 0){Write-Error 'Embedded diagnostic not found'; exit 10};" ^
  "$code=$raw.Substring($idx+$mark.Length);" ^
  "& ([ScriptBlock]::Create($code)) -GameRoot (Get-Location).Path;" ^
  "exit $LASTEXITCODE"

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Diagnostico terminou com codigo %RC%.
echo.
pause
exit /b %RC%

:__POWERSHELL_BELOW__
param(
    [Parameter(Mandatory=$true)]
    [string]$GameRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Step([string]$Message) {
    Write-Host ("[DIAG] " + $Message) -ForegroundColor Cyan
}

function Relative([string]$Base, [string]$Full) {
    $b = [IO.Path]::GetFullPath($Base).TrimEnd("\\") + "\\"
    $f = [IO.Path]::GetFullPath($Full)
    if ($f.StartsWith($b,[StringComparison]::OrdinalIgnoreCase)) {
        return $f.Substring($b.Length)
    }
    return $f
}

function Redact([string]$Text) {
    if ($null -eq $Text) { return "" }
    $v = [string]$Text
    if ($env:USERPROFILE) {
        $v = [regex]::Replace(
            $v,
            [regex]::Escape($env:USERPROFILE),
            "%USERPROFILE%",
            [Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
    }
    return $v
}

function RvaToOffset([UInt64]$Rva,[object[]]$Sections) {
    foreach ($s in $Sections) {
        $span = [Math]::Max([UInt64]$s.VirtualSize,[UInt64]$s.RawSize)
        $start = [UInt64]$s.VirtualAddress
        if ($Rva -ge $start -and $Rva -lt ($start + $span)) {
            return [Int64]([UInt64]$s.RawPointer + ($Rva - $start))
        }
    }
    return [Int64]-1
}

function AsciiZ([byte[]]$Data,[Int64]$Offset) {
    if ($Offset -lt 0 -or $Offset -ge $Data.Length) { return "" }
    $end = [Math]::Min($Data.Length,$Offset + 4096)
    $bytes = New-Object Collections.Generic.List[byte]
    for ($i=$Offset; $i -lt $end; $i++) {
        if ($Data[$i] -eq 0) { break }
        [void]$bytes.Add($Data[$i])
    }
    return [Text.Encoding]::ASCII.GetString($bytes.ToArray())
}

function ReadPE([string]$Path) {
    $r = [ordered]@{
        IsPE=$false; Error=""; Architecture=""; Machine="";
        Subsystem=""; DllCharacteristics=""; AppContainer=$false;
        EntryRva=""; ImageBase=""; Sections=@(); Imports=@(); Exports=@()
    }

    try {
        $d=[IO.File]::ReadAllBytes($Path)
        if ($d.Length -lt 256 -or $d[0] -ne 0x4D -or $d[1] -ne 0x5A) {
            $r.Error="not-pe"; return [pscustomobject]$r
        }

        $pe=[BitConverter]::ToInt32($d,0x3C)
        if ($pe -lt 0 -or ($pe+256) -gt $d.Length -or
            $d[$pe] -ne 0x50 -or $d[$pe+1] -ne 0x45) {
            $r.Error="bad-pe"; return [pscustomobject]$r
        }

        $r.IsPE=$true
        $coff=$pe+4
        $machine=[BitConverter]::ToUInt16($d,$coff)
        $nsects=[BitConverter]::ToUInt16($d,$coff+2)
        $optsz=[BitConverter]::ToUInt16($d,$coff+16)
        $opt=$coff+20
        $magic=[BitConverter]::ToUInt16($d,$opt)

        switch ($machine) {
            0x014C {$arch="x86"}
            0x8664 {$arch="x64"}
            0x01C0 {$arch="ARM"}
            0xAA64 {$arch="ARM64"}
            default {$arch=("0x{0:X4}" -f $machine)}
        }

        if ($magic -eq 0x10B) {
            $dd=$opt+96
            $base=[UInt64][BitConverter]::ToUInt32($d,$opt+28)
            $ts=4
            $ord=[UInt64]::Parse("80000000",[Globalization.NumberStyles]::HexNumber)
            $mask=[UInt64]::Parse("7FFFFFFF",[Globalization.NumberStyles]::HexNumber)
        } elseif ($magic -eq 0x20B) {
            $dd=$opt+112
            $base=[BitConverter]::ToUInt64($d,$opt+24)
            $ts=8
            $ord=[UInt64]::Parse("8000000000000000",[Globalization.NumberStyles]::HexNumber)
            $mask=[UInt64]::Parse("7FFFFFFFFFFFFFFF",[Globalization.NumberStyles]::HexNumber)
        } else {
            $r.Error=("optional-magic-0x{0:X}" -f $magic)
            return [pscustomobject]$r
        }

        $r.Architecture=$arch
        $r.Machine=("0x{0:X4}" -f $machine)
        $r.EntryRva=("0x{0:X}" -f [BitConverter]::ToUInt32($d,$opt+16))
        $r.ImageBase=("0x{0:X}" -f $base)
        $r.Subsystem=[BitConverter]::ToUInt16($d,$opt+68)
        $dc=[BitConverter]::ToUInt16($d,$opt+70)
        $r.DllCharacteristics=("0x{0:X4}" -f $dc)
        $r.AppContainer=(($dc -band 0x1000) -ne 0)

        $sections=@()
        $st=$opt+$optsz
        for ($i=0;$i -lt $nsects;$i++) {
            $p=$st+($i*40)
            if (($p+40) -gt $d.Length) { break }
            $nb=New-Object byte[] 8
            [Array]::Copy($d,$p,$nb,0,8)
            $sections += [pscustomobject]@{
                Name=[Text.Encoding]::ASCII.GetString($nb).Trim([char]0)
                VirtualSize=[BitConverter]::ToUInt32($d,$p+8)
                VirtualAddress=[BitConverter]::ToUInt32($d,$p+12)
                RawSize=[BitConverter]::ToUInt32($d,$p+16)
                RawPointer=[BitConverter]::ToUInt32($d,$p+20)
            }
        }
        $r.Sections=@($sections)

        # Imports
        $irva=[UInt64][BitConverter]::ToUInt32($d,$dd+8)
        $isz=[UInt64][BitConverter]::ToUInt32($d,$dd+12)
        $imports=@()

        if ($irva -ne 0 -and $isz -ne 0) {
            $io=RvaToOffset $irva $sections
            if ($io -ge 0) {
                for ($di=0;$di -lt 4096;$di++) {
                    $p=$io+($di*20)
                    if (($p+20) -gt $d.Length) { break }

                    $oft=[UInt64][BitConverter]::ToUInt32($d,$p)
                    $time=[BitConverter]::ToUInt32($d,$p+4)
                    $forward=[BitConverter]::ToUInt32($d,$p+8)
                    $nrva=[UInt64][BitConverter]::ToUInt32($d,$p+12)
                    $ft=[UInt64][BitConverter]::ToUInt32($d,$p+16)

                    if ($oft -eq 0 -and $time -eq 0 -and $forward -eq 0 -and
                        $nrva -eq 0 -and $ft -eq 0) { break }

                    $dll=AsciiZ $d (RvaToOffset $nrva $sections)
                    if (-not $dll) {$dll="<unknown>"}
                    if ($oft -ne 0) {$trva=$oft} else {$trva=$ft}
                    $to=RvaToOffset $trva $sections

                    if ($to -lt 0) {
                        $imports += [pscustomobject]@{DLL=$dll;Function="";Ordinal=""}
                        continue
                    }

                    for ($j=0;$j -lt 65536;$j++) {
                        $ep=$to+($j*$ts)
                        if (($ep+$ts) -gt $d.Length) { break }
                        if ($ts -eq 8) {
                            $v=[BitConverter]::ToUInt64($d,$ep)
                        } else {
                            $v=[UInt64][BitConverter]::ToUInt32($d,$ep)
                        }
                        if ($v -eq 0) { break }

                        $fn=""; $ordinal=""
                        if (($v -band $ord) -ne 0) {
                            $ordinal=[int]($v -band 0xFFFF)
                        } else {
                            $hn=$v -band $mask
                            $ho=RvaToOffset $hn $sections
                            if ($ho -ge 0 -and ($ho+2) -lt $d.Length) {
                                $fn=AsciiZ $d ($ho+2)
                            }
                        }

                        $imports += [pscustomobject]@{
                            DLL=$dll; Function=$fn; Ordinal=$ordinal
                        }
                    }
                }
            }
        }
        $r.Imports=@($imports)

        # Exports
        $erva=[UInt64][BitConverter]::ToUInt32($d,$dd)
        $esz=[UInt64][BitConverter]::ToUInt32($d,$dd+4)
        $exports=@()

        if ($erva -ne 0 -and $esz -ne 0) {
            $eo=RvaToOffset $erva $sections
            if ($eo -ge 0 -and ($eo+40) -le $d.Length) {
                $baseOrd=[BitConverter]::ToUInt32($d,$eo+16)
                $nNames=[BitConverter]::ToUInt32($d,$eo+24)
                $aNames=[UInt64][BitConverter]::ToUInt32($d,$eo+32)
                $aOrds=[UInt64][BitConverter]::ToUInt32($d,$eo+36)
                $no=RvaToOffset $aNames $sections
                $oo=RvaToOffset $aOrds $sections

                if ($no -ge 0 -and $oo -ge 0) {
                    $limit=[Math]::Min([Int64]$nNames,100000)
                    for ($i=0;$i -lt $limit;$i++) {
                        $nameRva=[UInt64][BitConverter]::ToUInt32($d,$no+($i*4))
                        $name=AsciiZ $d (RvaToOffset $nameRva $sections)
                        $oi=[BitConverter]::ToUInt16($d,$oo+($i*2))
                        $exports += [pscustomobject]@{
                            Name=$name; Ordinal=[UInt64]$baseOrd+$oi
                        }
                    }
                }
            }
        }
        $r.Exports=@($exports)
    } catch {
        $r.Error=$_.Exception.Message
    }

    return [pscustomobject]$r
}

$root=(Resolve-Path -LiteralPath $GameRoot).Path
$exe=Join-Path $root "AMS.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "AMS.exe not found: $root"
}

$base=Join-Path $root "_campaign_unified_diagnostic"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$run=Join-Path $base ("run-"+$stamp)
$reports=Join-Path $run "reports"
$dumps=Join-Path $run "dumps"
New-Item -ItemType Directory -Force -Path $reports,$dumps | Out-Null

Step "1/6 core integrity"

$keyFiles=@(
    "AMS.exe","WCPToolkit.dll","InAppPurchaseComponentW8.dll","IGPLib_x86.dll",
    "App.xbf","DirectXPage.xbf","resources.pri",
    "data\xml.bin","data\xml.bin.hdr","data\snsconfig.json",
    "vccorlib120_app.dll","msvcp120_app.dll","msvcr120_app.dll"
)

$integrity=@()
foreach ($rel in $keyFiles) {
    $p=Join-Path $root $rel
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        $f=Get-Item -LiteralPath $p
        $integrity += [pscustomobject]@{
            Path=$rel; Found=$true; Size=$f.Length;
            SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
        }
    } else {
        $integrity += [pscustomobject]@{
            Path=$rel; Found=$false; Size=""; SHA256=""
        }
    }
}
$integrity | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "core-integrity.csv")

Step "2/6 PE imports and exports"

$corePE=@(
    "AMS.exe","WCPToolkit.dll","InAppPurchaseComponentW8.dll",
    "IGPLib_x86.dll","Microsoft.Live.dll","Facebook.dll"
)
$peSummary=@(); $imports=@(); $exports=@()

foreach ($rel in $corePE) {
    $p=Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { continue }

    $info=ReadPE $p
    $peSummary += [pscustomobject]@{
        File=$rel; IsPE=$info.IsPE; Error=$info.Error;
        Architecture=$info.Architecture; Machine=$info.Machine;
        Subsystem=$info.Subsystem; DllCharacteristics=$info.DllCharacteristics;
        AppContainer=$info.AppContainer; EntryRva=$info.EntryRva;
        ImageBase=$info.ImageBase; ImportCount=@($info.Imports).Count;
        ExportCount=@($info.Exports).Count
    }

    foreach ($i in @($info.Imports)) {
        $imports += [pscustomobject]@{
            File=$rel; DLL=$i.DLL; Function=$i.Function; Ordinal=$i.Ordinal
        }
    }
    foreach ($e in @($info.Exports)) {
        $exports += [pscustomobject]@{
            File=$rel; Name=$e.Name; Ordinal=$e.Ordinal
        }
    }
}
$peSummary | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "pe-summary.csv")
$imports | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "pe-imports.csv")
$exports | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "pe-exports.csv")

Step "3/6 Store/UWP/XAML/ad references"

$terms=[ordered]@{
    store=@("Windows.ApplicationModel.Store","CurrentApp","StoreContext","ms-windows-store:")
    package=@("Windows.ApplicationModel.Package","PackageFamilyName","PackageFullName","AppUserModelID","GetCurrentPackage")
    xaml=@("Windows.UI.Xaml.Application","Windows.ApplicationModel.Core.CoreApplication","RoActivateInstance","RoGetActivationFactory","ms-appx:","DirectXPage","ApplicationData.Current","Windows.Storage.ApplicationData")
    ads_iap=@("Vungle","rewarded","ad_rewards","IGPLib","InAppPurchase","iap.gameloft","purchase")
    online=@("secure.gameloft.com","eve.gameloft.com","gameoptions.gameloft.com","201205igp.gameloft.com","Microsoft.Live","XboxLive")
}

$refs=@()
foreach ($rel in @("AMS.exe","WCPToolkit.dll","Gameoptions_W8.json","in-app-purchase_w8.1.xml","data\snsconfig.json")) {
    $p=Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { continue }
    $f=Get-Item -LiteralPath $p
    if ($f.Length -gt 268435456) { continue }

    try {
        $bytes=[IO.File]::ReadAllBytes($p)
        $ascii=[Text.Encoding]::ASCII.GetString($bytes)
        $unicode=[Text.Encoding]::Unicode.GetString($bytes)

        foreach ($category in $terms.Keys) {
            foreach ($term in $terms[$category]) {
                $a=([regex]::Matches($ascii,[regex]::Escape($term),"IgnoreCase")).Count
                $u=([regex]::Matches($unicode,[regex]::Escape($term),"IgnoreCase")).Count
                if (($a+$u) -gt 0) {
                    $refs += [pscustomobject]@{
                        File=$rel; Category=$category; Term=$term;
                        Ascii=$a; Utf16=$u; Total=$a+$u
                    }
                }
            }
        }
    } catch {}
}
$refs | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "runtime-references.csv")

Step "4/6 Windows runtime state"

$system=New-Object Collections.Generic.List[string]
$system.Add("Generated: $(Get-Date -Format o)")
try {
    $os=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $system.Add("OS: $($os.Caption)")
    $system.Add("Version: $($os.Version)")
    $system.Add("Build: $($os.BuildNumber)")
    $system.Add("Architecture: $($os.OSArchitecture)")
} catch {
    $system.Add("OS query failed: $($_.Exception.Message)")
}
try {
    foreach ($gpu in @(Get-CimInstance Win32_VideoController -ErrorAction Stop)) {
        $system.Add("GPU: $($gpu.Name)")
        $system.Add("GPU Driver: $($gpu.DriverVersion)")
    }
} catch {}

try {
    $pkg=Get-AppxPackage -Name "A278AB0D.AsphaltXtreme" -ErrorAction SilentlyContinue
    if ($pkg) {
        foreach ($p in @($pkg)) {
            $system.Add("Legacy package registered: YES")
            $system.Add("PackageFullName: $($p.PackageFullName)")
            $system.Add("InstallLocation: $(Redact $p.InstallLocation)")
        }
    } else {
        $system.Add("Legacy package registered: NO")
    }
} catch {
    $system.Add("Package query failed: $($_.Exception.Message)")
}
$system | Set-Content -LiteralPath (Join-Path $reports "system-runtime.txt") -Encoding UTF8

Step "5/6 AMS.exe runtime/crash capture"

$wer="HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\AMS.exe"
$werExisted=Test-Path -LiteralPath $wer
$oldFolder=$null; $oldCount=$null; $oldType=$null

if ($werExisted) {
    try {
        $old=Get-ItemProperty -LiteralPath $wer
        if ($old.PSObject.Properties["DumpFolder"]) {$oldFolder=$old.DumpFolder}
        if ($old.PSObject.Properties["DumpCount"]) {$oldCount=$old.DumpCount}
        if ($old.PSObject.Properties["DumpType"]) {$oldType=$old.DumpType}
    } catch {}
}

$exitCode=""
$state=""
$start=$null

try {
    New-Item -Path $wer -Force | Out-Null
    New-ItemProperty -Path $wer -Name DumpFolder -PropertyType ExpandString -Value $dumps -Force | Out-Null
    New-ItemProperty -Path $wer -Name DumpCount -PropertyType DWord -Value 3 -Force | Out-Null
    New-ItemProperty -Path $wer -Name DumpType -PropertyType DWord -Value 1 -Force | Out-Null

    $start=Get-Date
    $proc=Start-Process -FilePath $exe -WorkingDirectory $root -PassThru
    $pidValue=$proc.Id

    Start-Sleep -Seconds 2

    $modules=@()
    try {
        $live=Get-Process -Id $pidValue -ErrorAction Stop
        foreach ($m in @($live.Modules)) {
            $modules += [pscustomobject]@{
                Module=$m.ModuleName
                FileName=(Redact $m.FileName)
                BaseAddress=("0x{0:X}" -f $m.BaseAddress.ToInt64())
                MemorySize=$m.ModuleMemorySize
                Version=$m.FileVersionInfo.FileVersion
            }
        }
    } catch {}
    $modules | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $reports "loaded-modules.csv")

    $finished=$false
    try {$finished=$proc.WaitForExit(30000)} catch {}

    if ($finished) {
        $proc.Refresh()
        $exitCode=$proc.ExitCode
        $state="exited"
        Start-Sleep -Seconds 3
    } else {
        $state="still-running-after-30s"
    }

    $runtime=New-Object Collections.Generic.List[string]
    $runtime.Add("PID: $pidValue")
    $runtime.Add("State: $state")
    if ($exitCode -ne "") {
        $runtime.Add("ExitCodeDecimal: $exitCode")
        $runtime.Add(("ExitCodeHex: 0x{0:X8}" -f ([uint32]$exitCode)))
    }

    $dumpFiles=@(Get-ChildItem -LiteralPath $dumps -File -Filter "*.dmp" -ErrorAction SilentlyContinue)
    $runtime.Add("DumpCount: $($dumpFiles.Count)")
    foreach ($d in $dumpFiles) {$runtime.Add("Dump: $($d.Name) | $($d.Length) bytes")}
    $runtime.Add("")

    foreach ($log in @("Application","Microsoft-Windows-AppModel-Runtime/Admin","Microsoft-Windows-TWinUI/Operational")) {
        $runtime.Add("===== $log =====")
        try {
            $events=Get-WinEvent -FilterHashtable @{
                LogName=$log; StartTime=$start.AddSeconds(-3); EndTime=(Get-Date).AddSeconds(3)
            } -ErrorAction Stop | Where-Object {
                ([string]$_.Message) -match "(?i)AMS\.exe|Asphalt|ReXtreme|A278AB0D\.AsphaltXtreme"
            } | Select-Object -First 100

            if (-not $events) {$runtime.Add("(no matching events)")}
            foreach ($e in @($events)) {
                $runtime.Add(("[{0}] Id={1} Provider={2}" -f $e.TimeCreated.ToString("o"),$e.Id,$e.ProviderName))
                $runtime.Add((Redact ([string]$e.Message)))
                $runtime.Add("")
            }
        } catch {
            $runtime.Add("Log read error: $($_.Exception.Message)")
        }
        $runtime.Add("")
    }
    $runtime | Set-Content -LiteralPath (Join-Path $reports "runtime-crash.txt") -Encoding UTF8
}
finally {
    if (Test-Path -LiteralPath $wer) {
        Remove-Item -LiteralPath $wer -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($werExisted) {
        New-Item -Path $wer -Force | Out-Null
        if ($null -ne $oldFolder) {New-ItemProperty -Path $wer -Name DumpFolder -PropertyType ExpandString -Value $oldFolder -Force | Out-Null}
        if ($null -ne $oldCount) {New-ItemProperty -Path $wer -Name DumpCount -PropertyType DWord -Value $oldCount -Force | Out-Null}
        if ($null -ne $oldType) {New-ItemProperty -Path $wer -Name DumpType -PropertyType DWord -Value $oldType -Force | Out-Null}
    }
}

Step "6/6 one diagnostic ZIP"

$summary=New-Object Collections.Generic.List[string]
$summary.Add("Asphalt ReXtreme Unified Diagnostic")
$summary.Add("Generated: $(Get-Date -Format o)")
$summary.Add("Core files found: $(@($integrity | Where-Object {$_.Found -eq $true}).Count)/$($integrity.Count)")
$summary.Add("PE import rows: $($imports.Count)")
$summary.Add("PE export rows: $($exports.Count)")
$summary.Add("AppContainer core PE: $(@($peSummary | Where-Object {$_.AppContainer -eq $true}).Count)")
$summary.Add("Runtime references: $($refs.Count)")
$summary.Add("Process state: $state")
if ($exitCode -ne "") {$summary.Add(("Exit: {0} / 0x{1:X8}" -f $exitCode,([uint32]$exitCode)))}
$summary.Add("Game files modified: NO")
$summary | Set-Content -LiteralPath (Join-Path $run "SUMMARY.txt") -Encoding UTF8

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=Join-Path $base ("Asphalt-ReXtreme-Unified-Diagnostic-"+$stamp+".zip")
if (Test-Path -LiteralPath $zip) {Remove-Item -LiteralPath $zip -Force}
[IO.Compression.ZipFile]::CreateFromDirectory($run,$zip,[IO.Compression.CompressionLevel]::Optimal,$false)

Write-Host ""
Write-Host "UNIFIED DIAGNOSTIC COMPLETE" -ForegroundColor Green
Write-Host "Send only this ZIP:"
Write-Host "  $zip"
