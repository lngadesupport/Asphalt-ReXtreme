param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    [switch]$Restore
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
$Ams=Join-Path $GameRoot "AMS.exe"
$BackupRoot=Join-Path $GameRoot "_PROFILE_PHASE9_BACKUP"
$AmsBackup=Join-Path $BackupRoot "AMS.phase5.bak"
$Report=Join-Path $GameRoot "PROFILE-PHASE9-INTERNAL-REPORT.json"

$ExpectedPhase5="56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"

if(-not (Test-Path -LiteralPath $Ams -PathType Leaf)){
    throw "AMS.exe not found: $Ams"
}

function Get-Hash([string]$p){
    (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}

if($Restore){
    if(-not (Test-Path -LiteralPath $AmsBackup -PathType Leaf)){
        throw "Phase 9 backup not found: $AmsBackup"
    }
    if((Get-Hash $AmsBackup) -ne $ExpectedPhase5){
        throw "Phase 9 AMS backup is not verified Phase 5."
    }

    Copy-Item -LiteralPath $AmsBackup -Destination $Ams -Force

    $resourceManifest=Join-Path $BackupRoot "resource-backups.json"
    if(Test-Path -LiteralPath $resourceManifest -PathType Leaf){
        $items=Get-Content -LiteralPath $resourceManifest -Raw | ConvertFrom-Json
        foreach($item in @($items)){
            $src=Join-Path $BackupRoot ("resources\"+$item.RelativePath)
            $dst=Join-Path $GameRoot $item.RelativePath
            if(Test-Path -LiteralPath $src -PathType Leaf){
                Copy-Item -LiteralPath $src -Destination $dst -Force
            }
        }
    }

    Write-Host ""
    Write-Host "PHASE 9 RESTORED TO VERIFIED PHASE 5" -ForegroundColor Green
    exit 0
}

$current=Get-Hash $Ams
if($current -ne $ExpectedPhase5){
    $candidates=@(
        (Join-Path $GameRoot "AMS.PHASE5.RETRY-ID.bak"),
        (Join-Path $GameRoot "AMS.PHASE5.BACKUP.exe"),
        (Join-Path $GameRoot "_PROFILE_PHASE6_BACKUP\AMS.phase5.bak")
    )
    $restored=$false
    foreach($candidate in $candidates){
        if(-not (Test-Path -LiteralPath $candidate -PathType Leaf)){continue}
        if((Get-Hash $candidate) -eq $ExpectedPhase5){
            Copy-Item -LiteralPath $candidate -Destination $Ams -Force
            $restored=$true
            break
        }
    }
    if(-not $restored){
        throw "Verified Phase 5 AMS required. Current hash: $current"
    }
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Copy-Item -LiteralPath $Ams -Destination $AmsBackup -Force

[byte[]]$d=[IO.File]::ReadAllBytes($Ams)

$patches=@(
    [pscustomobject]@{
        Name="Campaign local profile: failed first validation still enters valid-result path"
        Offset=[Convert]::ToInt32("0069B8C6",16)
        Before=[byte[]](0x74,0x24)
        After=[byte[]](0x74,0x22)
    },
    [pscustomobject]@{
        Name="Campaign local profile: failed secondary validation returns valid"
        Offset=[Convert]::ToInt32("0069B8E6",16)
        Before=[byte[]](0x32,0xC0)
        After=[byte[]](0xB0,0x01)
    },
    [pscustomobject]@{
        Name="Campaign startup: bypass dead remote-profile sync gate"
        Offset=[Convert]::ToInt32("0092B82A",16)
        Before=[byte[]](0x0F,0x84,0x8D,0x01,0x00,0x00)
        After=[byte[]](0xE9,0x8E,0x01,0x00,0x00,0x90)
    }
)

$patchReport=@()
foreach($p in $patches){
    for($i=0;$i -lt $p.Before.Length;$i++){
        if($d[$p.Offset+$i] -ne $p.Before[$i]){
            throw ("Unexpected byte for {0} at 0x{1:X8}: expected {2:X2}, got {3:X2}" -f
                $p.Name,($p.Offset+$i),$p.Before[$i],$d[$p.Offset+$i])
        }
    }
    [Array]::Copy($p.After,0,$d,$p.Offset,$p.After.Length)
    $patchReport += [ordered]@{
        Name=$p.Name
        Offset=("0x{0:X8}" -f $p.Offset)
        Before=(($p.Before | ForEach-Object {$_.ToString("X2")}) -join " ")
        After=(($p.After | ForEach-Object {$_.ToString("X2")}) -join " ")
    }
}

[IO.File]::WriteAllBytes($Ams,$d)

# Internal UI text patch. Both phrases are 26 characters, so a raw replacement
# cannot shift resource offsets.
$OldText="VERIFICANDO PERFIL ON-LINE"
$NewText="CARREGANDO PERFIL LOCAL..."
if($OldText.Length -ne $NewText.Length){
    throw "Internal UI strings must be the same length."
}

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
public static class ReXtremePhase9Search {
    public static int[] FindAll(byte[] h, byte[] n) {
        if (h == null || n == null || n.Length == 0 || n.Length > h.Length)
            return new int[0];
        var r = new List<int>();
        int start=0;
        while(start <= h.Length-n.Length) {
            int p=Array.IndexOf<byte>(h,n[0],start);
            if(p<0 || p>h.Length-n.Length) break;
            bool ok=true;
            for(int j=1;j<n.Length;j++) if(h[p+j]!=n[j]) { ok=false; break; }
            if(ok) r.Add(p);
            start=p+1;
        }
        return r.ToArray();
    }
}
"@

$resourceBackups=@()
$textPatches=@()
$resourceBackupDir=Join-Path $BackupRoot "resources"
New-Item -ItemType Directory -Path $resourceBackupDir -Force | Out-Null

$oldA=[Text.Encoding]::UTF8.GetBytes($OldText)
$newA=[Text.Encoding]::UTF8.GetBytes($NewText)
$oldW=[Text.Encoding]::Unicode.GetBytes($OldText)
$newW=[Text.Encoding]::Unicode.GetBytes($NewText)

$candidates=Get-ChildItem -LiteralPath $GameRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notlike "$BackupRoot*" -and
        $_.Name -ne "AMS.exe" -and
        $_.Length -gt 0 -and $_.Length -le 64MB -and
        ($_.Extension.ToLowerInvariant() -in @(".pri",".xbf",".xml",".json",".txt",".bin",".dat",".loc",".res"))
    }

foreach($f in $candidates){
    try{
        [byte[]]$b=[IO.File]::ReadAllBytes($f.FullName)
        $changed=$false
        foreach($pair in @(
            [pscustomobject]@{Name="UTF8";Old=$oldA;New=$newA},
            [pscustomobject]@{Name="UTF16LE";Old=$oldW;New=$newW}
        )){
            $hits=[ReXtremePhase9Search]::FindAll($b,$pair.Old)
            if($hits.Length -eq 0){continue}

            $rel=$f.FullName.Substring($GameRoot.Length).TrimStart("\")
            if(-not $changed){
                $backupFile=Join-Path $resourceBackupDir $rel
                New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
                Copy-Item -LiteralPath $f.FullName -Destination $backupFile -Force
                $resourceBackups += [ordered]@{RelativePath=$rel}
            }

            foreach($off in $hits){
                [Array]::Copy($pair.New,0,$b,$off,$pair.New.Length)
                $textPatches += [ordered]@{
                    File=$rel
                    Encoding=$pair.Name
                    Offset=("0x{0:X8}" -f $off)
                    Before=$OldText
                    After=$NewText
                }
            }
            $changed=$true
        }
        if($changed){[IO.File]::WriteAllBytes($f.FullName,$b)}
    }catch{}
}

$resourceBackups | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $BackupRoot "resource-backups.json") -Encoding UTF8

$status=[ordered]@{
    Phase="9-internal-campaign-profile"
    Model="native-default-profile-object; remote sync bypassed"
    OriginalAMS_SHA256=$ExpectedPhase5
    PatchedAMS_SHA256=Get-Hash $Ams
    BinaryPatches=$patchReport
    InternalTextPatches=$textPatches
    RequiresProfileSeedFile=$false
    RequiresExternalOverlay=$false
    Notes=@(
        "The game already constructs its default profile object in memory.",
        "Phase 9 forces that local object to be accepted and skips the dead remote startup sync gate.",
        "Normal game persistence remains responsible for writing future local profile state."
    )
}
$status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Report -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " PHASE 9 INTERNAL CAMPAIGN PROFILE APPLIED" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "Native AMS patches: 3"
Write-Host ("Internal UI text patches: {0}" -f $textPatches.Count)
Write-Host ("Patched AMS SHA-256: {0}" -f $status.PatchedAMS_SHA256)
Write-Host ""
Write-Host "No localprofile/profile seed file is required." -ForegroundColor Cyan
Write-Host "Launch the registered game normally and test startup."
Write-Host ""
