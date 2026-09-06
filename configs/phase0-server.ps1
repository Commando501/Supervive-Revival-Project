<#
.SYNOPSIS
  S74 / B1 Phase-0 gate: does the shipping SUPERVIVE-Win64-Shipping.exe run as a
  dedicated (or listen) SERVER at all? This is the make-or-break test for the
  "real exe as the dedicated server" route (docs/session-74-b1-real-exe-as-server-scoping.md).

.DESCRIPTION
  Launches a SECOND instance of the real client binary in a SERVER role, pointed at
  the tutorial map + the full BP_LokiGameMode_Tutorial, with its log sent to a SEPARATE
  file (-abslog) so it does not clobber the client's Loki.log. Then tails that log and
  classifies the outcome GO / NO-GO / (expected) bootstrap-error.

  We are NOT trying to reach playable here. We only want to know whether the process
  enters a SERVER code path: binds an IpNetDriver listener AND/OR ULokiGameInstance
  constructs ULokiServerPlatformInstance. If it does (even if it then errors on Agones /
  AccelByte-server auth), B1 is ALIVE. If it silently runs as a client / never listens /
  exits immediately, B1 is DEAD.

  PREREQ (recommended, not required): run the normal redirect first so the server
  instance's AccelByte/server calls are answered rather than hanging on NXDOMAIN:
      .\configs\launch-redirect.ps1 -NoLaunch
  That sets hosts + cacert + starts ags (:8080/:443) WITHOUT launching the client.
  Phase 0 also passes -ini: AccelByte overrides to localhost:8080 directly.

  Requires elevation (to kill the prior elevated DS stub holding :7777).

.PARAMETER Mode        'dedicated' (default, headless -server) or 'listen' (?listen).
.PARAMETER Port        Server port (default 7777 — matches the client's S62 travel target).
.PARAMETER NoSteam     Add -nosteam (a dedicated server usually needs no Steam client auth).
.PARAMETER NullRhi     Add -nullrhi -nosplash -unattended (standard DS args; drop if it misbehaves).
.PARAMETER KillClient  Also kill a running SUPERVIVE client instance (off by default — the
                       S73 client may be mid-use; Phase 0 doesn't need it and abslog keeps logs separate).
.PARAMETER GameRoot    SUPERVIVE install (folder containing Loki\Binaries).
.PARAMETER WatchSeconds How long to tail+classify the server log (default 120).

.EXAMPLE  .\configs\phase0-server.ps1
.EXAMPLE  .\configs\phase0-server.ps1 -Mode listen
.EXAMPLE  .\configs\phase0-server.ps1 -NoSteam -NullRhi
#>
param(
  [ValidateSet('dedicated','listen')] [string]$Mode = 'dedicated',
  [int]$Port = 7777,
  [switch]$NoSteam,
  [switch]$NullRhi,
  [switch]$KillClient,
  [string]$GameRoot = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE",
  [int]$WatchSeconds = 120
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$exe      = Join-Path $GameRoot "Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
$srvLog   = Join-Path $repoRoot "docs\phase0-server.log"
$mapUrl   = "/Game/Loki/Maps/Tutorial/LVL_Tutorial"
$gmPath   = "/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C"

# ---- require admin (to kill the elevated DS stub on :7777) ----
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
  Write-Host "Elevation required (kill prior elevated stub + clean :$Port). Relaunching as admin..." -ForegroundColor Yellow
  $al = @("-NoExit","-ExecutionPolicy","Bypass","-File",$PSCommandPath,"-Mode",$Mode,"-Port",$Port,"-GameRoot",$GameRoot,"-WatchSeconds",$WatchSeconds)
  if ($NoSteam)    { $al += "-NoSteam" }
  if ($NullRhi)    { $al += "-NullRhi" }
  if ($KillClient) { $al += "-KillClient" }
  Start-Process powershell -Verb RunAs -ArgumentList $al
  return
}

if (-not (Test-Path $exe)) { throw "Shipping exe not found: $exe" }

# ---- free port $Port: kill the S73 DS stub (UnrealEditor-Cmd) if present ----
$stub = Get-Process UnrealEditor-Cmd -ErrorAction SilentlyContinue
if ($stub) {
  Write-Host "Killing DS stub (UnrealEditor-Cmd PID $($stub.Id -join ',')) to free :$Port..." -ForegroundColor Cyan
  $stub | ForEach-Object { try { Stop-Process $_ -Force } catch {} }
  Start-Sleep -Seconds 2
}

# ---- report/handle a running client instance ----
$client = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue
if ($client) {
  if ($KillClient) {
    Write-Host "Killing running SUPERVIVE client (PID $($client.Id -join ',')) per -KillClient..." -ForegroundColor Cyan
    $client | ForEach-Object { try { Stop-Process $_ -Force } catch {} }
    Start-Sleep -Seconds 2
  } else {
    Write-Warning "A SUPERVIVE-Win64-Shipping.exe is already running (PID $($client.Id -join ',')) — the S73 client."
    Write-Warning "  Phase 0's server instance uses a SEPARATE log ($srvLog) so logs won't clash."
    Write-Warning "  If the server refuses to start a 2nd instance, re-run with -KillClient."
  }
}

# ---- confirm nothing still holds $Port ----
$busy = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($busy) {
  Write-Warning "Port $Port still has a listener (PID $($busy.OwningProcess -join ',')). The server may fail to bind."
  Write-Warning "  (UDP-only listeners won't show here; UE game traffic is UDP, so this is just a heads-up.)"
}

# ---- build the server URL + args ----
$local = "http://localhost:8080"
$ab    = "/Script/AccelByteUe4Sdk.AccelByteSettings"
$loki  = "/Script/Loki.LokiGameProjectSettings"

if ($Mode -eq 'dedicated') {
  $url = "$mapUrl?game=$gmPath"
} else {
  $url = "$mapUrl?game=$gmPath?listen"
}

$args = @($url)
if ($Mode -eq 'dedicated') { $args += @("-server","-port=$Port") } else { $args += "-port=$Port" }
$args += @(
  "-abslog=$srvLog",
  "-log",
  "-newconsole",
  # AccelByte + Theorycraft PostAuth overrides -> local ags (so server-auth calls resolve, not NXDOMAIN)
  "-ini:Engine:[$ab]:BaseUrl=$local",
  "-ini:Engine:[$ab]:IamServerUrl=$local/iam",
  "-ini:Engine:[$ab]:PlatformServerUrl=$local/platform",
  "-ini:Engine:[$ab]:BasicServerUrl=$local/basic",
  "-ini:Engine:[$loki]:ProdPostAuthURL=$local",
  "-ini:Engine:[$loki]:ProdClientConfigURL=$local",
  "-ini:Game:[$loki]:ProdPostAuthURL=$local",
  "-ini:Game:[$loki]:ProdClientConfigURL=$local"
)
if ($NoSteam) { $args += "-nosteam" }
if ($NullRhi) { $args += @("-nullrhi","-nosplash","-unattended") }

# fresh log
if (Test-Path $srvLog) { Remove-Item $srvLog -Force -ErrorAction SilentlyContinue }

Write-Host ""
Write-Host "=== S74 B1 Phase-0: launching shipping exe as a $($Mode.ToUpper()) server on :$Port ===" -ForegroundColor Green
Write-Host "exe : $exe" -ForegroundColor DarkGray
Write-Host "url : $url" -ForegroundColor DarkGray
Write-Host "log : $srvLog" -ForegroundColor DarkGray
Write-Host "args: $($args -join ' ')" -ForegroundColor DarkGray
Write-Host ""

Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory (Split-Path $exe)
Write-Host "Launched. Tailing $srvLog for $WatchSeconds s (Ctrl+C to stop early)..." -ForegroundColor Cyan
Write-Host ""

# ---- classifier ----
$goPat = 'IpNetDriver|InitListen|listening on port|Created socket|NM_DedicatedServer|Dedicated server|LokiReplicationGraph|ServerPlatformInstance|AgonesManager|Agones|ServerAuthManager|ServerCoreGameManager|Bringing World .*up for play'
$noPat = 'LVL_Login|LVL_LobbyV2|BP_LoginHUD|Running as client|WITH_SERVER_CODE|server code|RequestExit|LogExit|appRequestExit'
$errPat = 'failed to get ULokiServerPlatformInstance|Agones.*(fail|error|refus)|AccelByte.*(fail|error)|LoginQueue|Fatal error|Assertion failed'

# wait for the log to appear (packed exe init can take 10-30s)
for ($i=0; $i -lt 60 -and -not (Test-Path $srvLog); $i++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Path $srvLog)) {
  Write-Warning "No $srvLog after 30s. Either -abslog was ignored (check the client Loki.log at"
  Write-Warning "  $env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log) or the process didn't start. NO-GO leaning."
  return
}

$deadline = (Get-Date).AddSeconds($WatchSeconds)
$sawGo = $false; $sawNo = $false
Get-Content $srvLog -Wait -Tail 0 | ForEach-Object {
  $line = $_
  if ($line -match $goPat)  { Write-Host "  [GO?]   $line" -ForegroundColor Green;  $sawGo = $true }
  elseif ($line -match $errPat) { Write-Host "  [boot]  $line" -ForegroundColor Yellow } # server-bootstrap error = ALSO a GO signal
  elseif ($line -match $noPat) { Write-Host "  [NO-GO?]$line" -ForegroundColor Red;   $sawNo = $true }
  if ((Get-Date) -gt $deadline) {
    Write-Host ""
    Write-Host "=== verdict (after $WatchSeconds s) ===" -ForegroundColor Green
    if ($sawGo) { Write-Host "GO signals seen: the exe entered a SERVER code path. -> proceed to Phase 1." -ForegroundColor Green }
    elseif ($sawNo) { Write-Host "NO-GO signals seen: the exe ran as a client / exited. B1 likely dead; fall back to B2 or bank." -ForegroundColor Red }
    else { Write-Host "Inconclusive — read $srvLog fully (grep for NetMode/IpNetDriver/ServerPlatformInstance)." -ForegroundColor Yellow }
    break
  }
}
