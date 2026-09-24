param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot,
  [Parameter(Mandatory=$true)][string]$OutputDir
)
$ErrorActionPreference="Continue"
Set-StrictMode -Version Latest
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$GameRoot=Join-Path $ProjectRoot "_PACKAGE_PHASE5"
New-Item -ItemType Directory -Path $OutputDir -Force|Out-Null
$out=New-Object System.Collections.Generic.List[object]
$files=Get-ChildItem -LiteralPath $GameRoot -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
  $_.FullName -notmatch '\\_(PROFILE|RUNTIME|LOCAL_BACKEND)' -and $_.Extension -ne '.bak' -and
  $_.Length -le 120MB -and ($_.Extension -match '^\.(exe|dll|json|xml|txt|cfg|ini|dat|bin)$' -or $_.Name -match '(?i)manifest|config|server|network')
}
foreach($f in $files){
  try{
    [byte[]]$b=[IO.File]::ReadAllBytes($f.FullName)
    $a=[Text.Encoding]::GetEncoding(28591).GetString($b)
    $u=[Text.Encoding]::Unicode.GetString($b)
    foreach($pair in @(@("ASCII",$a),@("UTF16LE",$u))){
      $enc=$pair[0];$s=$pair[1]
      $vals=New-Object System.Collections.Generic.HashSet[string]([StringComparer]::OrdinalIgnoreCase)
      foreach($m in [regex]::Matches($s,'(?i)https?://[a-z0-9._~:/?#\[\]@!$&''()*+,;=%-]{4,}')){[void]$vals.Add($m.Value.Trim([char]0))}
      foreach($m in [regex]::Matches($s,'(?i)(?:[a-z0-9-]{1,63}\.)+(?:com|net|org|io|co|me|app|cloud|games|gameloft|microsoft|windows)(?::\d{1,5})?')){[void]$vals.Add($m.Value)}
      foreach($m in [regex]::Matches($s,'(?i)[a-z0-9._/-]{0,80}(?:gameloft|asphalt|xtreme)[a-z0-9._/?=&%-]{0,120}')){if($m.Value.Length -ge 6){[void]$vals.Add($m.Value)}}
      foreach($v in $vals){
        $out.Add([pscustomobject]@{File=$f.FullName.Substring($GameRoot.Length).TrimStart('\');Encoding=$enc;Value=$v})
      }
    }
  }catch{}
}
$out|Sort-Object Value,File -Unique|Export-Csv -LiteralPath (Join-Path $OutputDir "STATIC-NETWORK-STRINGS.csv") -NoTypeInformation -Encoding UTF8
