param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot = Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams = Join-Path $GameRoot "AMS.exe"

$PFN = "A278AB0D.AsphaltXtreme_h6adky7gbf63m"
$LocalState = Join-Path $env:LOCALAPPDATA ("Packages\" + $PFN + "\LocalState")
$ExpectedAms = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

if (-not (Test-Path -LiteralPath $Ams -PathType Leaf)) {
    throw "Phase 5 game tree not found: $Ams"
}

# Always return to the verified Phase 5 binary before building Phase 8.
$current = (Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()
if ($current -ne $ExpectedAms) {
    $candidates = @(
        (Join-Path $GameRoot "AMS.PHASE5.RETRY-ID.bak"),
        (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
        (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak")
    )

    $restored = $false
    foreach($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $h = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($h -eq $ExpectedAms) {
            Copy-Item -LiteralPath $candidate -Destination $Ams -Force
            $restored = $true
            break
        }
    }

    if (-not $restored) {
        throw "AMS.exe is not verified Phase 5 and no verified Phase 5 backup was found. Current hash: $current"
    }
}

if (-not (Test-Path -LiteralPath $LocalState -PathType Container)) {
    throw "LocalState not found: $LocalState. Launch the registered game at least once first."
}

$required = @("localprofile","profile")
$optional = @("settings")

function Test-RequiredProfileFiles {
    foreach($name in $required) {
        $p = Join-Path $LocalState $name
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { return $false }
        if ((Get-Item -LiteralPath $p).Length -le 0) { return $false }
    }
    return $true
}

if (-not (Test-RequiredProfileFiles)) {
    Write-Host ""
    Write-Host "No existing LocalState profile was found." -ForegroundColor Yellow
    Write-Host "Bootstrapping a clean profile with the game's own initialization code..." -ForegroundColor Cyan

    $manifest = Join-Path $GameRoot "AppxManifest.xml"
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "AppxManifest.xml not found: $manifest"
    }

    # Re-register this exact Phase 5 tree. This also repairs stale/broken
    # shell:AppsFolder registration after an accidental uninstall.
    Write-Host "Registering Campaign package tree..." -ForegroundColor Cyan
    Add-AppxPackage -Register $manifest -ForceApplicationShutdown

    New-Item -ItemType Directory -Path $LocalState -Force | Out-Null

    # Launch only to let the original game code create its valid profile containers.
    Start-Process "explorer.exe" ("shell:AppsFolder\\" + $PFN + "!App")

    $created = $false
    for($i=0; $i -lt 120; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-RequiredProfileFiles) {
            $created = $true
            break
        }
    }

    # We only needed the game's serializer/initializer to create the seed.
    $amsProc = Get-Process -Name "AMS" -ErrorAction SilentlyContinue
    if ($amsProc) {
        $amsProc | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }

    if (-not $created) {
        throw "The game did not create localprofile/profile during bootstrap."
    }

    Write-Host "Game-generated Campaign profile seed created successfully." -ForegroundColor Green
}

$CampaignRoot = Join-Path $GameRoot "CampaignProfile"
$Seed = Join-Path $CampaignRoot "seed"
$User = Join-Path $CampaignRoot "user"
New-Item -ItemType Directory -Path $Seed -Force | Out-Null
New-Item -ItemType Directory -Path $User -Force | Out-Null

$profileFiles = @()
foreach($name in ($required + $optional)) {
    $src = Join-Path $LocalState $name
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { continue }

    # Seed is immutable after first capture; user mirror is refreshed now.
    $seedDst = Join-Path $Seed $name
    if (-not (Test-Path -LiteralPath $seedDst -PathType Leaf)) {
        Copy-Item -LiteralPath $src -Destination $seedDst -Force
    }
    Copy-Item -LiteralPath $src -Destination (Join-Path $User $name) -Force

    $profileFiles += [ordered]@{
        Name=$name
        Size=(Get-Item -LiteralPath $src).Length
        SHA256=(Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

# Conservative native text patch: only exact same-size strings are replaced.
# This modifies the game's own resource bytes when the localized phrase is stored plainly.
$oldText = "VERIFICANDO PERFIL ON-LINE"
$newText = "CARREGANDO PERFIL LOCAL..."
if ($oldText.Length -ne $newText.Length) {
    throw "Internal text replacement must preserve character count."
}

function Find-AllBytes([byte[]]$Haystack,[byte[]]$Needle) {
    $hits = New-Object System.Collections.Generic.List[int]
    if ($Needle.Length -eq 0 -or $Needle.Length -gt $Haystack.Length) { return @() }
    for($i=0; $i -le $Haystack.Length-$Needle.Length; $i++) {
        if($Haystack[$i] -ne $Needle[0]) { continue }
        $ok=$true
        for($j=1; $j -lt $Needle.Length; $j++) {
            if($Haystack[$i+$j] -ne $Needle[$j]) { $ok=$false; break }
        }
        if($ok) { $hits.Add($i); $i += $Needle.Length-1 }
    }
    return $hits.ToArray()
}

$patchHits = @()
$extensions = @(".xml",".json",".txt",".bin",".dat",".loc",".pri",".xbf",".res",".pak")
$files = Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notlike "$CampaignRoot*" -and
        $_.Length -gt 0 -and $_.Length -le 64MB -and
        ($extensions -contains $_.Extension.ToLowerInvariant())
    }

$asciiOld=[Text.Encoding]::UTF8.GetBytes($oldText)
$asciiNew=[Text.Encoding]::UTF8.GetBytes($newText)
$wideOld=[Text.Encoding]::Unicode.GetBytes($oldText)
$wideNew=[Text.Encoding]::Unicode.GetBytes($newText)

foreach($file in $files) {
    try {
        [byte[]]$bytes=[IO.File]::ReadAllBytes($file.FullName)
        $changed=$false

        foreach($pair in @(
            [pscustomobject]@{Encoding="UTF8";Old=$asciiOld;New=$asciiNew},
            [pscustomobject]@{Encoding="UTF16LE";Old=$wideOld;New=$wideNew}
        )) {
            $hits=Find-AllBytes $bytes $pair.Old
            foreach($off in $hits) {
                [Array]::Copy($pair.New,0,$bytes,$off,$pair.New.Length)
                $patchHits += [ordered]@{
                    File=$file.FullName.Substring($GameRoot.Length).TrimStart("\")
                    Encoding=$pair.Encoding
                    Offset=("0x{0:X8}" -f $off)
                    Old=$oldText
                    New=$newText
                }
                $changed=$true
            }
        }

        if($changed) {
            [IO.File]::WriteAllBytes($file.FullName,$bytes)
        }
    } catch {}
}

# Also record where the localization keys exist, without rewriting them.
$keyHits=@()
$keys=@("STR_MENU_SYNC_LOADING","STR_POPUP_LOGIN_ERROR_DESCRIPTION","STR_POPUP_LOGIN_ERROR_TITLE")
foreach($file in $files) {
    try {
        [byte[]]$bytes=[IO.File]::ReadAllBytes($file.FullName)
        foreach($key in $keys) {
            foreach($enc in @(
                [pscustomobject]@{Name="UTF8";Bytes=[Text.Encoding]::UTF8.GetBytes($key)},
                [pscustomobject]@{Name="UTF16LE";Bytes=[Text.Encoding]::Unicode.GetBytes($key)}
            )) {
                foreach($off in (Find-AllBytes $bytes $enc.Bytes)) {
                    $keyHits += [ordered]@{
                        File=$file.FullName.Substring($GameRoot.Length).TrimStart("\")
                        Key=$key
                        Encoding=$enc.Name
                        Offset=("0x{0:X8}" -f $off)
                    }
                }
            }
        }
    } catch {}
}

$manifest=[ordered]@{
    Edition="Asphalt ReXtreme: Campaign Edition"
    ProfileModel="embedded-seed-plus-persistent-user-mirror"
    PackageFamilyName=$PFN
    LocalState=$LocalState
    AMS_SHA256=(Get-FileHash -LiteralPath $Ams -Algorithm SHA256).Hash.ToLowerInvariant()
    Files=$profileFiles
    NativeLoadingTextPatches=$patchHits
    LocalizationKeyHits=$keyHits
    Notes=@(
        "CampaignProfile\\seed is the immutable embedded baseline profile.",
        "CampaignProfile\\user is the persistent mirrored user profile.",
        "LocalState remains the writable runtime copy required by UWP.",
        "No profile-creation UI is required when the embedded profile is available."
    )
}
$manifest | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $CampaignRoot "campaign-profile-manifest.json") -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 8 EMBEDDED CAMPAIGN PROFILE READY" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ("Embedded profile files: {0}" -f $profileFiles.Count)
Write-Host ("Native loading-text patches: {0}" -f $patchHits.Count)
Write-Host ("Localization-key hits: {0}" -f $keyHits.Count)
Write-Host ("Profile root: {0}" -f $CampaignRoot)
Write-Host ""
