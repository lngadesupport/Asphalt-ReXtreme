param(
    [ValidateSet("Install","Play","Repair","Update","Status")]
    [string]$Action = "Status",
    [string]$SourceDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PackageRoot = Join-Path $Root "_PACKAGE_PHASE5"
$CleanRoot = Join-Path $Root "CLEAN-1.7.3.8-EXTRACTED"
$CleanGame = Join-Path $CleanRoot "Game"
$RuntimeRoot = Join-Path $Root "runtime\python312-x86"
$StatePath = Join-Path $Root "_BETA_STATE.json"
$VersionPath = Join-Path $Root "beta\VERSION.json"
$ExpectedOriginalAms = "3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8"
$PackageName = "A278AB0D.AsphaltXtreme"
$BetaBranch = "public-beta-0.1"
$PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-win32.zip"
$PythonZipSize = 9960069

function Step([string]$Message) {
    Write-Host ("[ReXtreme Beta] " + $Message) -ForegroundColor Cyan
}

function Read-Version {
    if (-not (Test-Path -LiteralPath $VersionPath)) {
        throw "beta\VERSION.json nao encontrado."
    }
    return (Get-Content -LiteralPath $VersionPath -Raw | ConvertFrom-Json)
}

function Find-CompatibleGameRoot([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $ams = @(Get-ChildItem -LiteralPath $resolved -Recurse -File -Filter "AMS.exe" -ErrorAction SilentlyContinue)
    $matches = @()
    foreach ($file in $ams) {
        try {
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
            if ($hash -eq $ExpectedOriginalAms) {
                $matches += $file
            }
        } catch {}
    }
    if ($matches.Count -ne 1) {
        throw "Era esperado exatamente um AMS.exe pristine 1.7.3.8 x86 com SHA-256 $ExpectedOriginalAms; encontrados: $($matches.Count)."
    }
    $root = $matches[0].Directory.FullName
    if (-not (Test-Path -LiteralPath (Join-Path $root "AppxManifest.xml"))) {
        throw "AppxManifest.xml nao encontrado ao lado do AMS.exe compativel."
    }
    return $root
}

function Import-CleanSource([string]$Path) {
    if (Test-Path -LiteralPath (Join-Path $CleanGame "AMS.exe")) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $CleanGame "AMS.exe")).Hash.ToLowerInvariant()
        if ($hash -eq $ExpectedOriginalAms) {
            Step "Fonte limpa em cache ja e compativel; reutilizando."
            return
        }
        throw "O cache CLEAN-1.7.3.8-EXTRACTED existe mas nao possui o AMS pristine esperado."
    }

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $Path = Read-Host "Cole o caminho da pasta extraida do Asphalt Xtreme 1.7.3.8 x86"
    }
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Pasta de origem invalida."
    }

    $gameRoot = Find-CompatibleGameRoot $Path
    Step ("Importando fonte limpa de: " + $gameRoot)

    if (Test-Path -LiteralPath $CleanRoot) {
        Remove-Item -LiteralPath $CleanRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $CleanGame | Out-Null

    & robocopy.exe $gameRoot $CleanGame /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS /NP
    $rc = $LASTEXITCODE
    if ($rc -gt 7) {
        throw "Falha ao copiar fonte limpa. Robocopy=$rc"
    }

    $copiedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $CleanGame "AMS.exe")).Hash.ToLowerInvariant()
    if ($copiedHash -ne $ExpectedOriginalAms) {
        throw "Hash do AMS mudou durante a copia."
    }

    # If the source bundle also contains the VC120 framework APPX, make it discoverable
    # by the existing Phase 5 builder. Nothing is downloaded from unofficial mirrors.
    $dep = @(Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe*.appx" } |
        Select-Object -First 1)
    if ($dep) {
        Copy-Item -LiteralPath $dep.FullName -Destination (Join-Path $Root $dep.Name) -Force
        Step "VC120 x86 local encontrado e copiado para o bootstrap."
    }
}

function Ensure-PortablePython {
    $python = Join-Path $RuntimeRoot "python.exe"
    if (Test-Path -LiteralPath $python) {
        return $python
    }

    Step "Baixando runtime Python embeddable oficial (CPython 3.12.10 x86)..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $runtimeParent = Split-Path $RuntimeRoot -Parent
    New-Item -ItemType Directory -Force -Path $runtimeParent | Out-Null
    $zip = Join-Path $runtimeParent "python-3.12.10-embed-win32.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $zip

    $size = (Get-Item -LiteralPath $zip).Length
    if ($size -ne $PythonZipSize) {
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        throw "Runtime Python baixado com tamanho inesperado: $size bytes."
    }

    if (Test-Path -LiteralPath $RuntimeRoot) {
        Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $RuntimeRoot -Force
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue

    $pth = Join-Path $RuntimeRoot "python312._pth"
    if (-not (Test-Path -LiteralPath $pth)) {
        throw "python312._pth nao encontrado no runtime embeddable."
    }
    $lines = @(Get-Content -LiteralPath $pth)
    if ($lines -notcontains "..\..\tools") {
        Add-Content -LiteralPath $pth -Value "..\..\tools" -Encoding ASCII
    }

    if (-not (Test-Path -LiteralPath $python)) {
        throw "python.exe nao apareceu apos extracao."
    }
    return $python
}

function Repair-GhostRegistration {
    $backup = $null
    $current = @(Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue)

    foreach ($pkg in $current) {
        $location = [string]$pkg.InstallLocation
        $isGhost = [string]::IsNullOrWhiteSpace($location)

        if (-not $isGhost) {
            $isGhost = -not (Test-Path -LiteralPath $location -PathType Container)
        }

        if (-not $isGhost) {
            continue
        }

        Step ("Registro AppX orfao detectado: " + $pkg.PackageFullName)
        Step "InstallLocation esta vazio ou aponta para uma pasta que nao existe."

        if (-not $backup) {
            $backup = Backup-LocalState
        }

        Step "Removendo somente o registro AppX quebrado do usuario atual..."
        Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop

        $remaining = @(Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue)
        $bad = @($remaining | Where-Object {
            [string]::IsNullOrWhiteSpace([string]$_.InstallLocation) -or
            -not (Test-Path -LiteralPath ([string]$_.InstallLocation) -PathType Container)
        })
        if ($bad.Count -gt 0) {
            throw "O registro AppX orfao continuou presente apos Remove-AppxPackage."
        }

        Step "Registro AppX orfao removido com sucesso."
    }

    return $backup
}

function Assert-NoConflictingRegistration {
    $existing = @(Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue)
    foreach ($pkg in $existing) {
        if (-not $pkg.InstallLocation) { continue }
        if (Test-Path -LiteralPath $PackageRoot) {
            $expected = [IO.Path]::GetFullPath($PackageRoot).TrimEnd("\")
            $actual = [IO.Path]::GetFullPath($pkg.InstallLocation).TrimEnd("\")
            if ([StringComparer]::OrdinalIgnoreCase.Equals($expected,$actual)) {
                continue
            }
        }
        throw @"
Existe um Asphalt Xtreme registrado em outra pasta:
  $($pkg.InstallLocation)

O beta 0.1 ainda reutiliza temporariamente a identidade UWP original.
Por seguranca, o instalador NAO remove essa instalacao nem o LocalState automaticamente.
Use um perfil Windows limpo/de teste ou faca backup/remocao explicita antes de instalar o beta.
"@
    }
}

function Backup-LocalState {
    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending | Select-Object -First 1
    if (-not $pkg) { return $null }

    $local = Join-Path $env:LOCALAPPDATA ("Packages\" + $pkg.PackageFamilyName + "\LocalState")
    if (-not (Test-Path -LiteralPath $local)) { return $null }

    $backupRoot = Join-Path $Root "_BETA_SAVE_BACKUP"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $backupRoot $stamp
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Copy-Item -LiteralPath $local -Destination (Join-Path $backup "LocalState") -Recurse -Force
    Step ("Save backup: " + $backup)
    return $backup
}

function Restore-LocalState([string]$Backup) {
    if ([string]::IsNullOrWhiteSpace($Backup)) { return }
    $src = Join-Path $Backup "LocalState"
    if (-not (Test-Path -LiteralPath $src)) { return }

    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
        Sort-Object Version -Descending | Select-Object -First 1
    $dst = Join-Path $env:LOCALAPPDATA ("Packages\" + $pkg.PackageFamilyName + "\LocalState")
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Copy-Item -LiteralPath (Join-Path $src "*") -Destination $dst -Recurse -Force
    Step "Save LocalState restaurado."
}

function Build-Beta {
    $ghostBackup = Repair-GhostRegistration
    Assert-NoConflictingRegistration

    $phase2 = Join-Path $Root "tools\build_ams_phase2.ps1"
    $phase5 = Join-Path $Root "tools\build_package_phase5.ps1"
    $finalizer = Join-Path $Root "FINALIZE-CAMPAIGN-EDITION.cmd"
    foreach ($required in @($phase2,$phase5,$finalizer)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Arquivo de build ausente: $required"
        }
    }

    Step "Construindo AMS Phase 2 verificado..."
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $phase2 -SourceDir $Root
    if ($LASTEXITCODE -ne 0) { throw "AMS Phase 2 falhou: $LASTEXITCODE" }

    Step "Construindo/registrando Package Phase 5..."
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $phase5 -SourceDir $Root
    if ($LASTEXITCODE -ne 0) { throw "Package Phase 5 falhou: $LASTEXITCODE" }

    $python = Ensure-PortablePython
    $oldPath = $env:PATH
    $oldNoPause = $env:REXTREME_NO_PAUSE
    try {
        $env:PATH = $RuntimeRoot + ";" + $env:PATH
        $env:REXTREME_NO_PAUSE = "1"
        Step "Aplicando Campaign finalizer / Career Adapter v3..."
        & cmd.exe /d /c ('"' + $finalizer + '"')
        if ($LASTEXITCODE -ne 0) { throw "Campaign finalizer falhou: $LASTEXITCODE" }
    } finally {
        $env:PATH = $oldPath
        $env:REXTREME_NO_PAUSE = $oldNoPause
    }

    $version = Read-Version
    $state = [ordered]@{
        product = $version.product
        version = $version.version
        installed_at = (Get-Date).ToString("o")
        source_build = $version.source_build
        package_root = $PackageRoot
        startup_mode = "uwp-loose-compatibility"
        portable_startup_ready = $false
        campaign_final_status = (Join-Path $Root "_TRACE_MONTAR\CAMPAIGN-FINAL-STATUS.json")
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8

    if ($ghostBackup) {
        Restore-LocalState $ghostBackup
    }

    Step "Build do beta concluido."
}

function Install-Beta {
    Import-CleanSource $SourceDir
    Build-Beta
}

function Play-Beta {
    if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot "AppxManifest.xml"))) {
        throw "_PACKAGE_PHASE5 nao esta instalado. Rode INSTALL-BETA.cmd."
    }

    [xml]$manifest = Get-Content -LiteralPath (Join-Path $PackageRoot "AppxManifest.xml") -Raw
    $name = [string]$manifest.Package.Identity.Name
    $app = $manifest.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application'][1]")
    $appId = [string]$app.Id

    $pkg = Get-AppxPackage -Name $name -ErrorAction SilentlyContinue |
        Where-Object {
            $_.InstallLocation -and
            [StringComparer]::OrdinalIgnoreCase.Equals(
                [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd("\"),
                [IO.Path]::GetFullPath($PackageRoot).TrimEnd("\")
            )
        } |
        Sort-Object Version -Descending | Select-Object -First 1

    if (-not $pkg) {
        Step "Registro do beta ausente; registrando o layout local..."
        Add-AppxPackage -Register (Join-Path $PackageRoot "AppxManifest.xml") -ForceApplicationShutdown
        $pkg = Get-AppxPackage -Name $name -ErrorAction Stop |
            Sort-Object Version -Descending | Select-Object -First 1
    }

    Step ("Iniciando " + $pkg.PackageFamilyName + "!" + $appId)
    Start-Process "explorer.exe" -ArgumentList ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!" + $appId)
}

function Repair-Beta {
    if (-not (Test-Path -LiteralPath (Join-Path $CleanGame "AMS.exe"))) {
        throw "Fonte limpa em cache ausente. Rode INSTALL-BETA.cmd novamente com a fonte 1.7.3.8 x86."
    }

    $backup = Backup-LocalState
    Get-Process -Name "AMS" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    $pkg = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue |
        Where-Object {
            $_.InstallLocation -and
            (Test-Path -LiteralPath $PackageRoot) -and
            [StringComparer]::OrdinalIgnoreCase.Equals(
                [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd("\"),
                [IO.Path]::GetFullPath($PackageRoot).TrimEnd("\")
            )
        } | Select-Object -First 1
    if ($pkg) {
        Step "Removendo apenas o registro beta antes da reconstrucao..."
        Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
    }

    Build-Beta
    if ($backup) { Restore-LocalState $backup }
}

function Update-Beta {
    Step "Atualizando somente arquivos do projeto; jogo, fonte limpa e save nao sao tocados."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $base = "https://raw.githubusercontent.com/lngadesupport/Asphalt-ReXtreme/$BetaBranch"
    $paths = @(
        "INSTALL-BETA.cmd",
        "PLAY-BETA.cmd",
        "REPAIR-BETA.cmd",
        "UPDATE-BETA.cmd",
        "DIAGNOSE-BETA.cmd",
        "BISECT-BETA-STARTUP.cmd",
        "FINALIZE-CAMPAIGN-EDITION.cmd",
        "beta/VERSION.json",
        "docs/PUBLIC_BETA_0.1.0.md",
        "tools/public_beta.ps1",
        "tools/build_ams_phase2.ps1",
        "tools/build_package_phase5.ps1",
        "tools/capture_beta_runtime.ps1",
        "tools/beta_startup_bisect.ps1",
        "tools/campaign_garage_startup_probe.py",
        "tools/campaign_profile_adapter_v1.py",
        "tools/xtea_assets.py",
        "tools/rextreme_economy.py",
        "tools/economy_audit.py",
        "tools/build_campaign_vehicle_catalog.py",
        "tools/build_campaign_event_catalog.py",
        "tools/build_campaign_upgrade_catalog.py",
        "tools/build_campaign_objective_catalog.py",
        "tools/build_campaign_objective_catalog_from_package.py",
        "tools/build_campaign_upgrade_ui_map.py",
        "tools/build_campaign_production_data.py",
        "tools/build_campaign_auxiliary_data.py",
        "tools/build_campaign_store_catalog.py",
        "tools/build_campaign_store_from_shop.py",
        "tools/audit_campaign_store_keys_from_package.py",
        "tools/campaign_garage_v2.py",
        "tools/campaign_career_adapter_v2.py",
        "tools/campaign_career_adapter_v3.py",
        "tools/campaign_upgrade_adapter_v1.py",
        "tools/campaign_store_adapter_v1.py",
        "tools/validate_campaign_data_prepatch.py",
        "tools/validate_campaign_final.py"
    )

    $tmp = Join-Path $env:TEMP ("ReXtremeBetaUpdate-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    try {
        foreach ($rel in $paths) {
            $uri = $base + "/" + ($rel -replace "\\","/") + "?channel=beta1-sync"
            $dst = Join-Path $tmp $rel
            New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
            Invoke-WebRequest -UseBasicParsing -Headers @{"Cache-Control"="no-cache"} -Uri $uri -OutFile $dst
        }

        foreach ($rel in $paths) {
            $src = Join-Path $tmp $rel
            $dst = Join-Path $Root $rel
            New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
            Copy-Item -LiteralPath $src -Destination $dst -Force
        }
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    $v = Read-Version
    Step ("Atualizado para canal " + $v.channel + " / " + $v.version)
    Write-Host "Se houver mudanca de runtime Campaign, rode REPAIR-BETA.cmd."
}

function Show-Status {
    $v = Read-Version
    Write-Host ""
    Write-Host $v.product -ForegroundColor Green
    Write-Host ("Version: " + $v.version)
    Write-Host ("Channel: " + $v.channel)
    Write-Host ("Startup: " + $v.startup_mode)
    Write-Host ("Portable startup ready: " + $v.portable_startup_ready)
    if (Test-Path -LiteralPath $StatePath) {
        Write-Host ""
        Get-Content -LiteralPath $StatePath
    }
}

try {
    switch ($Action) {
        "Install" { Install-Beta }
        "Play"    { Play-Beta }
        "Repair"  { Repair-Beta }
        "Update"  { Update-Beta }
        "Status"  { Show-Status }
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host ("[ERRO] " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
