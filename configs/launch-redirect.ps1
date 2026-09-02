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
                      protocol-shape signal � even with nothing listening on
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
  # Extra raw switches appended to the game's command line, e.g.
  #   -ExtraArgs '-ini:Engine:[Core.Log]:LogOnline=Verbose','-LogCmds="LogFoo Verbose"'
  # Added S113 for FK-11 (log-verbosity control plane). The engine echoes the whole
  # command line as `LogInit: Command Line:`, so anything passed here is verifiable
  # as DELIVERED independently of whether it took effect.
  [string[]]$ExtraArgs = @(),
  [string]$Open = "",
  [string]$Hook = "",   # path to a shim DLL to inject on launch (manual-map via inject.exe).
                         # For a working STORE + HUNTERS roster, use:
                         #   tools\sigbypass-mod\catalog_store_fix.dll
                         # (AssetManager scan + self-restoring IsCatalogDataReady jz-NOP that
                         #  dodges the 3-5min code-integrity check + CatalogEntry purchasable
                         #  poke). This is the single combined store/roster hook.
                         # Uses inject.exe launch (CREATE_SUSPENDED+mmap+Resume)
                         # so the DLL is loaded BEFORE the game's first
                         # UEngine::Browse call at startup. Required to catch
                         # the natural LVL_Login + LVL_LobbyV2 startup
                         # browses for testing the hook end-to-end.
  [switch]$NoHook,       # skip ALL shim auto-injection (clean RE run)
  [switch]$Missions,     # DEPRECATED no-op alias: missions are now in the DEFAULT set. Kept so old
                         # invocations / docs still work. (Was: "durable Missions mode".)
  [switch]$NoMissions,   # DEPRECATED no-op: missions_fix left the default set 2026-08-14 (the missions
                         # page is served natively by the backend now). Kept so old invocations work.
  [switch]$WithMissionsShim, # opt BACK IN to the retired missions_fix.dll (one-flag rollback)
  [switch]$NoLoadout,   # drop loadout_fix.dll from the default set (isolate non-customization surfaces)
  [switch]$NoPasses,    # drop battlepass_adopt_fix.dll (PASSES / Hunter's Journey) from the default set
  [switch]$NoCrashWatch, # do NOT arm usmapdump crashwatch. Armed by default: it is pure RPM and
                         # idle until the game CRASHES, at which point it suspends the dying
                         # process and dumps a full image before it exits. A crash-era image is
                         # worth ~2,334 .text pages that no healthy dump has bytes for -- 25x a
                         # tutorial sitting -- and costs zero extra launches because runs die on
                         # their own anyway. See docs/fk18-fk19-multistate-merge-settled.md 12.2.
                         # Trade-off, stated: on a real crash it FREEZES the process for the
                         # duration of the dump. That is free (it is dying), but if a marker ever
                         # fires spuriously a healthy game would freeze once, then resume.
  [int]$InjectGapSeconds, # S109: seconds between successive secondary manual-maps. Injector default is
                         # now 20 (raised from 3 on 2026-08-05). At 3 s the four secondaries were
                         # mapped in a ~13 s burst and EVERY death in the S109 series landed at or
                         # after it; >=10 s gaps cut the hazard ~71x. Pass 3 to restore the old burst.
                         # See docs/s109-dump-forensics.md sections 18-20.
  [switch]$ResetCapture  # S149 capture-gen fix: before starting ags, archive any existing docs\capture.log
                         # under a stamped name and CreateNew a fresh entry with CreationTimeUtc == UtcNow.
                         # Off by default -- byte-identical to today's primary launch when unset. Unblocks
                         # S149's bind-only flight and any successor gate that admits on capture generation
                         # (measured -10849 s stale in flight 1). See configs/capture-gate.ps1.
)
# DEFAULT (no flags): primary catalog_store_fix.dll (store + HUNTERS roster) is injected at launch, then
# configs/inject-secondaries.ps1 injects the full secondary set once it settles � pick/refresh (pi8),
# pick-commit (catalog_pick_fix), customization (loadout_fix), and missions (missions_fix). The three
# ProcessInternal-hooking shims (pi8, loadout_fix, missions_fix) coexist via the shared
# Local\SuperviveMissionsPIHook mutex (each installs its PI jmp only transiently). This one launch now
# gives EVERY durable fix at once. -NoMissions / -NoLoadout trim the set; -NoHook skips all shims;
# -Hook <path> injects exactly one DLL and no secondaries. Requires ags built with /revival/missions/*
# and /revival/loadout (server/internal/interactive/{missions,loadout}.go).

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
  if ($Revert)     { $argList += "-Revert" }
  if ($NoLaunch)   { $argList += "-NoLaunch" }
  if ($Open)       { $argList += @("-Open",$Open) }
  if ($Hook)       { $argList += @("-Hook",$Hook) }
  if ($NoHook)     { $argList += "-NoHook" }
  if ($Missions)   { $argList += "-Missions" }    # accepted (no-op alias) � forwarded so it isn't silently dropped
  if ($NoMissions) { $argList += "-NoMissions" }
  if ($NoLoadout)  { $argList += "-NoLoadout" }
  # S113: forward -ExtraArgs too. CLAUDE.md records that -NoPasses was silently
  # DROPPED across elevation, which invalidated a whole bisection - do not repeat it.
  if ($ExtraArgs -and $ExtraArgs.Count) { $argList += @("-ExtraArgs", ($ExtraArgs -join ',')) }
  # S149 capture-gen fix: same forwarding rule -- silently dropping this across
  # elevation would leave the capture stale under a fresh backend.
  if ($ResetCapture) { $argList += "-ResetCapture" }
  Start-Process powershell -Verb RunAs -ArgumentList $argList
  return
}

# ---- default store/roster hook: auto-inject catalog_store_fix.dll unless -NoHook ----
# The native IsCatalogDataReady gate (CatMgr+0x354) is client state the dead backend
# can't set, so the STORE tabs + HUNTERS roster stay empty without a per-launch shim.
# catalog_store_fix.dll opens that gate (self-restoring jz-NOP that dodges the ~3-5min
# code-integrity check) and pokes CatalogEntry purchasable flags. Defaulting it here
# removes the manual -Hook step; pass -NoHook for a clean RE run, or -Hook <path> for a
# different shim. Only the elevated launch path reaches this (non-admin returned above;
# Revert/NoLaunch don't inject).
if (-not $NoHook -and -not $Revert -and -not $NoLaunch -and -not $Hook) {
  $defaultHook = Join-Path $repoRoot "tools\sigbypass-mod\catalog_store_fix.dll"
  if (Test-Path $defaultHook) {
    $Hook = $defaultHook
    # After the primary catalog_store_fix settles, inject-secondaries.ps1 injects the FULL secondary set:
    # pick/refresh (pi8) + pick-commit (catalog_pick_fix) + customization (loadout_fix) + missions
    # (missions_fix). The three PI-hookers coexist via the shared Local\SuperviveMissionsPIHook mutex.
    $InjectSecondaries = $true
    $secExtra = @()
    if ($WithMissionsShim) { $secExtra += "-WithMissionsShim" }
    if ($NoLoadout)  { $secExtra += "-NoLoadout" }
    if ($NoPasses)   { $secExtra += "-NoPasses" }
    # S109: spread the secondary manual-maps. Default 3 s packs all four into a ~13 s burst,
    # and every death in the S109 series lands at or after that burst (docs/s109-dump-forensics.md
    # section 18). Pass -InjectGapSeconds 60 to spread it.
    if ($PSBoundParameters.ContainsKey('InjectGapSeconds')) { $secExtra += "-GapSeconds $InjectGapSeconds" }
    $parts = @("pick/refresh","pick-commit")
    if (-not $NoLoadout)  { $parts += "customization" }
    if ($WithMissionsShim) { $parts += "missions(shim,retired)" }
    Write-Host "Auto-hook: store/roster (catalog_store_fix) + $($parts -join ' + '). Missions render natively (no shim). Use -NoHook (clean RE), -NoLoadout to trim, -WithMissionsShim to restore the retired missions_fix." -ForegroundColor Cyan
  } else {
    Write-Host "Auto-hook: catalog_store_fix.dll not found at $defaultHook" -ForegroundColor Yellow
    Write-Host "  -> launching WITHOUT the store/roster hook (STORE + HUNTERS will be empty)." -ForegroundColor Yellow
  }
}

function Remove-HostsEntries {
  # Read + write via .NET File APIs (deterministic handle close). A
  # `Get-Content $hostsFile | Set-Content $hostsFile` pipeline left the read
  # handle open long enough to collide with the write ("Stream was not
  # readable", an ArgumentException the old IOException-only catch let escape).
  # Defender / SmartScreen also occasionally hold a scan handle on hosts for
  # ~100-500ms, so retry on ANY transient failure.
  $maxTries = 20
  for ($i=0; $i -lt $maxTries; $i++) {
    try {
      $kept = [System.IO.File]::ReadAllLines($hostsFile) |
        Where-Object { $_ -notmatch [regex]::Escape($Marker) }
      [System.IO.File]::WriteAllLines($hostsFile, [string[]]$kept, [System.Text.Encoding]::ASCII)
      return
    } catch {
      if ($i -eq $maxTries - 1) { throw }
      Start-Sleep -Milliseconds 250
    }
  }
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

# ---- S149 capture-gen fix (opt-in): archive stale docs\capture.log + stamp a
#      fresh one under UtcNow BEFORE ags opens it. Off by default -- primary
#      launch flow is byte-identical when -ResetCapture is not passed. See
#      configs/capture-gate.ps1's block-comment for the S149-flight-1 refusal
#      this closes (measured CreationTimeUtc delta -10849.3 s, gate 60s window).
if ($ResetCapture) {
  # Label the archive with either the caller's tag or a wall-clock stamp so
  # runs don't collide. AGS_CAPTURE_LABEL is a plain env var so any flight
  # helper (fk24-stage.ps1, an S149 wrapper, etc.) can name its capture
  # without adding another cross-elevation switch.
  $labelForGate = if ($env:AGS_CAPTURE_LABEL) { $env:AGS_CAPTURE_LABEL }
                  else { Get-Date -Format 'yyyyMMdd-HHmmss' }
  & (Join-Path $PSScriptRoot 'capture-gate.ps1') `
      -CapturePath (Join-Path $repoRoot 'docs\capture.log') `
      -Label       $labelForGate
}

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

# ---- verify the HTTP mux is actually SERVING (not just that TLS certs were written) ----
# The cert-chain wait proves ags started + cleared TLS init, but not that the request mux answers. A
# quick GET of a lightweight, side-effect-free revival endpoint confirms the backend will actually
# respond to the game's login/menu calls � catching a half-up server (panicked handler, port bind race)
# BEFORE we launch the game and stare at a mystery hang. Best-effort: retry ~5s, WARN (don't abort) on
# failure, since a probe false-negative shouldn't block a launch when ags is otherwise up.
# -UseBasicParsing avoids the IE engine; 127.0.0.1 bypasses the proxy.
$healthUrl = "http://127.0.0.1:8080/revival/missions/progress"
$served = $false
for ($i=0; $i -lt 10 -and -not $served; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $served = $true }
  } catch { Start-Sleep -Milliseconds 500 }
}
if ($served) {
  Write-Host "Backend serving HTTP (probe $healthUrl -> 200)." -ForegroundColor Green
} else {
  Write-Warning "Backend cert chain is up but $healthUrl did not answer in ~5s."
  Write-Warning "  The game may still work, but if login/menu hangs, check $srvOut for a handler panic or bind error."
}

# ---- append our ROOT CA to the game's libcurl CA bundle (from clean backup) ----
if (-not (Test-Path $caBundle)) { throw "CA bundle not found: $caBundle" }
if (-not (Test-Path "$caBundle.supervive-bak")) { Copy-Item $caBundle "$caBundle.supervive-bak" }
# Always start from the pristine bundle, then append our current root.
Copy-Item "$caBundle.supervive-bak" $caBundle -Force
Write-Host "Appending Root CA to game cacert.pem..." -ForegroundColor Cyan
Add-Content -Path $caBundle -Value "`n# SUPERVIVE Revival Root CA" -Encoding ascii
Add-Content -Path $caBundle -Value (Get-Content $certPath -Raw) -Encoding ascii

# ---- hosts file redirect (idempotent, marked) � SINGLE atomic write ----
# Remove any stale marker lines AND append the fresh redirect in ONE write, with
# retry. A separate Remove-HostsEntries + Add-Content raced Defender's scan-lock on
# the file we'd just written ("hosts is being used by another process"): the remove
# write triggers a real-time scan that briefly holds hosts, then the immediate
# append fails. One read-filter-append-write with retry avoids the intermediate
# state and rides out the transient lock.
$add = $HostsToRedirect | ForEach-Object { "127.0.0.1`t$_`t$Marker" }
$maxTries = 30
for ($i=0; $i -lt $maxTries; $i++) {
  try {
    $kept = [System.IO.File]::ReadAllLines($hostsFile) |
      Where-Object { $_ -notmatch [regex]::Escape($Marker) }
    [System.IO.File]::WriteAllLines($hostsFile, [string[]]($kept + $add), [System.Text.Encoding]::ASCII)
    break
  } catch {
    if ($i -eq $maxTries - 1) { throw }
    Start-Sleep -Milliseconds 250
  }
}
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

# ---- preserve any pending crashpad report BEFORE we launch (FK-9, S109) ----
# When the game dies, Sentry's crashpad handler -- not UE's -- writes the minidump,
# into <GameRoot>\Loki\.sentry-native\ with NO `UECC-*` directory. MEASURED S109:
# crashpad flushes pending reports at the NEXT PROCESS START, not on a timer, so the
# launch we are about to perform is exactly what destroys the previous run's dump.
# Archiving here is therefore deterministic and cannot lose one -- no watcher needed.
# See configs/archive-crashdumps.ps1 for the evidence.
& (Join-Path $PSScriptRoot "archive-crashdumps.ps1") -GameRoot $GameRoot

# ---- arm the crash-capture harness ------------------------------------------------------------
# A crashing process is the highest-.text-coverage state this project has ever observed (best
# crash-era process 62.68% vs merged2's 54.95%), and nobody has ever captured one, because the
# window from the first crash log line to crashpad handoff is ~34 ms -- far shorter than a dump.
# crashwatch closes that by SUSPENDING the dying process on trigger, which turns an unknown
# sub-second window into unlimited time; it then dumps and RESUMES so crashpad still writes its
# own minidump. Pure RPM, no injection, no module-image write. Idle until a crash marker appears.
if (-not $NoCrashWatch) {
  $usmapExe = Join-Path $repoRoot "tools\usmapdump\usmapdump.exe"
  if (Test-Path $usmapExe) {
    $cwStamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $cwOut   = Join-Path $repoRoot "dumps\crash-$cwStamp"
    $cwLog   = Join-Path $repoRoot "docs\crashwatch.out.log"
    $cwArgs  = "crashwatch SUPERVIVE-Win64-Shipping.exe `"$cwOut`" -poll 50"
    Start-Process -FilePath $usmapExe -ArgumentList $cwArgs `
        -WindowStyle Minimized `
        -RedirectStandardOutput $cwLog -RedirectStandardError "$cwLog.err" | Out-Null
    Write-Host "Crash-capture armed: dumps/crash-$cwStamp (log: docs/crashwatch.out.log)" -ForegroundColor Cyan
    Write-Host "  idle until the game crashes; then suspends it and dumps before it exits." -ForegroundColor DarkGray
  } else {
    Write-Host "  (usmapdump.exe not found - crash capture NOT armed)" -ForegroundColor Yellow
  }
}

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
# Raw extra switches (S113, FK-11). Appended verbatim; verify delivery by reading
# the `LogInit: Command Line:` echo at the top of Loki.log.
if ($ExtraArgs -and $ExtraArgs.Count) {
  Write-Host "Extra command-line args ($($ExtraArgs.Count)):" -ForegroundColor Cyan
  foreach ($a in $ExtraArgs) { Write-Host "  $a" -ForegroundColor DarkGray; $iniArgs += $a }
}
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
  # NOTE: $Hook contains spaces (the repo path). Start-Process does NOT quote
  # individual -ArgumentList ARRAY elements, so the array form splits the DLL path
  # at the spaces and inject silently fails (no marker). Pass ONE quoted argument
  # STRING instead � the same fix the ags Start-Process above uses. Capture inject's
  # stdout/stderr so a failed mmap is visible in docs/inject-watch.out.log.
  $watchOut = Join-Path $repoRoot "docs\inject-watch.out.log"
  $injArgs  = "watch-now SUPERVIVE-Win64-Shipping.exe `"$Hook`""
  $watchProc = Start-Process -FilePath $injectExe -ArgumentList $injArgs `
      -WindowStyle Minimized -PassThru `
      -RedirectStandardOutput $watchOut -RedirectStandardError "$watchOut.err"
  Start-Sleep -Milliseconds 200   # let watch-now's poll loop spin up
  # Secondary shims (pick + refresh) � injected by a DETACHED helper that waits for the
  # primary catalog_store_fix to install + self-unhook first (so two thread-suspending hook
  # installs never race). Detached so it outlives this launcher (the game exe detaches and
  # this script exits). Only on the auto-hook path; an explicit -Hook injects just that DLL.
  if ($InjectSecondaries) {
    $secInj = Join-Path $repoRoot "configs\inject-secondaries.ps1"
    if (Test-Path $secInj) {
      $setDesc = @("pi8","catalog_pick_fix")
      if (-not $NoLoadout)  { $setDesc += "loadout_fix" }
      if ($WithMissionsShim) { $setDesc += "missions_fix(retired)" }
      Write-Host "  Secondary shims ($($setDesc -join ' + ')) will inject once the store/roster hook settles." -ForegroundColor DarkGray
      # Quote the spaced paths in ONE argument string (Start-Process does not quote -ArgumentList array
      # elements, so the repo path would split and powershell couldn't find the script). Append the
      # -WithMissionsShim / -NoLoadout toggles the injector honours.
      $secArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$secInj`" -Repo `"$repoRoot`""
      foreach ($e in $secExtra) { $secArgs += " $e" }
      Start-Process powershell -WindowStyle Hidden -ArgumentList $secArgs | Out-Null
    } else {
      Write-Host "  (inject-secondaries.ps1 not found � secondary shims will NOT auto-inject)" -ForegroundColor Yellow
    }
  }
  Write-Host "Launching SUPERVIVE (PostAuth -> $local)..." -ForegroundColor Cyan
  & $exe @iniArgs
  # When the game exits, the watch-now process is harmless (loop ends when
  # it finds the process). It exits on its own after a successful mmap.
} else {
  Write-Host "Launching SUPERVIVE (PostAuth -> $local)..." -ForegroundColor Cyan
  & $exe @iniArgs
}

# ---- NO post-exit sweep here, deliberately (FK-9, S109) ----
# I first added a second archive call at this point, assuming `& $exe` blocks until the
# game exits. IT DOES NOT: the shipping exe detaches, so `& $exe` returns in ~1 s and
# this line ran BEFORE the game had even mounted its paks. MEASURED 2026-08-04 16:38 --
# the "postexit" archive was written one second after the "before launch" one, of the
# same report. It was pure duplication under a misleading name.
#
# The pre-launch sweep is sufficient, and provably so:
#   * a pending report is only ever destroyed by a launch (MEASURED 16:38:51 -- metadata
#     went 150 B/num_records=1 -> 16 B/num_records=0 in the same second crashpad_handler
#     started), and we archive immediately before that;
#   * at pre-launch time Saved\Logs\Loki.log is STILL the dead session's log, because UE
#     rotates it at game startup -- so the sweep captures the correct, untruncated log
#     for the death it is archiving, not the new run's.
#
# Blocking here to wait for the game to exit is NOT an option: CLAUDE.md's hands-free
# tutorial recipe requires this script to return promptly so fk24-stage.ps1 can run.
# If you want a dump in dumps\ without waiting for the next launch, run
# `configs\archive-crashdumps.ps1 -Label <tag>` by hand after the death.

