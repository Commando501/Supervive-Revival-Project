# udp7777-listener.ps1 -- minimal UDP listener for the diagnostic test in
# session 7. Listens on UDP 7777, logs every received packet with timestamp,
# source endpoint, byte count, and the first 64 bytes hex-dumped, to
# Saved/Logs/udp7777-rx.log. Ctrl-C to stop.
#
# Usage:
#   .\udp7777-listener.ps1
#
# Purpose: verify whether the SUPERVIVE client (with browse_hook v10 active)
# actually sends a UDP packet to 127.0.0.1:7777 before its FMallocBinned2
# crash. If yes -> engine init reached the StatelessConnect first-send before
# the FString destructor fired -> the crash happens AFTER the wire activity,
# and browse_hook v11's UE-allocator work can target a specific narrow fix.
# If no -> the crash is pre-send and v11 must come first.

$logPath = 'G:\git\Supervive Revival Project\unreal-stub\Saved\Logs\udp7777-rx.log'
$logDir  = Split-Path $logPath
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$ErrorActionPreference = 'Continue'  # don't bail on transient errors

# Truncate log on start so each diagnostic run is its own file.
Set-Content -Path $logPath -Value "udp7777-listener started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff')`r`n"

$ep  = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 7777)
$udp = New-Object System.Net.Sockets.UdpClient $ep

Write-Host "Listening on UDP 0.0.0.0:7777 -- packets logged to $logPath" -ForegroundColor Cyan
Write-Host "Ctrl-C to stop." -ForegroundColor DarkGray

try {
  while ($true) {
    $remote = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
    $bytes  = $udp.Receive([ref]$remote)
    $ts     = Get-Date -Format 'HH:mm:ss.fff'
    # Dump the FULL packet so we can compare to UE5.4 StatelessConnect format.
    # Handshake packets are typically <200 bytes.
    $hex    = ($bytes | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
    $line   = "[$ts] RX $($bytes.Length)B from $remote : $hex"
    Write-Host $line -ForegroundColor Green
    Add-Content -Path $logPath -Value $line
  }
} finally {
  $udp.Close()
  Write-Host "Listener stopped." -ForegroundColor DarkGray
}
