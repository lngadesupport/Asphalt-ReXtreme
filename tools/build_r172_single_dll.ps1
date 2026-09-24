param([string]$SourceDir = ".")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$vswhere = Join-Path $pf86 "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) { throw "vswhere.exe not found" }

$install = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if (-not $install) { throw "MSVC x86 toolchain not found" }

$vcvars = Join-Path $install "VC\Auxiliary\Build\vcvarsall.bat"
$outDir = Join-Path $SourceDir "RUNTIME_STUBS\R172"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$cpp = Join-Path $SourceDir "src-reconstructed\local-runtime\LocalEventRuntimeR172.cpp"
$def = Join-Path $SourceDir "runtime-stubs\IGPLib_x86_r172.def"
$outDll = Join-Path $outDir "IGPLib_x86.dll"
$outPdb = Join-Path $outDir "IGPLib_x86.pdb"

$compile = @(
  'cl.exe /nologo /std:c++17 /O2 /MT /EHsc /LD /DWIN32 /D_WINDOWS /DUNICODE /D_UNICODE',
  ('"{0}"' -f $cpp),
  ('/link /MACHINE:X86 /DEF:"{0}" /OUT:"{1}" /PDB:"{2}" user32.lib gdi32.lib kernel32.lib' -f $def,$outDll,$outPdb)
) -join ' '

$cmd = ('call "{0}" x86 >nul && {1}' -f $vcvars,$compile)
& cmd.exe /d /s /c $cmd
if ($LASTEXITCODE -ne 0) { throw "R17.2 build failed: $LASTEXITCODE" }
if (-not (Test-Path $outDll)) { throw "R17.2 DLL missing" }

$report=[ordered]@{
  Phase="R17.2 Single DLL Deferred"
  Architecture="x86"
  Host="IGPLib_x86.dll"
  SecondaryLoadLibrary=$false
  DllMainStartsRuntime=$false
  Trigger="IGPLib::InitBridgeClass"
  DelayedStartMilliseconds=2000
  OverlayUIEnabled=$false
  HardenedPEValidation=$true
  RequireModuleName="AMS.exe"
  BuildCarVA="0x00A87960"
  SelectedCarIdHelperVA="0x00D805F0"
  SHA256=(Get-FileHash -Algorithm SHA256 -LiteralPath $outDll).Hash.ToLowerInvariant()
}
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $outDir "R172-BUILD-REPORT.json") -Encoding UTF8
Write-Host "R17.2 built: $outDll" -ForegroundColor Green
