<#
.SYNOPSIS
  Redirect the SUPERVIVE client's dead backends to our local community server and
  launch the game.

.DESCRIPTION
  After the official servers were retired the client cannot log in. Recon of the
  client (Loki.log) shows three backends:

    1. AccelByte (IAM/platform/basic) - redirected via UE -ini: overrides to
       http://localhost:8080. (This already works.)
    2. accounts.projectloki.theorycraftgames.com - Theorycraft's own auth host
       that the Steam login actually calls. Host record is gone (NXDOMAIN), so
       login hangs ("Auth Failure 14005"). Redirected here via the hosts file.
    3. client-config-jx-prod...theorycraftgames.com - feature-flag config (non
       fatal). Also redirected via the hosts file.

  Hosts #2/#3 use HTTPS with libcurl bVerifyPeer=true, so we append our server's
  self-signed cert to the game's libcurl CA bundle
  (Loki/Content/Certificates/cacert.pem) and serve HTTPS on :443.

  Requires admin (hosts file + :443 + killing the prior elevated server).
  Re-run with -Revert to undo the hosts and cacert changes.

.PARAMETER GameRoot   SUPERVIVE install (folder containing Loki\Binaries).
.PARAMETER Revert     Undo hosts + cacert.pem changes and exit.
.PARAMETER NoLaunch   Set up redirect + start server, but don't launch the game.
.PARAMETER Open       Dedicated-server-stub probe #6 (UE console): append
                      -ExecCmds="open <Open>" to the game's launch args so the
                      UE engine fires its built-in NetConnection travel command
                      after init. Use to bypass the matchmaking state machine
                      (which probes #1-5 proved is ticket-id-gated and can't
                      be spoofed from a fresh menu). Format "ip:port", e.g.
                      "127.0.0.1:7777". The Loki.log LogNet* / LogPlatformFile
                      / Failed-to-connect activity that follows is the
                      protocol-shape signal — even with nothing listening on
                      the port, the client-side handshake attempt names the
                      driver, the StatelessConnect handler, and the first
                      control-channel message it tries to send.

.EXAMPLE  .\launch-redirect.ps1
.EXAMPLE  .\launch-redirect.ps1 -Revert
.EXAMPLE  .\launch-redirect.ps1 -Open "127.0.0.1:7777"
#>
param(
  [string]$GameRoot = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE",
  [switch]$Revert,
  [switch]$NoLaunch,
  [string]$Open = "",
  [string]$Hook = ""    # path to a manual-map shim DLL (browse_hook.dll, etc.)
                         # Uses inject.exe launch (CREATE_SUSPENDED+mmap+Resume)
                         # so the DLL is loaded BEFORE the game's first
                         # UEngine::Browse call at startup. Required to catch
                         # the natural LVL_Login + LVL_LobbyV2 startup
                         # browses for testing the hook end-to-end.
)

$ErrorActionPreference = "Stop"
$repoRoot  = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $repoRoot "server"
$certPath  = Join-Path $repoRoot "certs\root.crt"   # CA to append to game bundle
$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$caBundle  = Join-Path $GameRoot "Loki\Content\Certificates\cacert.pem"
$go        = "$env:ProgramFiles\Go\bin\go.exe"

$HostsToRedirect = @(
  "accounts.projectloki.theorycraftgames.com",
  "client-config-jx-prod.prodcluster.awsinfra.theorycraftgames.com"
)
$Marker = "# SUPERVIVE-REVIVAL"

# ---- require admin ----
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
  Write-Host "Elevation required (hosts file + port 443). Relaunching as admin..." -ForegroundColor Yellow
  $argList = @("-NoExit","-ExecutionPolicy","Bypass","-File",$PSCommandPath,"-GameRoot",$GameRoot)
  if ($Revert)   { $argList += "-Revert" }
  if ($NoLaunch) { $argList += "-NoLaunch" }
  if ($Open)     { $argList += @("-Open",$Open) }
  if ($Hook)     { $argList += @("-Hook",$Hook) }
  Start-Process powershell -Verb RunAs -ArgumentList $argList
  return
}

function Remove-HostsEntries {
  $lines = Get-Content $hostsFile | Where-Object { $_ -notmatch [regex]::Escape($Marker) }
  Set-Content -Path $hostsFile -Value $lines -Encoding ascii
}

# ---- revert mode ----
if ($Revert) {
  Write-Host "Reverting hosts entries..." -ForegroundColor Cyan
  Remove-HostsEntries
  if (Test-Path "$caBundle.supervive-bak") {
    Write-Host "Restoring original cacert.pem..." -ForegroundColor Cyan
    Copy-Item "$caBundle.supervive-bak" $caBundle -Force
  }
  $userEngineIni = Join-Path $env:LOCALAPPDATA "SUPERVIVE\Saved\Config\WindowsClient\Engine.ini"
  if (Test-Path $userEngineIni) {
    Write-Host "Removing bVerifyPeer override from user Engine.ini..." -ForegroundColor Cyan
    try { (Get-Item $userEngineIni).IsReadOnly = $false } catch {}
    $txt = Get-Content $userEngineIni -Raw
    $txt = $txt -replace "(?ms)\r?\n\[HTTP\.Curl\]\r?\nbVerifyPeer=false\r?\n\r?\n\[SSL\]\r?\nbValidateRootCertificates=false\r?\n?", ""
    Set-Content -Path $userEngineIni -Value $txt -Encoding ascii -NoNewline
  }
  Write-Host "Done. Redirects removed." -ForegroundColor Green
  return
}

# ---- kill any prior server holding our ports ----
Get-Process ags,go -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process $_ -Force } catch {} }
Start-Sleep -Seconds 2

# regenerate the cert chain fresh (structure changed: root + leaf)
$certsDir = Join-Path $repoRoot "certs"
if (Test-Path $certsDir) { Get-ChildItem $certsDir | Remove-Item -Force -ErrorAction SilentlyContinue }

# ---- build the server first (so startup is instant, not a cold compile) ----
if (-not (Test-Path $go)) { throw "Go not found at $go" }
$agsExe = Join-Path $serverDir "ags.exe"
Write-Host "Building community backend..." -ForegroundColor Cyan
& $go build -C $serverDir -o $agsExe ./cmd/ags
if ($LASTEXITCODE -ne 0) { throw "go build failed (exit $LASTEXITCODE)" }

# ---- start it (:8080 HTTP + :443 HTTPS) ----
Write-Host "Starting community backend (:8080 HTTP + :443 HTTPS)..." -ForegroundColor Cyan
$logArg = Join-Path $repoRoot "docs\capture.log"
$srvOut = Join-Path $repoRoot "docs\server.out.log"
# NOTE: paths contain spaces ("Supervive Revival Project"). Start-Process does
# NOT quote array elements, and Go's flag parser stops at the first non-flag
# token, so unquoted space paths silently drop later flags. Pass ONE quoted
# argument string instead.
$argString = "-http :8080 -https :443 -log `"$logArg`" -certs `"$certsDir`""
Start-Process -FilePath $agsExe -ArgumentList $argString `
  -WorkingDirectory $serverDir -RedirectStandardError $srvOut
# wait up to 30s for the cert chain
for ($i=0; $i -lt 60 -and -not (Test-Path $certPath); $i++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Path $certPath)) {
  if (Test-Path $srvOut) { Write-Host "--- server output ---" -ForegroundColor Red; Get-Content $srvOut | Write-Host }
  throw "Server did not produce $certPath (see $srvOut)"
}
Write-Host "Server up; cert chain generated." -ForegroundColor Green
Start-Sleep -Seconds 2

# ---- append our ROOT CA to the game's libcurl CA bundle (from clean backup) ----
if (-not (Test-Path $caBundle)) { throw "CA bundle not found: $caBundle" }
if (-not (Test-Path "$caBundle.supervive-bak")) { Copy-Item $caBundle "$caBundle.supervive-bak" }
# Always start from the pristine bundle, then append our current root.
Copy-Item "$caBundle.supervive-bak" $caBundle -Force
Write-Host "Appending Root CA to game cacert.pem..." -ForegroundColor Cyan
Add-Content -Path $caBundle -Value "`n# SUPERVIVE Revival Root CA" -Encoding ascii
Add-Content -Path $caBundle -Value (Get-Content $certPath -Raw) -Encoding ascii

# ---- hosts file redirect (idempotent, marked) ----
Remove-HostsEntries
$add = $HostsToRedirect | ForEach-Object { "127.0.0.1`t$_`t$Marker" }
Add-Content -Path $hostsFile -Value $add -Encoding ascii
Write-Host "Hosts entries added:" -ForegroundColor Cyan
$HostsToRedirect | ForEach-Object { Write-Host "  127.0.0.1  $_" }
ipconfig /flushdns | Out-Null

# ---- disable libcurl peer verification via USER Engine.ini ----
# The -ini: command line is applied too late for FCurlHttpManager::InitCurl (it
# reads bVerifyPeer during very early engine init). The user/Saved Engine.ini is
# merged before that, so we set it there instead.
$userEngineIni = Join-Path $env:LOCALAPPDATA "SUPERVIVE\Saved\Config\WindowsClient\Engine.ini"
if (Test-Path $userEngineIni) {
  # Clear any read-only flag from a previous run so we can rewrite it.
  try { (Get-Item $userEngineIni).IsReadOnly = $false } catch {}
  $ini = Get-Content $userEngineIni -Raw
  if ($ini -notmatch "(?m)^\s*bVerifyPeer\s*=") {
    Write-Host "Disabling libcurl peer verification in user Engine.ini..." -ForegroundColor Cyan
    $block = @("", "[HTTP.Curl]", "bVerifyPeer=false", "", "[SSL]", "bValidateRootCertificates=false")
    Add-Content -Path $userEngineIni -Value $block -Encoding ascii
  } else { Write-Host "bVerifyPeer override already present." -ForegroundColor DarkGray }
  # Make read-only so the game can't strip our section before curl init reads it.
  try { (Get-Item $userEngineIni).IsReadOnly = $true; Write-Host "  (Engine.ini set read-only)" -ForegroundColor DarkGray } catch {}
} else {
  Write-Warning "User Engine.ini not found at $userEngineIni - run the game once first."
}

if ($NoLaunch) { Write-Host "Server + redirect ready. Skipping game launch (-NoLaunch)." -ForegroundColor Green; return }

# ---- AccelByte -ini overrides + launch ----
$exe = Join-Path $GameRoot "Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
if (-not (Test-Path $exe)) { throw "Shipping exe not found: $exe" }
$ab   = "/Script/AccelByteUe4Sdk.AccelByteSettings"
$loki = "/Script/Loki.LokiGameProjectSettings"
$local = "http://localhost:8080"
$iniArgs = @(
  # AccelByte SDK backend -> local server
  "-ini:Engine:[$ab]:BaseUrl=$local",
  "-ini:Engine:[$ab]:IamServerUrl=$local/iam",
  "-ini:Engine:[$ab]:PlatformServerUrl=$local/platform",
  "-ini:Engine:[$ab]:BasicServerUrl=$local/basic",
  "-ini:Engine:[$ab]:LobbyServerUrl=ws://localhost:8080/lobby/",
  # Theorycraft PostAuth (Steam login) + client-config -> local server (HTTP, no TLS).
  # Read at login time, so the -ini override applies (unlike early curl init).
  # Hedge the config file: try both Engine and Game.
  "-ini:Engine:[$loki]:ProdPostAuthURL=$local",
  "-ini:Engine:[$loki]:ProdClientConfigURL=$local",
  "-ini:Game:[$loki]:ProdPostAuthURL=$local",
  "-ini:Game:[$loki]:ProdClientConfigURL=$local",
  "-log"
)
# Probe #6: append UE's built-in `open <addr>:<port>` console command via
# -ExecCmds. Fires after engine init, so it'll race the login flow - if it
# triggers a NetConnection attempt before login completes, we still get the
# Loki.log signal we want (driver name, control-channel first message,
# failure mode). Nothing needs to be listening on the port for the probe
# to be diagnostic.
if ($Open) {
  # Probe #6 result (2026-06-29): -ExecCmds="open $Open" reached the engine's
  # CommandLine (logged at engine init) but never produced a Browse to the
  # target - the DefaultMap browse to LVL_Login fired in the same frame and
  # clobbered the open command. Shipping build also stripped the dev console
  # (ConsoleKeys/EnableCheats/ConsoleClass strings ALL absent from the exe),
  # so manual console entry post-menu isn't an option either.
  #
  # Probe #7: positional URL form. UE's startup parser treats the first
  # non-switch arg as the initial URL - it REPLACES DefaultMap entirely, so
  # there's no race with LVL_Login. The game won't reach the menu (we go
  # straight to a NetConnection attempt), but Loki.log will name the
  # NetDriver, the StatelessConnect handler, and the first control-channel
  # message - exactly the protocol surface we need to size the UE5.4 stub
  # server build.
  Write-Host "Probe #7 active: positional URL $Open (replaces DefaultMap browse)" -ForegroundColor Yellow
  $iniArgs += $Open
}
if ($Hook) {
  if (-not (Test-Path $Hook)) {
    throw "Hook DLL not found: $Hook"
  }
  $injectExe = Join-Path $repoRoot "tools\inject\inject.exe"
  if (-not (Test-Path $injectExe)) {
    throw "inject.exe not found at $injectExe (build it with 'go build -C tools/inject -o inject.exe .')"
  }
  # watch-now (not launch): polls every 1ms for the SUPERVIVE process to
  # appear, then immediately manual-maps the DLL. We launch the game via
  # the normal `& $exe @iniArgs` path so Steam's DRM init runs as expected
  # (CREATE_SUSPENDED + Resume bypasses Steam handshake and the game won't
  # show a window). The race window for "engine init finishes before our
  # mmap completes" is on the order of 1-2 seconds; the polling loop wins.
  Write-Host "Spawning inject watch-now to catch the game on launch..." -ForegroundColor Cyan
  Write-Host "  DLL: $Hook" -ForegroundColor DarkGray
  $watchProc = Start-Process -FilePath $injectExe `
      -ArgumentList @("watch-now", "SUPERVIVE-Win64-Shipping.exe", $Hook) `
      -WindowStyle Minimized -PassThru
  Start-Sleep -Milliseconds 200   # let watch-now's poll loop spin up
  Write-Host "Launching SUPERVIVE (PostAuth -> $local)..." -ForegroundColor Cyan
  & $exe @iniArgs
  # When the game exits, the watch-now process is harmless (loop ends when
  # it finds the process). It exits on its own after a successful mmap.
} else {
  Write-Host "Launching SUPERVIVE (PostAuth -> $local)..." -ForegroundColor Cyan
  & $exe @iniArgs
}
