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

  -NoLoadout drops loadout_fix (to isolate one surface while debugging). -WithMissionsShim restores
  missions_fix, which left the default set on 2026-08-14 because the missions page is now native.

  Spawned detached+hidden by launch-redirect.ps1 so it outlives that script (the game exe detaches and
  the launcher exits). Every shim self-defers its own work until its target objects exist, so exact
  timing is not critical — we only gate on the primary's hook being installed+removed.
#>
param(
  [string]$Repo = (Split-Path -Parent $PSScriptRoot),
  [switch]$NoMissions,        # DEPRECATED no-op: missions_fix left the default set 2026-08-14 (the
                              # missions page is served natively now). Kept so old invocations work.
  [switch]$WithMissionsShim,  # opt BACK IN to the retired missions_fix.dll (rollback switch)
  [switch]$NoLoadout,
  [switch]$NoPasses,   # S83: skip battlepass_adopt_fix (PASSES / Hunter's Journey)
  [int]$GapSeconds = 20,# S109: seconds between successive manual-maps. DEFAULT RAISED 3 -> 20 on
                        # 2026-08-05 after a 5-point gap sweep; see the note at the loop. Costs ~80 s
                        # before the full menu set is live (was ~35 s) and cuts the protector-kill
                        # hazard ~71x. Pass -GapSeconds 3 to restore the old burst behaviour.
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
#     change. Reads GET /revival/missions/progress + POSTs /revival/missions/manifest. RETIRED from the
#     default set 2026-08-14 (served natively now); -WithMissionsShim restores it.
$dlls = @("tools\sigbypass-mod\mainmenu_refresh_pi8.dll",
          "tools\sigbypass-mod\catalog_pick_fix.dll")
if (-not $NoLoadout)  { $dlls += "tools\sigbypass-mod\loadout_fix.dll" }
# ---------------------------------------------------------------------------------------------
# missions_fix: RETIRED FROM THE DEFAULT SET, 2026-08-14. The missions page is now served
# NATIVELY by the backend and needs no shim at all.
#
# WHAT REPLACED IT: server/internal/interactive serves FPlayerProgression.MissionInfo on
# GET /progression/players/{id}. The native ingester (0x585A570) copy-constructs it into
# ProgressionManager+0x90, which builds real UMissionModel/UMissionPoolModel objects, loads each
# mission's data asset, and then UMissionsModel::OnMissionAssetLoaded (impl base+0x56F3ED0) sets
# bAllMissionLoaded and broadcasts. MEASURED on a clean -NoHook run: DAILIES 3/3 and WEEKLIES 8/8
# render with correct localized titles, real progress bars, correct XP tiers and a working CLAIMED
# state — with ZERO shims resident. (The mission list comes from the game's own data assets via
# server/internal/interactive/missions_catalog.json; the shim's manifest is no longer used.)
#
# WHY RETIRING IT MATTERS, not just tidiness: missions_fix manual-maps a DLL and installs a
# TRANSIENT 5-byte ProcessInternal .text patch. CLAUDE.md's measured hazard ladder at a 320 s hold
# is  nothing 0/22 · bytecode 0/9 · transient .text 4/12 · standing .text 7/8 — so every launch that
# no longer does this is a launch that no longer takes the transient-.text risk.
#
# ★ BONUS the native path also fixed: bAllMissionLoaded gates the lobby NEWS/ANNOUNCEMENT banner
# carousel too (WBP_UI_PlayScreen_LobbyV2 statement [10]), which the shim could never open because
# its model swap left that flag at 0. The banner now renders from client-config.
#
# -WithMissionsShim restores it (rollback is one flag). -NoMissions is now a no-op alias, kept so
# existing invocations and docs do not break.
if ($WithMissionsShim) { $dlls += "tools\sigbypass-mod\missions_fix.dll" }
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
Log "secondary injector started (repo=$Repo) WithMissionsShim=$WithMissionsShim NoLoadout=$NoLoadout"
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
# ★ THE GAP IS LOAD-BEARING (S109, 2026-08-04/05). It used to be 3 s, to "avoid overlapping hook
# installs". MEASURED: at 3 s the four secondaries are mapped inside a ~13 s burst starting at
# T+20 s, and EVERY death in the S109 series (20, 23, 25, 30, 35, 41, 51, 55, 65 s) lands at or
# after that burst -- while every configuration that skips this sequence entirely (clean, a single
# inert canary, catalog_store_fix alone, pi8 alone) survived 4.44 h with ZERO deaths.
#
# A 5-point gap sweep, treatment verified per run by parsing this very log:
#
#     gap    runs   exposure   injections   deaths
#      3 s      3      129 s           12        3     <- 1 per 43 s
#     10 s      4    1,210 s           20        0
#     20 s      4    1,214 s           20        0     <- DEFAULT
#     30 s      4      669 s           12        2
#     60 s      5    3,015 s           25        0
#
#   pooled >=10 s: 6,108 s / 77 injections / 2 deaths = 1 per 3,054 s
#   -> 71x lower per second, 9.6x lower per injection, P = 8.6e-05
#
# 20 s was chosen over 10 s for margin and over 60 s for cost: it is indistinguishable from 60 s in
# the data and adds ~80 s (not 4.3 min) before the store/roster/missions/passes are all live.
#
# ⚠ This is a MITIGATION, NOT A CURE. The residual is ~1 death per 3,054 s, i.e. roughly 1-in-3.4
# across a 15-minute sitting. Keep archiving crash dumps and treat an unexplained death as possibly
# ours. See docs/s109-dump-forensics.md sections 18-20 (20 retracts an earlier "eliminates" claim).
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
