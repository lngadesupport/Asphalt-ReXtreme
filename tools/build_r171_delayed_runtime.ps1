param(
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$vswhere = Join-Path $pf86 "Microsoft Visual Studio\Installer\vswhere.exe"

if (-not (Test-Path -LiteralPath $vswhere)) {
    throw "vswhere.exe not found"
}

$install = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if (-not $install) {
    throw "MSVC x86 toolchain not found"
}

$vcvars = Join-Path $install "VC\Auxiliary\Build\vcvarsall.bat"
if (-not (Test-Path -LiteralPath $vcvars)) {
    throw "vcvarsall.bat not found: $vcvars"
}

$outDir = Join-Path $SourceDir "RUNTIME_STUBS\R171"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$bootstrapC = Join-Path $SourceDir "runtime-stubs\r171_igp_bootstrap.c"
$bootstrapDef = Join-Path $SourceDir "runtime-stubs\IGPLib_x86_r171.def"
$runtimeCpp = Join-Path $SourceDir "src-reconstructed\local-runtime\LocalEventRuntimeR171.cpp"

$bootstrapObj = Join-Path $outDir "r171_igp_bootstrap.obj"
$igpDll = Join-Path $outDir "IGPLib_x86.dll"
$runtimeDll = Join-Path $outDir "ReXtremeLocalRuntime.dll"
$runtimePdb = Join-Path $outDir "ReXtremeLocalRuntime.pdb"

$bootstrapCmd = @(
    'cl.exe /nologo /c /O1 /Oi /GS- /TC /DWIN32 /D_WINDOWS',
    ('"{0}" /Fo"{1}"' -f $bootstrapC,$bootstrapObj),
    '&&',
    ('link.exe /nologo /dll /noentry /nodefaultlib /machine:x86 /def:"{0}" /out:"{1}" "{2}" kernel32.lib' -f $bootstrapDef,$igpDll,$bootstrapObj)
) -join ' '

$runtimeCmd = @(
    'cl.exe /nologo /std:c++17 /O2 /MT /EHsc /LD /DWIN32 /D_WINDOWS /DUNICODE /D_UNICODE',
    ('"{0}"' -f $runtimeCpp),
    ('/link /MACHINE:X86 /OUT:"{0}" /PDB:"{1}" user32.lib gdi32.lib kernel32.lib' -f $runtimeDll,$runtimePdb)
) -join ' '

$cmd = ('call "{0}" x86 >nul && {1} && {2}' -f $vcvars,$bootstrapCmd,$runtimeCmd)
& cmd.exe /d /s /c $cmd
if ($LASTEXITCODE -ne 0) {
    throw "R17.1 build failed with code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $igpDll)) { throw "IGPLib_x86.dll missing" }
if (-not (Test-Path -LiteralPath $runtimeDll)) { throw "ReXtremeLocalRuntime.dll missing" }

$report = [ordered]@{
    Phase = "R17.1 Delayed Core Runtime"
    Architecture = "x86"
    Bootstrap = "IGPLib_x86.dll"
    BootstrapNoEntry = $true
    Trigger = "IGPLib::InitBridgeClass"
    Runtime = "ReXtremeLocalRuntime.dll"
    DllMainStartsRuntime = $false
    DelayedStartMilliseconds = 1500
    OverlayUIEnabled = $false
    BuildCarVA = "0x00A87960"
    SelectedCarIdHelperVA = "0x00D805F0"
    BootstrapSHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $igpDll).Hash.ToLowerInvariant()
    RuntimeSHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimeDll).Hash.ToLowerInvariant()
}

$report | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $outDir "R171-BUILD-REPORT.json") -Encoding UTF8

Write-Host "R17.1 delayed runtime built." -ForegroundColor Green
Write-Host "Bootstrap: $igpDll"
Write-Host "Runtime:   $runtimeDll"
