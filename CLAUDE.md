# SUPERVIVE Revival — project rules for Claude

This is a reverse-engineering project to revive a Steam-launched UE5.4 game whose
official backends are dead. We've redirected the client to a local Go server
(`server/cmd/ags`) over hosts-file + HTTPS-with-self-signed-cert. The work spans
backend RE, IoStore extraction, native shim injection, and asset-registry patching.
Lots of dead ends. Honor the prior-work docs.

The whole front-end menu is now ONLINE: login, the ALL HUNTERS roster (+ click-to-
refresh), the STORE, COSMETICS, the full MISSIONS page (with working progress
bars), the PASSES / Hunter's Journey account pass (full 85-tier ladder), and the
AVATAR / CALLSIGN customization (render + live switching) all render live. That was
achieved with the backend feed **plus** a set of client-side native shims built on a
reusable game-thread native-call primitive (see below).

**Current frontier = the tutorial WORLD.** Getting in is solved (S107/S108): the client
loads `LVL_Tutorial`, the hero spawns, is possessed, moves, and **walks/runs with real
locomotion animation** (S108b). The whole sitting is now **hands-free** — no human at the
keyboard (see "Tutorial sittings" below). What is still open is *simulation* (abilities /
combat: the hero owns no ability system) and *stability* (the run dies within ~1–5 min and
the cause is not attributed).

## Before doing anything else

### If the user mentions hero/roster/grid/hunters/store/cosmetics/missions modal/passes/battlepass
**These are SOLVED — they render live.** Do NOT re-open the closed hypotheses.
- **Roster / store / cosmetics** — root cause was one un-set client-side
  catalog-ready sub-flag (`CatMgr+0x354`), NOT the backend, NOT enumeration, NOT
  LokiAssetManager bypass (all falsified over ~13 sessions). Fix = the native shim
  `tools/sigbypass-mod/catalog_store_fix.dll` (self-restoring `jz`-NOP that dodges
  the ~3–5 min integrity check + AssetManager scan + CatalogEntry poke). STORE
  tiles also need the backend to mark cosmetics `IsOwned` (`handleInventory`).
  Living log: `docs/hero-roster-attempts.md`; memory `supervive-hero-roster-blocker`
  + `supervive-store-status`.
- **Missions** — the full page renders client-side via the native-call primitive
  (`AsyncLoadPrimaryAssets` → `CreateMissionModelFromFinalProgress` → swap
  `ProgMgr.MissionsModel`), packaged as `tools/sigbypass-mod/missions_fix.dll`
  (`launch-redirect.ps1 -Missions`). Per-account progress served by the backend.
  Read `docs/session-59-progress-bars.txt` + `docs/missions-progression-hookup.md`;
  memory `supervive-missions-page-status`.
- **PASSES / Hunter's Journey (ACCOUNT pass)** — the page renders live with its full
  85-tier ladder (S83). Two client-side root causes, NOT the backend (that route was
  exhausted over ~9 probes): (1) `CheckAccountPassChanges` (`0x5794480`, the populate's
  real caller) bailed on its tier gate `dword[PM+0x90+0xEC] == -1`; (2) the keystone —
  a **VM map-key mismatch**: it finds the view model by `P->GetPrimaryAssetId()`
  (vtbl+0x1D0) → `ToString` (`0x12F4230`) → `FindVM` (`0x57AB180`), i.e.
  **`ProgressionTrack:HuntersJourney`**, while our track keyed it bare `HuntersJourney`.
  Fix = `tools/sigbypass-mod/battlepass_adopt_fix.dll` resolves that key at runtime and
  adopts with it (BUMP its `Version` on every re-inject). Two traps: `VM.Levels`(+0xC8)
  is `TArray<UObject*>` (NOT PrimaryAssetId) and the populate `0x57DF4B0` CONSTRUCTS
  objects — **never force-call it** (that was the S82 crash); and the old note
  "P = S[+0x238]" is WRONG (S *is* `HuntersJourney_C`).
  Read `docs/session-83-passes-tier-grid-solved.txt`; memory
  `supervive-passes-battlepass-status` (its POST-SESSION CORRECTIONS block is
  load-bearing — a later 21-agent RE pass showed the grid is built by the VM
  builder's Init `0x57BB560` ahead of both gates, so the map key is the SOLE
  verified cause, and it FALSIFIED "the backend route is exhausted": the native
  ingester `0x585A570` does exist). Still open: real PROGRESS (tiers draw but
  nothing is claimed — gated on `byte[PM+0x388]`) and the SEASONAL pass (same
  byte, plus no packed `LokiDataAsset_Season`).

- **AVATAR / CALLSIGN (player-card customization)** — SOLVED end-to-end, BACKEND-ONLY,
  no shim (S85, 2026-07-21). Three causes, none the render/enum: (1) the avatar CARD
  reads `PartyMember.PersonalizationLoadout` which we never served — fix = `buildSoloParty`
  serves `personalizationLoadout` on the party member; (2) switches wrote to the WRONG
  ACCOUNT — the client's `/oauth/token` grant fell to an ad-hoc `"player"` key
  (`b70b628c…`) while the Steam login + party used `platform:steam` (`9b9d…`); fix =
  `token.LocalPlayerKey`/`LocalPlayerID` canonicalizes every unidentified-user auth path;
  (3) `UPartyModel::SetParty` (`base+0x587BE90`) gates the whole party doc on a strict
  monotonic `FParty.Version` (`cmp [PartyModel+0x568]; jge bail`) — we pinned `1`; fix =
  `store.partyVersion()` bumps on each loadout write. LATENCY (~30-57s → ~1.5s): the client
  applies the party ONLY on its `/notifications` messenger-RECONNECT resync, so we DROP that
  socket on a loadout write (`ws.Conn.Drop()` + `lobby.MarkDirty`, wired via
  `interactive.SetPartyDirtyNotifier`). The ~1s floor is the client's own reconnect backoff
  (not backend-controllable); a native shim (write member loadout + broadcast
  `OnPersonalizationLoadoutChanged` `base+0x587C699`) would reach ~0.2s but adds a PI-hooker —
  parked. ⚠ `PartyModel` exposes NO reflected `Version` UProperty (absence of a UProperty ≠
  absence of the field). ⚠ the `avId:""` presence trap: sample presence AFTER an equip.
  Read `docs/session-85-avatar-render.md`; memory `supervive-avatar-render-status`.

Before RE-touching any of these, READ the relevant doc above first — the value is
the trial-and-error history, and the corrected root causes are easy to regress on.

### Before touching anything tutorial- / FK-7- / FK-24-shaped
Read `docs/s108-fk24-instrument-corrected.md` **including its RETRACTIONS block at the
top, which governs**, then `docs/s108b-ksmactor-bisect.md`, `docs/s108-crash-triage.md`,
`docs/s108-fk7-verification-attempt.md` and `docs/s108-skeptic-review.md`. Memory:
`supervive-fk24-probe-self-lethal`, `supervive-tutorial-crash-fk7`.

The short version, because it has already cost two sessions:
- **The FK-24 watchpoint probe was killing the game**, and its crash was recorded as a
  game crash for a whole session. Dump `166396E2` (DR mode) and `FED1F952` (page mode) are
  both **the shim self-killing**, not FK-7. Do not feed them to `crash_census.csv` analysis.
- **S107's "the watchpoint is VOID → escalate `wprobe`→`wprobe2`" was unfounded.** The DR
  watchpoint fired fine (127/128 threads armed, GameThread among them). The writer of the
  `0x01` byte at `PCM+0x420` is **still NOT named**; FK-24 is OPEN.
- **FK-7 is OPEN.** Zero reproduce-then-repair runs exist. The `play_novtguard` positive
  control is MANDATORY and a **quiet control means the sitting is VOID, not a pass**.
  Hold to **T+220–250 s, NOT T+300 s** — the code-integrity kill lands at ~285 s.
- ⚠ **`play`'s `.text` hash has moved TWICE. Current: `7bc4df9236ead0ac`** (S109 root-bit fix).
  `ae532866e15fd8ac` was `play` only between S108b and S109; `a67239a0d83d9300` is `play-statictest`
  (S108b flipped `KSTATICTEST`). Docs citing either as "the candidate" are stale.
  ⚠ `play` / `play-strictroot` share a 161,792-byte `.text`, and `play` / `play-earlywalk` shared
  identical whole-file AND `.text` SIZES — **only the hash separates them. Diff `.text`, never size.**
- ⚠ **`KGCROOT` was silently INERT from S106 until S109.** Its root-bit corroboration used
  `AND(native classes) & ~OR(sampled ordinary objects)` on the false premise that ordinary objects are
  never rooted; **one** rooted sample in 64 vetoed the correct bit, so nothing was ever rooted. Fixed
  (frequency test; `-DKGCROOTSTRICT=1` restores the old one). ⚠ **Fixing it did NOT stop the asset
  collection** — the run AnimSequence is still collected with a verified `flags -> 40000004` readback,
  if anything sooner. So "rooting keeps it alive" is **not established in this build**.
  See `docs/s109-dump-forensics.md` §22-§24.
- ★★ **S110 ANSWERED THE MECHANISM — read `docs/s110-item-watch-gc-mechanism.md` before touching the
  anim/GC thread.** The asset really IS garbage-collected (full `BeginDestroyed → FinishDestroyed →
  LowLevelRename(NAME_None) → FreeUObjectIndex` pipeline, then the slot reissued 20 s later), so
  "torn down out of band" is ELIMINATED. The poked RootSet bit was set and readback-verified 251 ms
  before the destruction and did not prevent it; the engine zeroed it with the rest of the word.
  **Do not "fix" this by rooting harder.** Four other objects poked identically in the same pass
  survived — including one of the two `AnimSingleNodeInstance`s — because the traversal REACHED them.
  The run anim is referenced by nothing but a DLL C global. ⚠ Also: **"Unreachable" is not a sticky
  bit in this build.** Reachability is an alternating flag rotating through bits 0/1/2, flipped
  population-wide each GC pass — which is what S109's unexplained `flags=00000004` / "bit 1 on 81% of
  ordinary objects" actually was, and it gives a free read-only GC clock (`tools/re/item_watch.py`).

### Before touching anything menu-shaped
Skim `docs/trackb-notes.md` (Track B endpoint surface + ClientProfileData model)
and `docs/endpoints.md` (every endpoint the client hits + handler status).

### Before touching anything extraction-shaped
Skim `docs/findings.md` and `docs/r2-findings.md` (IoStore catalog + usmap RE +
the non-standard UObjectBase layout in this build: nameOff=0x20, classOff=0x18,
NOT the stock 0x18/0x10). `docs/game-map.md` has the full 68,228-asset catalog.
S110 calibrated the other two fields live (`tools/re/item_watch.py`, 400/400 and
100%/0% controls): **ObjectFlags@0x0C, InternalIndex@0x10** — so an object's
`FUObjectArray` slot can be read straight out of the object, no scan needed.

### Before touching anything AR-bin-shaped
Read `docs/trackb-assetregistry-route.md`. The `assetregistry apply-patch`
extractor subcommand works end-to-end; loose-file AR.bin deployment has been
proven INERT in this IoStore build (UE ignores the loose file even when valid).
Deployment requires an IoStore mod-pak overlay — non-trivial.

### Before touching anything native-shim-shaped
The keystone technique is a **game-thread native-call primitive**: hook
`ProcessInternal` (`base+0x13454A0`), capture a live `FFrame`, then call the target
`UFunction`'s native thunk (`UFunction.Func @ +0xE0`) **directly**. The direct call
has no guards, so it works where slot-56 `ProcessEvent` no-ops for native functions.
Param passing, OUT params (`FFrame.OutParms @ +0x80`), and `AsyncLoadPrimaryAssets`
are all RE'd on top of it. Read `docs/session-55-native-call-primitive.txt` (+ s56/
s57/s58/s59) and the `missions_nativecall_probe*.cpp` / `tools/re/*.py` families
before building a new shim. Memory: `supervive-missions-page-status`.

Two `ProcessInternal` hooks that stay PERMANENTLY installed race (they clobber each
other's prologue). The fix (S59): every PI-hooking shim (`mainmenu_refresh_pi8`,
`missions_fix`, `loadout_fix`) installs its 5-byte jmp only TRANSIENTLY — install →
piggyback one game-thread call → uninstall — serialized through a shared named mutex
`Local\SuperviveMissionsPIHook`, so only one has the hook installed at any instant.
That retired the old "mutually exclusive launch modes" split: all three now coexist and
inject together as the default set (see the launch procedure below).

## Launch / run procedure

From an **ELEVATED PowerShell**:
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1              # redirect + server + game; injects the FULL shim set
.\configs\launch-redirect.ps1 -NoMissions  # everything EXCEPT missions_fix (isolate non-missions surfaces)
.\configs\launch-redirect.ps1 -NoLoadout   # everything EXCEPT loadout_fix (isolate non-customization surfaces)
.\configs\launch-redirect.ps1 -NoHook      # clean RE run, no shim injection
```

By default the launcher injects the primary `catalog_store_fix.dll` (roster + store +
cosmetics) at launch, then `configs/inject-secondaries.ps1` injects the full secondary
set once it settles: `mainmenu_refresh_pi8` (pick→center refresh), `catalog_pick_fix`
(pick-commit), `loadout_fix` (customization/skin persistence), `missions_fix`
(durable missions page), and `battlepass_adopt_fix` (PASSES / Hunter's Journey — S83).
One launch = every durable fix, together. `-NoMissions` / `-NoLoadout` / `-NoPasses`
trim individual shims; `-Hook <path>` injects exactly one DLL and no
secondaries. `-Missions` is kept as a deprecated no-op alias (missions are now default).

**★ THE SECONDARIES ARE NOW INJECTED 20 s APART, AND THE MENU TAKES ~100 s TO FULLY POPULATE.**
That is deliberate and is **not** a regression — do not "fix" it by lowering the gap. S109
(2026-08-05) measured that injecting them ~3 s apart is what kills the process: with the old
3 s gap the four secondaries landed in a ~13 s burst and the game died at **1 per 43 s**;
at ≥10 s gaps the hazard is **71× lower** (`P = 8.6e-5`). Gap sweep, treatment verified per run:

| gap | exposure | injections | deaths |
|---:|---:|---:|---:|
| 3 s (old default) | 129 s | 12 | **3** |
| 10 s | 1,210 s | 20 | 0 |
| **20 s (new default)** | 1,214 s | 20 | **0** |
| 30 s | 669 s | 12 | 2 |
| 60 s | 3,015 s | 25 | 0 |

`configs/inject-secondaries.ps1 -GapSeconds N` (or `launch-redirect.ps1 -InjectGapSeconds N`)
changes it; pass `3` to reproduce the old burst. ⚠ **MITIGATION, NOT A CURE** — residual is
~1 death per 3,054 s (~1-in-3.4 over a 15-min sitting), so keep archiving dumps and treat an
unexplained death as **possibly ours**. Full evidence: `docs/s109-dump-forensics.md` §12–§20
(§20 retracts an earlier "eliminates" claim; §16 retracts "the PI hook is the mechanism").

**★ `configs/fk24-stage.ps1` now enforces the same minimum gap** (`-InjectGapSeconds`, default
**20**). It was NOT a uniform burst — measured spacing was gft→fo **~5 s** (lethal regime),
fo→sp **19 s**, sp→probe **7–17 s** — so only the first gap was clearly bad. The gate is a
*minimum*: the existing evidence waits (world-load, `[SP] done step=4`) count toward it and only
the shortfall is slept, costing **~15–29 s** of staging rather than ~50 s. The probe now arms
around **T+175 s** instead of ~T+145 s, leaving ~110 s before the ~285 s integrity kill — so the
**T+220–250 s hold still fits, but the armed window is tighter**; budget accordingly.
⚠ **UNVALIDATED ON A LIVE TUTORIAL RUN.** The 71× reduction was measured on the *menu* route.
Whether it moves the ~1–5 min tutorial deaths is the open question — and it is now the single
highest-value experiment on the board.
⚠ Do NOT re-derive stage spacing from `docs/fk24-stage-*-N-*.txt` mtimes: `Copy-Item` preserves the
SOURCE's LastWriteTime, and step 1 copies a stale marker `gft` never writes, so that delta reads as
+210 s or even +41,742 s. Only steps 2–4 are real.

**RESOLVED (was VALIDATION PENDING since 2026-07-10):** the default set runs THREE PI-hookers
(`pi8` + `loadout_fix` + `missions_fix`) and the full triple now has many confirmation launches.
It is **not** the killer: S109 showed `-NoPasses` (both PI hookers present) is ~21× *safer* than
`-NoMissions` (one present), and `pi8` alone ran 90 min clean. The shared-mutex design is fine;
the injection **burst** was the problem. `-NoMissions` / `-NoLoadout` still isolate individual
shims. See `supervive-missions-page-status` and `supervive-crashpad-capture-runtime-family`.

**Steam must be running first**, or login dies with `Auth Failure 14005` (SteamAPI
init fails). Easy to miss; surface this gotcha if you see Steam not running.

**Shim readiness:** the launcher fires the injectors detached then blocks on the game,
so for a consolidated "did every shim activate?" view run `.\configs\shim-status.ps1`
(or `-Watch`) in a SECOND terminal. It's read-only — reads each shim's `docs/*-marker.txt`
and classifies READY / running / FAILED / leftover (anchored to the game's start time so a
shim that finished and went quiet still reads READY, and a marker from a prior launch reads
`leftover`). Safe to run anytime, including while another session has the game open.

The script blocks until the game exits. Read live `Loki.log` at
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (NOT `docs/` — that's
the backend `capture.log` for HTTP traffic). The loopback admin panel is at
`http://127.0.0.1:9210/` while `ags` runs (hunter unlocks, store/ownership, wallet,
mission progress, per-account state; see `docs/admin-panel.md`).

### ★ Tutorial sittings (FK-7 / FK-24 / anything in `LVL_Tutorial`) — HANDS-FREE

**Do not improvise this, and do not use `-Hook <play dll>`.** `RM_PLAY` and
`RM_SPAWNPOSSESS` are **continuation** modes: they attach to an already-running tutorial
and `return 0` before the force-open block, so a lone `-Hook` **cannot work** (S107 wasted
a launch proving it).

The old recipe needed a human to press PLAY → TUTORIALS → BASIC TRAINING → START. It no
longer does. That press has exactly ONE backend effect — `POST /startSoloMode` sets
`playerState.SoloMode` — and `handleCoreGamePlayer` gates on
`forceTutorialMatch || SoloMode != ""`. So flip the flag instead:

```powershell
# 1. server/internal/interactive/interactive.go -> const forceTutorialMatch = true
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

# 2. ELEVATED PowerShell. Steam must already be running.
.\configs\launch-redirect.ps1 -NoHook          # returns after launching; game keeps running

# 3. SECOND call, once the game is up — stages the world and injects the DLL under test:
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_play.dll -Label myrun
```

MEASURED: with the flag on, the client parks itself **~13 s** after launch. `fk24-stage.ps1`
pre-flights that `ags` is really arming a match and refuses to run otherwise, then injects
`gft_ready_fix` → `tutorial_launch_fo` → `tutorial_launch_sp` → your probe, **gating each
step on measured evidence** and copying the marker off after every injection.
**Set the flag back to `false` when done** — otherwise a normal launch auto-parks into the
tutorial loading screen and looks broken.

⚠ **Order is load-bearing, and each of these cost a dead run:**
- `gft_ready_fix` goes **BEFORE** the force-open. The old documented `fo → gft → sp` order
  only worked because S107 injected all four back-to-back and gft landed *during* the 5.7 s
  LoadMap. Gate between them and the run dies with the log full of
  `ULokiGameFeatureToggles::Get … called when feature toggles were not ready`.
- Wait for `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` — **not** the bare
  string `LVL_Tutorial`, which the force-open's own echoed console command also contains.
- Wait for sp's own `[SP] done step=4` before injecting the probe. `ResolveSpawnPossess`
  and `RM_PLAY`'s resolve are both **one-shot, no retry**; a fixed 5 s sleep is not enough
  and the probe aborts at `[PL] ResolveWakeMove failed … -> abort` having armed nothing.
- `[SP] gm=0x0 pc=0x0 startSpot=0x0 heroClass=0x0` = the world is gone. Do not proceed.

**Expected yield: only ~2 of 4 launches reach the armed window.** Budget on *armed windows
reached*, never on launches.

Success looks like this in `docs\tutorial-launch-marker.txt`:
```
[SP]   gm=0x… pc=0x… startSpot=0x… heroClass=0x…        <- ALL FOUR non-zero
[SP]   done step=4 spawnedPawn=0x… cls=BP_HERO_Ronin_C
[PL]   *** init complete: body=BUILT; camera + WASD active ***
[ANIM] PlayAnimation(run, loop) ok / PlayAnimation(idle, loop) ok   <- locomotion animating
```

For iterative server-only restarts (game already running at menu, want to swap
backend behavior): kill `ags`, rebuild with
`& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`,
restart manually (regen certs + re-append to cacert.pem if you want a clean cert
chain). See `docs/hero-roster-attempts.md` "How to reproduce" for the exact recipe.

## Code conventions for this project

- Backend handlers live in `server/internal/<package>/<name>.go`. Each handler's
  comment block should record what was tried + what worked + what didn't, with
  dates. The trial-and-error history is the value.
- Probe-driven backend work: prefer **single-variable changes**. Bundled tests
  (10 changes at once) have repeatedly produced ambiguous results that wasted
  cycles. If a hypothesis fails, REVERT the probe before testing the next one.
- Validity model for endpoints: UE's `JsonObjectStringToUStruct` IGNORES unknown
  JSON keys and only rejects the whole doc when a key that DOES match has a wrong
  type. So adding speculative fields is safe; sending wrong-typed matched fields
  is not. See the comment at the top of `server/internal/menu/menu.go` for the
  full validity model.
- The two distinct LogLokiPlatformQuery error strings mean different things:
  `"Invalid response received"` = a required top-level field is absent.
  `"Deserialization failure"` = JSON parsed but container type mismatched target struct.

## Tooling shortcuts

- **Extractor:** `tools/extractor/` — .NET 9 / CUE4Parse-based. Subcommands:
  `enumerate`, `names`, `namesall`, `dump`, `raw`, `schema`, `assetregistry`.
  Build/run with
  `& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release` from `tools/extractor/extractor`.
- **usmap regeneration:** `tools/usmapdump/usmapdump.exe extract <exe-path>`
  produces `mappings.usmap`. Needed when game updates.
- **usmapdump RE commands:** `strings`, `wstrings`, `xref`, `disasm`, `peek`,
  `threads`, `findgametid`, `assetmgr` — read-only RPM, no injection.
- **usmapdump dumpimage:** `usmapdump.exe dumpimage <proc> [outDir]` — snapshots the
  live UNPACKED image to a cold PE for offline Ghidra/IDA (file-offset==RVA, ImageBase
  set to the live base, so project `base+0x…` addresses map 1:1). Also dumps private
  exec regions outside the module + a coverage manifest. Pure RPM (safe). CAVEAT: the
  build demand-decrypts `.text` pages on execution, so a single dump only captures pages
  the game has RUN — ~50% of `.text` at a fresh menu. Coverage rises the more code the
  game exercises; re-dump from a richer state (in-game) for more. Also writes
  `<stem>.exports.txt` (addr→module!export map, captured live) so `reconstructiat` can
  rebuild imports OFFLINE later. Dumps land in `/dumps/` (git-ignored).
- **usmapdump mergedumps:** `usmapdump.exe mergedumps <outFile> <in.dump.exe…|dir>` —
  unions several `dumpimage` snapshots into one maximally-covered image (fills each dump's
  demand-decrypt `.text` gaps from the others). A directory arg recurses for `*.dump.exe`.
  This is the path to near-complete `.text`: dump from DIFFERENT game states (login, hero
  grid, store, missions, and especially IN A MATCH — gameplay code never runs at menu),
  each to its own `dumps/<state>/`, then `mergedumps dumps/merged.dump.exe dumps`. Gain per
  dump = how much NEW code that state ran (two idle-menu dumps barely differ). CONSTRAINT:
  all inputs must share the same module base (ImageBase); a different-ASLR-base dump is
  rejected (its relocated `.text` bytes are incompatible). `.text` union is exact; the
  reported %, being non-zero-based, slightly undercounts (readable-zero bytes read as gaps).
- **usmapdump reconstructiat:** `usmapdump.exe reconstructiat <dumpFile> [outFile]` —
  rebuilds a real import table so Ghidra/IDA name API calls instead of raw IAT thunks, when
  the dumped IAT holds DIRECT resolved export addresses (unprotected binaries, e.g.
  explorer). Maps each slot to `module!export` via the `<stem>.exports.txt` sidecar, appends
  an `.idata2` section (descriptors + INT + names), repoints the Import data-dir. Fully
  OFFLINE. Validated on explorer (1066/1066). For SUPERVIVE use `deobfimports` instead — its
  IAT is import-PROTECTED (see below), so reconstructiat resolves ~0 of its slots.
- **usmapdump deobfimports:** `usmapdump.exe deobfimports <proc> <dumpFile> [outFile]` — the
  SUPERVIVE path. Its imports are VMProtect/Themida-PROTECTED: each IAT slot points to an
  obfuscated trampoline in a packer-hidden region (NOT any registered module), computing the
  real API as `real = C2 ^ ROL64(C1 + M, 0x33)` (per-stub C1/C2 imm64; M = a per-launch data
  qword) then `jmp`-ing to it. deobfimports EMULATES each stub (x86asm decoder + tiny integer
  interpreter) against the LIVE process to recover the real target, VERIFIES it against the
  exports sidecar (exact match — a mis-emulation can only yield "unresolved", never a wrong
  name), then rebuilds the table like reconstructiat. Needs the SOURCE process ALIVE (stub
  code + M are read live; M encodes the ASLR-relocated target). Validated: **1107/1107 slots,
  0 undecodable, 0 off-target**; output parses in `debug/pe` (all 1107 named). `capture-dumps.ps1
  -Finalize` calls this automatically while the game runs.
- **Manual mapper / DLL injector:** `tools/inject/` — for no-throw payloads only
  (C++ exception unwinding gets eaten by the packer's vectored exception filter).
- **Native shims:** `tools/sigbypass-mod/` — `catalog_store_fix` (roster/store/
  cosmetics), `missions_fix` (durable missions page), `mainmenu_refresh_pi8`
  (pick→center refresh), `loadout_fix`, `tutorial_launch`, plus the
  `missions_nativecall_probe*` RE series that built the native-call primitive.
- **Tutorial sitting driver:** `configs/fk24-stage.ps1` — stages the tutorial world and
  injects a probe/candidate DLL hands-free. `-Probe <dll> [-Label <tag>] [-SkipProbe]`.
  Copies the marker off after each stage into `docs/fk24-stage-<label>-<n>-<shim>.txt`,
  because `Marker()` opens `CREATE_ALWAYS` so **every injection truncates
  `docs/tutorial-launch-marker.txt`** (FK-25). See the launch procedure above.
- **Crash-dump archiver:** `configs/archive-crashdumps.ps1` — preserves Sentry/crashpad crash
  reports (the 43.8 MB minidump + that run's own `Loki.log`) out of
  `<GameRoot>\Loki\.sentry-native\` into `dumps\crashpad-<stamp>\`, SHA-256 verified, source never
  deleted. `launch-redirect.ps1` calls it automatically before launching and after the game exits;
  safe to run by hand anytime (`-Label <tag>`). Parse a dump with
  `python tools/crashtri/mdctx.py <reports/*.dmp>` — there is no cdb/WinDbg on this machine.
- **RPM probes:** `tools/re/*.py` — Python probes driving the native-call primitive
  (struct/field/rep-layout walkers, param/OUT-param builders, mission-model dumps).
- **Admin panel:** loopback JSON API + embedded GUI in `server/internal/admin/`
  (`-admin`, default `http://127.0.0.1:9210/`). See `docs/admin-panel.md`.

## What NOT to do

- Don't run `launch-redirect.ps1 -Revert` casually — that strips the hosts entries
  + cacert mods. Only when the user explicitly asks to clean up.
- Don't use Steam to launch the game for testing the redirect — Steam launches the
  exe with no `-ini:` overrides, so the backend redirects don't apply.
- Don't kill the `SUPERVIVE-Win64-Shipping` process without warning — the user may
  be mid-test.
- Don't propose another C++-exception-using payload for injection. We tested
  three canary variants; the packer's exception handler kills the process even
  with `__CxxFrameHandler3` properly imported.
- Don't propose `ScanPrimaryAssetTypesFromConfig` as a shim target again — the
  function `__report_gsfailure`s mid-call regardless of thread context (verified
  via off-thread call, thread-hijack with fresh stack, thread-hijack with own
  stack, and APC on the real game thread).
- Don't leave a permanent `.text` patch in place — the ~3–5 min code-integrity
  check catches it and kills the process. Any raw `jz`-NOP must be self-restoring
  (patch → let the builder run → restore), the way `catalog_store_fix.dll` does.
- Don't leave a `ProcessInternal` hook PERMANENTLY installed if another PI-hooking shim
  is present — they race on the prologue. Coexisting PI-hookers must install the jmp only
  TRANSIENTLY and serialize via the shared `Local\SuperviveMissionsPIHook` mutex (the way
  `mainmenu_refresh_pi8` / `missions_fix` / `loadout_fix` do). That's what lets all three
  inject together in the default set — any NEW PI-hooking shim must follow the same pattern.
- Don't trust the extracted usmap for replicated container types — it has been
  wrong repeatedly (DS missions work cost several passes). Verify struct/array
  shapes against live RPM.
- **Don't read "no `UECC-*` directory in `Saved\Crashes`" as "the run died with no dump."**
  Sentry's **crashpad** writes a full minidump (43.8 MB) plus that run's own `Loki.log` into
  `<GameRoot>\Loki\.sentry-native\`. `harvest.py` and every hand-rolled census that enumerates
  `UECC-*` is blind to it. The clean tell in `Loki.log` is `handing control over to crashpad`.
  ⚠ That key is **NOT the last line** (two `LogTemp` lines follow it in the one death with a
  preserved dump) — scan the whole file, never `tail`. Bare `crashpad` is useless as a key: it
  matches two **startup** lines present in every session.
- **Don't rush to save a crashpad dump — and don't trust the retired "~60 seconds" advice.**
  RETRACTED S109: the old "uploads and DELETES it within ~3 minutes" was the gap between two `ls`
  calls with a relaunch inside it. MEASURED: crashpad tries **one** upload at crash+2 s, and on
  failure the report sits in `state=Pending` **indefinitely** (65+ min observed) because
  `crashpad_handler.exe` dies with the game and cannot retry. **The NEXT GAME LAUNCH is what
  clears it.** `launch-redirect.ps1` now archives the database automatically before launching and
  after the game exits (`configs/archive-crashdumps.ps1`, SHA-256 verified, never deletes the
  source); run it standalone anytime. ⚠ It depends on the upload failing — if the archiver ever
  warns "crashpad handoff but NO report on disk", uploads started succeeding and you must
  hosts-block `o566896.ingest.sentry.io`. See `docs/s109-fk9-capture-durable.md`.
- **Don't leave an S9x diagnostic switched on and then reason about the game.** This has now
  bitten twice: `KTESTACTOR` (S106) built a second degenerate body, and `KSTATICTEST` (S108b)
  called `PlayAnimation` on a `StaticMeshComponent`, faulting every run — SEH-caught, so it
  never crashed, it just printed `anim swapping DISABLED for the rest of the session` and
  **killed the hero's walk/run animation in every session for weeks**. Both defaulted to 1
  in shipped builds. When a shim behaves oddly, audit what the *shim* is doing before
  theorising about the game.
- **Don't A/B two DLLs without diffing their `.text` sha256.** Three artifacts have shipped
  identical-but-differently-named, and an A/B against a copy of itself burns a live run.
  When a `-D` default changes, DELETE the now-redundant variant rather than leaving a
  duplicate (S108b removed `play-nostatictest`/`play-nodiag` for exactly this).

## Memory layout

`memory/MEMORY.md` is the auto-loaded index. Project memory files (loaded on
demand when topics come up):
- `supervive-revival-overview` — goals, stack, redirect approach
- `supervive-milestone{1,2,3}-status` — chronological milestones
- `supervive-milestone3-trackb-status` — interactive write-back endpoints
- `supervive-hero-roster-blocker` — SOLVED; roster/store/cosmetics root cause + fix
- `supervive-store-status` — STORE online (bundles/skins/featured/supporter packs)
- `supervive-missions-page-status` — missions page + the native-call primitive
- `supervive-customization-persistence` — loadout write-back / equip persistence
- `supervive-dedicated-server-status` — DS stub + missions replication (parked)
- `supervive-tutorial-launch-status` — tutorial force-launch (world + possessed hero)
- `supervive-fk24-probe-self-lethal` — ★ the FK-24 probe was killing the game and its
  own VOID verdict was an artifact; hands-free sittings; the `KSTATICTEST` animation fix
- `supervive-tutorial-crash-fk7` — FK-7, still OPEN (zero reproduce-then-repair runs)
- `supervive-instrument-artifact-pattern` — ★★★ the project's dominant error mode; read
  it before recording ANY negative result as a property of the game
- `supervive-rpc-signature-solved` — ServerVerifyViewTarget 40-param signature
- `supervive-ags-cert-rebuild-gotcha` — re-append root.crt to cacert.pem on rebuild
