param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$CampaignRoot=Join-Path $GameRoot "CampaignProfile"
$Seed=Join-Path $CampaignRoot "seed"
$User=Join-Path $CampaignRoot "user"

$PFN="A278AB0D.AsphaltXtreme_h6adky7gbf63m"
$AppId="App"
$LocalState=Join-Path $env:LOCALAPPDATA ("Packages\"+$PFN+"\LocalState")

if(-not (Test-Path -LiteralPath (Join-Path $GameRoot "AMS.exe") -PathType Leaf)){
    throw "Campaign game tree not found."
}
if(-not (Test-Path -LiteralPath $Seed -PathType Container)){
    throw "Embedded CampaignProfile seed not found. Run BUILD-PROFILE-PHASE8-EMBEDDED.cmd first."
}

New-Item -ItemType Directory -Path $LocalState -Force | Out-Null
New-Item -ItemType Directory -Path $User -Force | Out-Null

$names=@("localprofile","profile","settings")
foreach($name in $names){
    $local=Join-Path $LocalState $name
    $userFile=Join-Path $User $name
    $seedFile=Join-Path $Seed $name

    # Persistent user mirror wins. Seed is only the fallback.
    if(Test-Path -LiteralPath $userFile -PathType Leaf){
        Copy-Item -LiteralPath $userFile -Destination $local -Force
    } elseif(Test-Path -LiteralPath $seedFile -PathType Leaf) {
        Copy-Item -LiteralPath $seedFile -Destination $local -Force
    }
}

Write-Host "Campaign profile restored to LocalState." -ForegroundColor Cyan
Write-Host "Launching Asphalt ReXtreme..." -ForegroundColor Cyan

Start-Process "explorer.exe" ("shell:AppsFolder\\"+$PFN+"!"+$AppId)

$proc=$null
for($i=0;$i -lt 60;$i++){
    Start-Sleep -Milliseconds 500
    $proc=Get-Process -Name "AMS" -ErrorAction SilentlyContinue | Select-Object -First 1
    if($proc){break}
}
if(-not $proc){
    throw "AMS.exe did not start. The UWP package may need to be registered again."
}

try {
    Wait-Process -Id $proc.Id
} finally {
    Start-Sleep -Milliseconds 500

    foreach($name in $names){
        $local=Join-Path $LocalState $name
        if(Test-Path -LiteralPath $local -PathType Leaf){
            $tmp=Join-Path $User ($name+".tmp")
            Copy-Item -LiteralPath $local -Destination $tmp -Force
            Move-Item -LiteralPath $tmp -Destination (Join-Path $User $name) -Force
        }
    }

    $mirror=[ordered]@{
        LastSync=(Get-Date).ToString("o")
        Source=$LocalState
        Destination=$User
        Files=@()
    }
    foreach($name in $names){
        $p=Join-Path $User $name
        if(Test-Path -LiteralPath $p -PathType Leaf){
            $mirror.Files += [ordered]@{
                Name=$name
                Size=(Get-Item -LiteralPath $p).Length
                SHA256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
    }
    $mirror | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath (Join-Path $CampaignRoot "last-user-mirror.json") -Encoding UTF8

    Write-Host "Campaign profile mirrored back into the game tree." -ForegroundColor Green
}
