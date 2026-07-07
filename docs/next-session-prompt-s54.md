# Continue: Dedicated-Server MISSIONS (Session 54 pickup)

Paste this into a fresh Claude session in `G:\git\Supervive Revival Project` (branch
`dedicated-server-stub`).

## TL;DR — where we are

We're reviving the UE5.4 **dedicated-server stub** (`unreal-stub/`) to deliver the **MISSIONS**
page to the live SUPERVIVE client via UE replication. Missions is the ONE menu surface with **no
client-side shortcut** (session 52 proved: no HTTP feed, mission assets don't resolve as primary
assets, and there's no game-thread native-call primitive — `ProcessEvent`-from-a-hook is a no-op).
The dedicated server (which replicates `LokiPlayerState_Missions`) is the only route.

**Session 53 BREAKTHROUGH: the long-standing DS "menu-load crash" is FIXED.** The DS gets the client
connected + into the menu (39 prior sessions of netcode RE: connect trigger, handshake, login, Join,
PC replication all work), but it always crashed ~30-71s into menu load. Session 53 proved that crash
was caused by the stub **suppressing PlayerState replication** — the client spawned a PlayerState
replica, never got a property bunch, and operated on a garbage field (a callback that got spun into a
thread at `0x7FF8F0400001` → execute-AV). **Un-suppressing PlayerState** (single-line change in
`LokiNetDriver.cpp`) makes a live client connect to the stub and sit at a **stable, working menu for
7+ minutes, zero crashes, `[UIREADY] TryUIReady SUCCESS`.** Bonus: PlayerState works with STOCK UE5.4
schema — no schema-injection needed (`NetworkChecksumMode=None` makes the client tolerate the field
divergence). Full writeup: **docs/session-53-ds-missions-gating-retest.txt**.

**UPDATE — Session 54 ALREADY BUILT the replication (committed + boot-verified).**
`unreal-stub/Source/Loki/LokiPlayerState_Missions.{h,cpp}`: a member-wise `FMissionProgress` USTRUCT
(engine `FPrimaryAssetId`/`FDateTime` so the RepLayout cmd stream is byte-identical) +
`ALokiPlayerState_Missions : AActor` named exactly `LokiPlayerState_Missions` so its path
`/Script/Loki.LokiPlayerState_Missions` binds to the client's class (both modules are "Loki").
Replicated `Missions`+`FinalMissionProgress`; `bAlwaysRelevant=true`. `LokiStubGameMode::PostLogin`
spawns it owned by the PC + seeds 2 Armory dailies. A boot-time `DumpClassNetCacheLayout` CONFIRMED
RepIndex `Missions=[11] FinalMissionProgress=[12]` (after AActor's 11 reps incl. injected
ServerState@10) — client-aligned. Stub boots clean + listening. See
`docs/session-54-ds-missions-replication.txt` + `docs/ds-server-s54-boot.log`.

**UPDATE 2 — Session 54 ALSO RAN THE LIVE TEST (computer-use). The core hypothesis is CONFIRMED; two
blockers remain and are precisely characterized.** Full detail: `docs/session-54-ds-missions-replication.txt`
(LIVE TEST section).
- WORKS: the client resolves `/Script/Loki.LokiPlayerState_Missions` by path to its own class (log:
  `... LokiPlayerState_Missions_2147480905` on the DS travel) and the actor replicates. The
  same-path-UCLASS trick is VALIDATED — no IoStore overlay. RepIndex 11/12 held.
- **BLOCKER 1 (schema) — THE NEXT-SESSION PRIORITY:** with missions seeded the client rejects the bunch
  (`ReceivedBunch: Invalid replicated field 0 in LokiPlayerState_Missions` → `ReceivedBunch failed.
  Closing connection` → ~1s reconnect loop). Empty-array isolation test (seed 0 → arrays==CDO → no
  element bytes) → error GONE, connection stable ~103s. ⇒ the desync is the **FMissionProgress ELEMENT
  wire format**, not the class layout. All 9 field types match usmap + engine sub-structs expand
  identically, so the client's FMissionProgress almost certainly has a **custom NetSerialize** (1 cmd)
  vs our member-wise ~11 cmds. FIX = RE that NetSerialize's byte layout + mirror it as a
  `WithNetSerializer` USTRUCT (pattern: `FPoolableActorServerState` in `LokiReplicatedStructs.h` +
  `Loki.cpp`). Confirm the theory first via `STRUCT_NetSerializeNative` in the client's FMissionProgress
  `UScriptStruct->StructFlags` (live RPM), or stub-side bit-count instrumentation.
- **BLOCKER 2 (crash):** even the EMPTY missions actor re-triggers the session-53 garbage-thread
  execute-AV (RIP=0x7FF8F0400001) ~103s post-Join — binding the replica makes the client half-init its
  missions subsystem then thread a stale callback. HYPOTHESIS: fully hydrating the actor (Blocker-1 fix)
  may also cure this. (A 3rd crash seen once — pre-Join read-AV at exe+0xFA4A53 — is the documented
  intermittent menu-load crash, unrelated; relaunch.)
- STILL-OPEN Q: client model association (how the client binds the replica to its local `UMissionsModel`;
  `OwningPlayerState` is NOT replicated — candidates: replicated `AActor::Owner`, a class scan, or a
  PlayerState subobject). And tune the `FPrimaryAssetId` name strings (`MakeMissionProgress` args) once
  data flows and the model populates but tiles don't filter into a category.
- `bSeedMissions` toggle in `LokiStubGameMode.cpp`: `true` = seed (iterate the NetSerialize fix),
  `false` = stable empty-actor baseline (isolate Blocker 2).

## The change already in the working tree (uncommitted — consider committing first)

`unreal-stub/Source/Loki/LokiNetDriver.cpp` — `APlayerState` removed from
`IsClassNetCacheDivergent()` (session-53 comment in the code). Module was rebuilt. Suggest:
`git add -A && git commit` the session-53 change + docs before starting new work.

## Live state at checkpoint (may have drifted/closed — reproduce via the recipe)

- A DS-connected client (this run PID ~6896) was alive + stable at the menu; stub server PID ~61312.
- If they're gone, just re-run the recipe below.

## Build + run recipe (from ELEVATED PowerShell; Steam must be running)

1. **Build stub** (only needed after editing `unreal-stub/Source/`):
   `& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' LokiEditor Win64 Development "-Project=G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WaitMutex`
   (~240s when source changed; "Target is up to date" if not. Server target isn't buildable — build
   the LokiEditor module and run via UnrealEditor-Cmd, which is the workaround.)
2. **Run stub** (headless, listens UDP 7777):
   `UnrealEditor-Cmd.exe "G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi -NoSplash -Unattended -abslog="<somelog>"`
   (UnrealEditor-Cmd.exe is at `H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\`. Wait for
   `IpNetDriver listening on port 7777` in the log. Boot takes ~60-90s.)
3. **Run client** (redirects travel to the stub):
   `configs\launch-redirect.ps1 -Hook "G:\git\Supervive Revival Project\tools\sigbypass-mod\browse_hook.dll"`
   (`browse_hook` rewrites the travel URL Host to 127.0.0.1 so the client dials the stub.
   **DO NOT add catalog_store_fix** — it crashes itself in the DS-connected catalog state.
   Client Loki.log: `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`.)
- Success signals (client): `TravelCompleted`, `Unlockable heroes fetched: 25 heroes` (repeats),
  `[UIREADY] ... TryUIReady SUCCESS`, no `crashpad`. Stub: `Join succeeded`.

## NEXT STEPS (LIVE TEST of the already-built replication)

The replication code is DONE + committed + boot-verified (see UPDATE above). What remains is running it
against a real client:

1. Run stub + client (recipe below). Watch for: does the client stay STABLE at the menu (like the
   session-53 PlayerState fix), or does it now CRASH? A new crash where s53 was stable ⇒ the
   `FMissionProgress` cmd stream desynced the RepLayout handle space (member-wise USTRUCT emits multiple
   cmds where the client expects fewer) ⇒ give `FMissionProgress` a custom `NetSerialize` +
   `WithNetSerializer=true` so it's ONE cmd — the exact fix `FPoolableActorServerState` uses in
   `LokiReplicatedStructs.h` (session 41). Check the stub log for the actor replicating + the client
   Loki.log for any `ReceivedBunch`/`Invalid replicated field`/`corrupted serialization` on
   `LokiPlayerState_Missions`.
2. If stable: open the Missions modal (computer-use — request access; the client is a full-tier native
   app) and check whether tiles render. Watch client Loki.log for `OnPSMissionsUpdated` /
   `OnMissionsUpdated` firing.
3. **If the actor replicates but the modal stays empty = the OPEN QUESTION (client model association):**
   the client must connect the replicated `ALokiPlayerState_Missions` to its local `UMissionsModel`, but
   `OwningPlayerState` is NOT replicated. Investigate how the client finds it — likely via replicated
   `AActor::Owner` (the stub sets Owner=PC), a class scan, or as a PlayerState subobject. If unclear, RE
   the client's `ProgressionManager` / `UMissionsModel` binding (session-52 doc has the BP + native API).
4. If the model populates but tiles don't appear in a category: the per-mission `FPrimaryAssetId` name
   strings are off — tune the `MakeMissionProgress(...)` args in `LokiPlayerState_Missions.cpp` (pool
   `MissionPool:Daily` = DA_MissionPoolDailyEasy, mission `Mission:ArmoryDaily_PlayAGame`; the container
   filters by PoolId + `Hero==self`). Full catalog: `tools/extractor/out/catalog/missions_catalog.json`.

Gotcha found session 54: UE 5.4 `NetUpdateFrequency` is a PUBLIC member (assign directly);
`SetNetUpdateFrequency()` is 5.5+ and won't compile.

## Key files
- `unreal-stub/Source/Loki/LokiNetDriver.cpp` — suppression (`IsClassNetCacheDivergent`,
  `ShouldReplicateActor/Function`), `InitBase` (NetworkChecksumMode=None).
- `unreal-stub/Source/Loki/LokiStubGameMode.{h,cpp}` — where to spawn the missions actor (PostLogin).
- `unreal-stub/Source/Loki/LokiReplicatedStructs.h` + `Loki.cpp` — replicated-struct + runtime
  FProperty/UFunction injection primitives (sessions 27-32, 41).
- `docs/session-53-ds-missions-gating-retest.txt` — full session-53 writeup (crash char + the fix).
- `docs/session-52-missions-page-decompiled.txt` — client missions data path + FMissionProgress layout
  + the full MissionsModel API.
- `docs/dedicated-server-stub.md` — the 39-session DS history (connect trigger, handshake, RPC sig).
- `tools/re/parse_minidump.py`, `tools/re/dump_all_threads.py` — Sentry-dump crash analysis.
- `tools/extractor/out/catalog/missions_catalog.json` — the mission data.
- memory: `supervive-dedicated-server-status`, `supervive-missions-page-status`.

## Gotchas
- Steam MUST be running before launching or login dies (Auth Failure 14005).
- Intermittent menu-load crash (~1 in a few launches, unrelated) — just relaunch.
- `browse_hook` injection occasionally loses the race — kill the game + re-run.
- Sentry crashpad writes dumps to `<GameRoot>\Loki\.sentry-native\reports\<uuid>.dmp` (NOT UECC dir;
  no Windows WER event). VEH crash shims DON'T fire (crashpad pre-empts) — parse the dump instead.
- The game's anti-tamper (`preloader.dll`) hooks `NtCreateThreadEx` — don't try to hook thread
  creation. (Was a dead end this session.)
- `catalog_store_fix` is UNSAFE in the DS-connected context (crashes itself). Don't inject it.
