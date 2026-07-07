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

**NEXT (your job): add `LokiPlayerState_Missions` replication to the stub + populate with mission data
→ the client's `OnPSMissionsUpdated` fires → `MissionsModel` populates → the Missions modal renders.**

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

## NEXT STEPS (the actual missions work)

1. (Optional) If any residual instability, un-suppress `AGameStateBase` / `ADefaultPawn` one at a time
   in `IsClassNetCacheDivergent()` (same single-variable pattern). The client is stable with only
   PlayerState un-suppressed, so likely not needed for the menu.
2. **Add a replicated `LokiPlayerState_Missions` actor to the stub.** THE HARD PART = the client must
   recognize the class so NetGUIDs resolve. Approaches to evaluate:
   - Name a stub `AActor` subclass `LokiPlayerState_Missions` (the stub already uses stock engine
     classes the client knows; a same-named class may bind by path/name).
   - OR replicate missions as a component/subobject on the (now-working) PlayerState.
   - Schema (usmap `tools/usmapdump/schema.txt:27753`): `LokiPlayerState_Missions : Actor`, 2 replicated:
     `Missions` (TArray<FMissionProgress>, RepNotify `OnMissionsUpdated`), `FinalMissionProgress`
     (TArray<FMissionProgress>, RepNotify). **FMissionProgress layout** (session-52 doc, size 0x60):
     ID(FString), AssetId(FPrimaryAssetId), PoolId(FPrimaryAssetId), Complete(bool), Failed(bool),
     ObjectiveProgress(TArray<int64>), MillisUntilExpiry(int64), Expiry(FDateTime), GrantedAt(FDateTime).
   - Client chain: OnRep(Missions) → `OnMissionsUpdated` → native `OnPSMissionsUpdated` on the
     `UMissionsModel` → populates `MissionsModel.Missions` → `WBP_UI_MissionModalCategory` /
     `WBP_UI_MissionContainer` render tiles (fully decompiled in session-52 doc).
   - Precedent for schema-matching a replicated struct: `LokiReplicatedStructs.h` +
     `Loki.cpp` `InjectServerStateReplicatedProperty` / `ForceSetUpReplicationData` (session 41).
     If stock FMissionProgress schema diverges and the client rejects the bunch, use that injection
     pattern (but PlayerState survived with stock schema, so try stock first).
3. **Populate** `Missions` with a few `FMissionProgress` entries from
   `tools/extractor/out/catalog/missions_catalog.json` (346 missions + 16 pools). Smoke-test 1-2
   Dailies first (pool `MissionPool:Daily` = DA_MissionPoolDailyEasy; mission
   `Mission:ArmoryDaily_PlayAGame`). FName ids in session-52/53 docs if needed.
4. **Reconnect + verify**: open the Missions modal (computer-use — request access; the client is a
   full-tier native app). Confirm the Dailies tab renders tiles. (The modal opened empty in every
   prior session; now it should populate.)

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
