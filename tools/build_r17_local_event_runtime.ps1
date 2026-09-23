param(
    [string]$SourceDir = "."
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$vswhere = Join-Path $pf86 "Microsoft Visual Studio\Installer\vswhere.exe"

function Resolve-VcVars {
    if ((Get-Command cl.exe -ErrorAction SilentlyContinue) -and
        $env:VSCMD_ARG_TGT_ARCH -eq "x86") {
        return $null
    }

    if (-not (Test-Path -LiteralPath $vswhere)) {
        throw "Visual Studio Build Tools nao encontrado. Instale Desktop development with C++ (x86)."
    }

    $install = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    if (-not $install) {
        throw "MSVC x86 nao encontrado. Instale o componente VC.Tools.x86.x64."
    }

    $vcvars = Join-Path $install "VC\Auxiliary\Build\vcvarsall.bat"
    if (-not (Test-Path -LiteralPath $vcvars)) {
        throw "vcvarsall.bat nao encontrado: $vcvars"
    }

    return $vcvars
}

$outDir = Join-Path $SourceDir "RUNTIME_STUBS"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$cpp = Join-Path $SourceDir "src-reconstructed\local-runtime\LocalEventRuntime.cpp"
$def = Join-Path $SourceDir "runtime-stubs\IGPLib_x86.def"
$outDll = Join-Path $outDir "IGPLib_x86.dll"
$outPdb = Join-Path $outDir "IGPLib_x86.pdb"

if (-not (Test-Path -LiteralPath $cpp)) { throw "Missing source: $cpp" }
if (-not (Test-Path -LiteralPath $def)) { throw "Missing DEF: $def" }

$vcvars = Resolve-VcVars

$compile = @(
    'cl.exe /nologo /std:c++17 /O2 /MT /EHsc /LD /DWIN32 /D_WINDOWS',
    ('"{0}"' -f $cpp),
    ('/link /MACHINE:X86 /DEF:"{0}" /OUT:"{1}" /PDB:"{2}" user32.lib gdi32.lib kernel32.lib' -f $def,$outDll,$outPdb)
) -join ' '

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " R17 - BUILD LOCAL EVENT RUNTIME" -ForegroundColor Cyan
Write-Host "============================================================"
Write-Host ""

if ($vcvars) {
    $cmd = ('call "{0}" x86 >nul && {1}' -f $vcvars,$compile)
    & cmd.exe /d /s /c $cmd
} else {
    & cmd.exe /d /s /c $compile
}

if ($LASTEXITCODE -ne 0) {
    throw "MSVC build failed with code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $outDll)) {
    throw "Build completed without output DLL: $outDll"
}

$report = [ordered]@{
    Phase = "R17 Local Event Runtime"
    Architecture = "x86"
    Host = "IGPLib_x86.dll"
    BuildCarVA = "0x00A87960"
    SelectedCarIdHelperVA = "0x00D805F0"
    StateFile = "%LOCALAPPDATA%\ReXtremeLocal\campaign.ini"
    RuntimeDll = $outDll
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $outDll).Hash.ToLowerInvariant()
    BinaryPatchToAMS = $false
    ReplacesOriginalBuildCarAtRuntime = $true
    OwnEventBus = $true
    OwnStore = $true
    OwnConsumers = @(
        "InventoryConsumer",
        "ProfileConsumer",
        "GarageConsumer",
        "PersistenceConsumer"
    )
    OwnUI = $true
}

$reportPath = Join-Path $outDir "R17-BUILD-REPORT.json"
$report | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Host ""
Write-Host "R17 runtime built." -ForegroundColor Green
Write-Host "DLL:    $outDll"
Write-Host "Report: $reportPath"
