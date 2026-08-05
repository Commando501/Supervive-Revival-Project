<#
.SYNOPSIS
  Detached secondary-shim injector for the SUPERVIVE revival launch — the SINGLE injector for the full
  durable shim set (this superseded the old inject-missions.ps1, whose only extra was missions_fix).

  launch-redirect.ps1 injects the PRIMARY hook (catalog_store_fix.dll) at launch via inject watch-now —
  it must beat the grid Construct to open the IsCatalogDataReady gate. This helper injects ALL the
  SECONDARY shims AFTER the primary has finished and self-unhooked, so two thread-suspending hook
  installs never race:
    - mainmenu_refresh_pi8.dll  (pick mirror + main-menu/HUNTERS refresh;     hooks ProcessInternal)
    - catalog_pick_fix.dll      (IsPreviewable/IsUseable Script patches;       NO PI hook — independent)
    - loadout_fix.dll           (customization / skin persistence replay;      hooks ProcessInternal)
    - missions_fix.dll          (durable missions page, ags-fed progress bars; hooks ProcessInternal)

  COEXISTENCE: the three ProcessInternal-hooking shims (pi8, loadout_fix, missions_fix) share the named
  mutex "Local\SuperviveMissionsPIHook". Each captures the ORIGINAL 5-byte PI prologue and installs its
  jmp only TRANSIENTLY (install -> piggyback one game-thread call -> uninstall) under that lock, so only
  one has the hook installed at any instant — they never race on the thread-suspending SafeWrite.
  catalog_pick_fix does only Script (bytecode) patches, so it is independent. (Historically pi8 and
  missions were mutually-exclusive launch MODES because two PERMANENT PI hooks race; the shared mutex +
  transient-install design — S59 — retired that split, so this one script now injects the whole set.)

  -NoMissions / -NoLoadout drop those shims from the set (to isolate one surface while debugging).

  Spawned detached+hidden by launch-redirect.ps1 so it outlives that script (the game exe detaches and
  the launcher exits). Every shim self-defers its own work until its target objects exist, so exact
  timing is not critical — we only gate on the primary's hook being installed+removed.
#>
param(
  [string]$Repo = (Split-Path -Parent $PSScriptRoot),
  [switch]$NoMissions,
  [switch]$NoLoadout,
  [switch]$NoPasses,   # S83: skip battlepass_adopt_fix (PASSES / Hunter's Journey)
  [int]$GapSeconds = 3,# S109: seconds between successive manual-maps. See the note at the loop --
                       # the 3 s default packs all four secondaries into a ~13 s burst, and every
                       # death in the S109 series lands at or after that burst.
  [int]$MaxWaitProcSec = 150,
  [int]$MaxWaitUnhookSec = 120
)
$ErrorActionPreference = "SilentlyContinue"
$name    = "SUPERVIVE-Win64-Shipping.exe"
$inject  = Join-Path $Repo "tools\inject\inject.exe"
$primaryMarker = Join-Path $Repo "docs\catalog-store-fix-marker.txt"
$log     = Join-Path $Repo "docs\inject-secondaries.log"
# Order: pi8 first (installs its PI hook + captures the pristine prologue), then the Script-only tile
# patcher, then the other two PI-hookers. Capture is race-free regardless of order (each grabs the mutex
# and re-verifies the pristine 5-byte prologue before stealing it), but this preserves parity with the
# historically-validated pi8-first sequence.
#   loadout_fix: replays saved customization equips (skins/gliders/wisps/sprays/chromas) by calling the
#     game's native setters on the game thread. Reads GET /revival/loadout. (-NoLoadout to skip.)
#   missions_fix: fetches per-objective progress from ags and swaps the mission model on menu load + on
#     change. Reads GET /revival/missions/progress + POSTs /revival/missions/manifest. (-NoMissions to skip.)
$dlls = @("tools\sigbypass-mod\mainmenu_refresh_pi8.dll",
          "tools\sigbypass-mod\catalog_pick_fix.dll")
if (-not $NoLoadout)  { $dlls += "tools\sigbypass-mod\loadout_fix.dll" }
if (-not $NoMissions) { $dlls += "tools\sigbypass-mod\missions_fix.dll" }
# S83: PASSES / Hunter's Journey. Without this the PASSES section is empty and
# /storefront/battlepass/progressiontracks tight-loops at ~15/s. The shim force-calls the real
# adoption sink (OnSuccess 0x57C8130) with a track keyed 'ProgressionTrack:HuntersJourney' — that
# key is the keystone; the game then builds the account VM and populates the 85-tier ladder itself.
# Progress (tier/XP) comes from the backend (GET /progression/players/{id}), no shim needed.
# NB it does NOT hook ProcessInternal, so it does not join the PI-hook mutex dance.
# ★ Its aggregate Version must EXCEED the client's adopted value or OnSuccess skips the adopt. A
# fresh process starts at 0, so the built-in 104 is fine on a clean launch; only RE-injecting into
# an already-adopted process needs a bump (see the Version comment in battlepass_adopt_fix.cpp).
if (-not $NoPasses)   { $dlls += "tools\sigbypass-mod\battlepass_adopt_fix.dll" }

function Log($m){ "$([DateTime]::Now.ToString('HH:mm:ss'))  $m" | Out-File -FilePath $log -Append -Encoding ascii }
"" | Out-File -FilePath $log -Encoding ascii   # truncate for this launch
Log "secondary injector started (repo=$Repo) NoMissions=$NoMissions NoLoadout=$NoLoadout"
Log ("set: " + ($dlls -join ", "))

if (-not (Test-Path $inject)) { Log "inject.exe not found at $inject - aborting"; return }

# 1) wait for the game process
$deadline = (Get-Date).AddSeconds($MaxWaitProcSec); $up = $false
while ((Get-Date) -lt $deadline) { if (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue) { $up = $true; break }; Start-Sleep -Seconds 1 }
if (-not $up) { Log "game process never appeared within ${MaxWaitProcSec}s - aborting"; return }
Log "game process is up"

# 2) wait for the primary hook to install AND self-unhook (marker "[unhook]") so its thread-suspending
#    SafeWrite is finished before any PI-hooker installs its own hook. Fallback: proceed after timeout.
$deadline = (Get-Date).AddSeconds($MaxWaitUnhookSec); $ready = $false
while ((Get-Date) -lt $deadline) {
  if (Test-Path $primaryMarker) { $c = Get-Content $primaryMarker -Raw -ErrorAction SilentlyContinue; if ($c -and $c -match '\[unhook\]') { $ready = $true; break } }
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited while waiting for primary unhook - aborting"; return }
  Start-Sleep -Milliseconds 500
}
if ($ready) { Log "primary catalog_store_fix installed+unhooked - safe to inject secondaries" }
else { Log "WARNING: primary [unhook] not seen in ${MaxWaitUnhookSec}s - injecting secondaries anyway" }

# 3) inject each secondary sequentially.
#
# ★ THE GAP IS LOAD-BEARING (S109, 2026-08-04). It was 3 s to "avoid overlapping hook installs".
# MEASURED: with a 3 s gap the four secondaries are all mapped inside a ~13 s burst starting at
# T+20 s, and EVERY death recorded in the S109 series (20, 23, 25, 30, 35, 41, 51, 55, 65 s) falls
# at or after that burst -- while every configuration that skips this sequence entirely (clean,
# a single inert canary, catalog_store_fix alone, pi8 alone) survived 4.44 h with ZERO deaths.
# See docs/s109-dump-forensics.md section 18.
#
# -GapSeconds spreads the burst. Default stays 3 so behaviour is unchanged unless asked for.
foreach ($d in $dlls) {
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited - stopping"; return }
  $path = Join-Path $Repo $d
  if (-not (Test-Path $path)) { Log "MISSING: $path - skipping"; continue }
  Log "injecting $d ..."
  $out = & $inject mmap $name $path 2>&1
  Log ($out -join " | ")
  Log ("gap ${GapSeconds}s before next secondary")
  Start-Sleep -Seconds $GapSeconds
}
Log "secondary injection complete"
