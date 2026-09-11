# Next session (S77) — DS route: solve the MOVEMENT garbage-thread crash → functional tutorial control

## The goal
Get **any kind of actual functional control in the tutorial** — a hero (or even just a spectator camera) that
**moves without crashing** over the live SUPERVIVE tutorial world, via the dedicated-server-stub (DS) route.

## Where we are (committed, verified — start here, don't re-derive)
The DS route (branch `dedicated-server-stub`, `unreal-stub/`) now reaches **very far**, and the last session
(S76 cont.) made the **stub durably stable**. Read `docs/session-76-worldsettings-breakthrough.md` (esp. the
CORRECTION section) + memory `supervive-dedicated-server-status` before touching anything.

What the client reaches over the DS route, verified live:
- Connects to the stub (127.0.0.1:7777) → travels to `LVL_Tutorial` → enters its **real replicated
  `LokiGameState`** (S70) → gets a real **Loki-typed PlayerController** (S73, TryGetLocalLokiController works) →
  a real **LokiPlayerState** → past the World-Partition level-visibility gate (S73).
- The stub **possesses a `LokiCharacter`** for the client (server-side).
- The client's own match flow advances to the **pre-drop hero screen** (hero BRALL, "DROP LEADER") and the
  "BATTLE ROYALE: THE BREACH … LOADING" match-load screen.
- The native dead-spectator camera is alive: mouse **rotates** the view (locked horizontal plane).

★ **STUB IS NOW STABLE (committed 4261e2f):** un-suppressing `AWorldSettings` had made the stub reliably crash on
the push-model assert (`bIsPushBased == Other.bIsPushBased`, CoreNet.h:331). Fixed with `ALokiWorldSettings`, a
**non-push mirror** (`LokiWorldSettingsStub.{h,cpp}`; S70 pattern — call `AActor::GetLifetimeReplicatedProps`, then
register derived props NON-PUSH), swapped in as the world's WorldSettings at map-load in
`ULokiGameEngine::LoadMap` (it's a serialized level actor, so `GEngine->WorldSettingsClass` can't do it — runtime
`SetWorldSettings` swap instead). **This technique is REUSABLE to un-suppress ANY stock class without the push
assert.** (`net.IsPushModelEnabled=0` does NOT work — "PushModel HandleCreation is now enabled" regardless.)
NB: `LokiWorldSettings`'s actor channel fails on the client (no `/Script/Loki.LokiWorldSettings` class → graceful
drop), so WorldSettings never hydrates — and WorldSettings is **NOT** the client-crash culprit (confirmed).

## ★ THE KEYSTONE PROBLEM — the movement garbage-thread AV (this is THE wall to functional control)
Any **movement** (WASD, spam-clicking keys) or **deploy progression** crashes the CLIENT (the stub survives) with:
```
ExceptionCode=0xC0000005  ExceptionAddress=0x7FF8F0400001 / 0x7FF90E000001  params=['0x8', ...]
```
`0x8` = **EXECUTE violation** at an **unmapped address** with a garbage stack = the **S53/S54 garbage-thread
execute-AV**: a **half-hydrated replicated subsystem spins a STALE CALLBACK into a thread**, which immediately
execute-AVs. Different addresses (0x7FF8F04…, 0x7FF90E0…) = different half-hydrated things per match stage
(whack-a-mole). CONFIRMED **NOT** the feature-toggle wall (`CursorCharacterAim`/`AttachAudioListenerToHero` "not
ready" spam is a RED HERRING) and **NOT** WorldSettings.

**S53 proved this class of bug is FIXABLE**: it fixed one instance by **un-suppressing the half-hydrated replica
on the stub** so it hydrates (PlayerState). The current culprit is a DIFFERENT replica, engaged by movement/deploy,
still un-identified. **Solving this is the path to functional control** — the stub already possesses a LokiCharacter;
if movement stops crashing, control becomes reachable.

### How to attack it (concrete)
1. **Triage every crash via the minidump** (this is the reliable signal, not the log):
   `python tools/re/parse_minidump.py <newest .dmp>` where dumps land in
   `G:\git\GAME BACKUPS…\SUPERVIVE\Loki\.sentry-native\reports\*.dmp`. `0x8`+unmapped-execute = the garbage-thread AV.
2. **Identify the culprit replica.** The faulting thread's stack is garbage (fresh thread), so the SPAWNING thread
   has the info. Two routes:
   - **(A) In-process shim** (external RPM is BLOCKED in-match — see gotcha): hook the UE async/task dispatch or
     thread-creation path and log when a thread/callback with target `0x7FF…01` is enqueued, with the caller stack →
     names the subsystem. (Careful: the preloader anti-tamper also hooks `NtCreateThreadEx` — S53 said it's not the
     crash cause, but a naive re-hook may conflict; hook a higher UE layer.)
   - **(B) Systematic hydration** (S53's proven method, now UNBLOCKED by the mirror): the stub's
     `LokiNetDriver.cpp::IsClassNetCacheDivergent` still suppresses a set; un-suppress candidate SPAWNED replicas
     one at a time (single-variable), using the `ALokiWorldSettings` mirror pattern if a stock class hits the push
     assert. Test whether the movement crash moves/vanishes. The culprit is a SPAWNED replica (S53 pattern —
     WorldSettings was wrong precisely because it's a LEVEL actor), engaged on movement/deploy.
3. **Also reconcile the match-type discrepancy:** the loading screen says "BATTLE ROYALE: THE BREACH", but ags
   serves `forceTutorialMatch`. S70 (a week ago) LEFT the loading screen into the tutorial world; this session it
   stalls on the BREACH loading. Figure out why the client now enters a BREACH-flavored match vs the tutorial, and
   whether the S70 loading-screen clear (ALokiGameState `CurrentPhase`=EGP_SpawnSelect) still applies.

## Reusable assets (all work)
- **Stub un-suppress technique:** `ALokiWorldSettings` non-push mirror + `ULokiGameEngine::LoadMap` swap — copy this
  for any stock class that hits the push assert when un-suppressed.
- **Crash triage:** `tools/re/parse_minidump.py` (0x8+unmapped-execute = garbage-thread AV).
- **Fly-cam / reveal shim:** `tools/sigbypass-mod/ds_hybrid.cpp`, `kMode` = `MODE_FREECAM` (spawn `ACameraActor` +
  `SetViewTargetWithBlend` + `K2_SetActorLocation` puppet), `MODE_SPECTATOR_CAM` (hide the `WBP_UI_MatchTransition`
  loading overlay + velocity puppet), `MODE_DEBUGCAM` (EnableDebugCamera — BLOCKED: no CheatManager in shipping).
  Build: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS ds_hybrid.cpp -o ds_hybrid.dll -lkernel32 -luser32`.
  Inject: `tools/inject/inject.exe mmap <PID> ds_hybrid.dll`. Marker: `docs/ds-hybrid-marker.txt`. Reflection-based
  offset resolution (PropOffsetOnClass), heap-guarded writes. NOTE: the native dead-spectator camera OVERRIDES
  `SetViewTargetWithBlend` each frame (you get rotation-only, no translate) — to make a spawned camera stick you'd
  need to poke the PC's view target each tick or drive the camera POV; and movement still hits the garbage AV.

## ★ GOTCHAS (will waste hours if forgotten)
- **In-match anti-tamper blocks external RPM.** Python `ctypes` `OpenProcess`/`ReadProcessMemory` WORKS at the menu
  but returns null/fails once the match goes "real" (the preloader anti-tamper wakes up). `inject.exe`/`usmapdump`
  (C tools, SeDebugPrivilege) still work. **Drive/inspect via in-process shims + minidumps in-match, not external
  pokes.** (This is why config_ready_scan.py etc. fail mid-match.)
- **The toggle "not ready" spam is a RED HERRING** — the crash is the garbage-thread AV, always confirm via minidump.
- **Steam-relaunch pid confusion:** `& $exe` launches a handoff process that cleanly exits (RequestExit 0,
  HandleExitCommand) and Steam relaunches the REAL game under a different pid. Find the live pid via
  `Get-Process SUPERVIVE-Win64-Shipping` and its `StartTime`/uptime, not the launcher's return.
- **Kill `UnrealEditor-Cmd` before rebuilding the stub** (LNK1104). Rebuild is ~10-70s incremental.
- **ags DS config:** `server/internal/interactive/interactive.go` `ConnectionDetails.address` must be
  `"127.0.0.1:7777"` (working-tree value; the committed baseline is `""`). `forceTutorialMatch=true`.
- **Base `0x7FF6B54F0000` is stable across relaunches; heap VAs are per-launch.**

## Recipe (elevated PS, Steam UP first — else Auth Failure 14005)
1. Ensure ags `interactive.go` address = `"127.0.0.1:7777"`.
2. Build stub: `& "H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" LokiEditor Win64 Development
   -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WarningsAsErrors` (kill UnrealEditor-Cmd
   first). Start stub: `UnrealEditor-Cmd.exe …\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777
   -nullrhi -NoSplash -Unattended -abslog=<log>` → wait "listening on port 7777" (+ "swapped WorldSettings ->
   ALokiWorldSettings").
3. Client: `configs\launch-redirect.ps1 -NoHook` (rebuilds ags + certs + launches; returns early via Steam relaunch).
4. Poll client `Loki.log` for `Entering game state LokiGameState` + `LokiPlayerController_<n>`; poll stub log for
   `Join succeeded`. The stub should NOT crash (mirror). Then attack the movement garbage-thread AV.

## Honest framing
The DS route now delivers the client into the live match flow with a stable stub, a Loki PC/PlayerState/GameState,
a server-possessed LokiCharacter, and reaches the pre-drop screen — the furthest any route has gone. The single
wall to functional control is the **movement garbage-thread AV** (a half-hydrated replica). It's a KNOWN,
S53-FIXABLE class of bug (identify + hydrate the replica), but the culprit is un-identified and each attempt
crashes + needs a relaunch, so it's a focused multi-cycle grind — not a one-shot. Reasonable-effort ceiling banked
so far: the stable spectator-in-the-live-match-flow with a Loki PC + a server-possessed hero, one replica-fix
short of movement.
