param(
  [Parameter(Mandatory=$true)][string]$OutputDir
)
$ErrorActionPreference="Continue"
Set-StrictMode -Version Latest
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$log=Join-Path $OutputDir "local-backend.log"
$stop=Join-Path $OutputDir "STOP"
function L([string]$m){("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$m)|Add-Content -LiteralPath $log -Encoding UTF8}
function Get-Sni([byte[]]$b){
  try{
    if($b.Length -lt 6 -or $b[0] -ne 0x16){return ""}
    $p=5
    if($b[$p] -ne 0x01){return ""}
    $p+=4+2+32
    $sid=$b[$p];$p+=1+$sid
    $cs=($b[$p]*256)+$b[$p+1];$p+=2+$cs
    $cm=$b[$p];$p+=1+$cm
    $extLen=($b[$p]*256)+$b[$p+1];$p+=2
    $end=[Math]::Min($b.Length,$p+$extLen)
    while($p+4 -le $end){
      $type=($b[$p]*256)+$b[$p+1]
      $len=($b[$p+2]*256)+$b[$p+3]
      $p+=4
      if($type -eq 0 -and $p+5 -le $end){
        $q=$p+2
        if($b[$q] -ne 0){return ""}
        $n=($b[$q+1]*256)+$b[$q+2]
        if($q+3+$n -le $b.Length){return [Text.Encoding]::ASCII.GetString($b,$q+3,$n)}
      }
      $p+=$len
    }
  }catch{}
  return ""
}
function Handle([System.Net.Sockets.TcpClient]$c,[int]$port){
  try{
    $c.ReceiveTimeout=1500;$c.SendTimeout=1500
    $s=$c.GetStream()
    $buf=New-Object byte[] 16384
    $n=$s.Read($buf,0,$buf.Length)
    if($n -le 0){return}
    [byte[]]$d=$buf[0..($n-1)]
    if($d[0] -eq 0x16){
      $sni=Get-Sni $d
      L ("TLS port={0} remote={1} sni={2} bytes={3}" -f $port,$c.Client.RemoteEndPoint,$sni,$n)
      return
    }
    $txt=[Text.Encoding]::UTF8.GetString($d)
    $first=($txt -split "\r?\n")[0]
    $host=""
    foreach($line in ($txt -split "\r?\n")){if($line -match '^(?i)Host:\s*(.+)$'){$host=$Matches[1].Trim();break}}
    L ("HTTP port={0} remote={1} host={2} request={3}" -f $port,$c.Client.RemoteEndPoint,$host,$first)
    $body='{"status":"ok","success":true,"code":0,"data":{},"server":"ReXtreme Local Backend"}'
    $bytes=[Text.Encoding]::UTF8.GetBytes($body)
    $crlf=[string][char]13+[char]10
    $hdr="HTTP/1.1 200 OK"+$crlf+"Content-Type: application/json; charset=utf-8"+$crlf+"Content-Length: "+$bytes.Length+$crlf+"Connection: close"+$crlf+"Cache-Control: no-store"+$crlf+$crlf
    $hb=[Text.Encoding]::ASCII.GetBytes($hdr)
    $s.Write($hb,0,$hb.Length);$s.Write($bytes,0,$bytes.Length);$s.Flush()
  }catch{L ("HANDLE-ERROR port={0} {1}" -f $port,$_.Exception.Message)}
  finally{try{$c.Close()}catch{}}
}
$ls=@()
foreach($p in @(80,443,8080,8443)){
  try{
    $l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
    $l.Start()
    $ls += [pscustomobject]@{Port=$p;Listener=$l}
    L ("LISTEN 127.0.0.1:{0}" -f $p)
  }catch{L ("BIND-ERROR 127.0.0.1:{0} {1}" -f $p,$_.Exception.Message)}
}
L "ReXtreme Local Backend discovery server started."
while(-not (Test-Path -LiteralPath $stop)){
  foreach($x in $ls){
    try{if($x.Listener.Pending()){Handle ($x.Listener.AcceptTcpClient()) $x.Port}}catch{L ("ACCEPT-ERROR {0}" -f $_.Exception.Message)}
  }
  Start-Sleep -Milliseconds 100
}
foreach($x in $ls){try{$x.Listener.Stop()}catch{}}
L "Server stopped."
