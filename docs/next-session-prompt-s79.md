# Next session (S79) — DS route: make the FIRST TUTORIAL MISSION playable (hero spawns + objectives trigger in order)

## The goal (new focus)
Get the **first tutorial mission actually working**: the player's **hero spawns in and is controllable**, and the
**mission's objectives trigger in the correct order** (the full objective/trigger chain, start to finish). We've
banked a stable spectator fly-cam in the live tutorial world (S70–S78); now push to an actually-PLAYABLE tutorial.

## Before doing anything, READ (don't re-derive — ~40 sessions of walls are already mapped)
- Memory `supervive-dedicated-server-status` (the DS route, S53→S78 — the whole arc).
- Memory `supervive-tutorial-launch-status` (the client-side force-open route + its ceiling).
- Memory `supervive-cheat-surface-inventory` + `docs/session-74-cheat-enum-dump.txt` (★ the game-native SPAWN
  primitives — this is the most promising unlock; see below).
- `docs/session-73-lokipc-mirror.txt` (the Loki-PC mirror — the client's local PC is now a real
  LokiPlayerController; the S72 "needs a Loki controller" wall is DOWN).
- `docs/session-78-vtable-hook-and-rotation-wall.md` (★ the NEW durable vtable-hook game-thread-exec primitive).
- `docs/session-72-hybrid-shim-foundation.txt` (the 4 hero-control walls — several are now down; see below).

## What is DE-RISKED / working now (the foundation to build on)
1. **The client reaches the LIVE tutorial world** with a valid replicated `ALokiGameState` in a playing phase
   (S70) — stable 2+ min, leaves the loading screen, primes gameplay actor pools. The DS route gives the client a
   real networked session (unlike the force-open route).
2. **The client's LOCAL PC is a real `LokiPlayerController`** (S73 by-path mirror) → `TryGetLocalLokiController`
   succeeds (this was THE S72/S72-phase-3 wall #3). So SUPERVIVE's gameplay code will accept the local controller.
3. **The game-thread native-call primitive** (S55–58): hook `ProcessInternal` (`base+0x13454A0`), capture a live
   FFrame, call a UFunction's native thunk (`+0xE0`) DIRECTLY (no ProcessEvent guards) — params + OUT-params
   (`FFrame.OutParms@+0x80`) + struct params (S74 `BuildOutParms`) all solved. In `tools/sigbypass-mod/ds_hybrid.cpp`.
4. ★ **NEW (S78): the DURABLE VTABLE HOOK** — per-frame game-thread execution with NO `.text` patch and NO
   thread-suspend (swap a per-frame-ticked object's vtable POINTER `obj@+0` to a heap copy whose slot is our stub).
   It dodges the `.text`-integrity anti-tamper (heap-only) and runs reliably every frame — far better than the
   ProcessInternal-sparsity-limited transient hook. `FindPerFrameSlot`/`InstallVtableMove`/`OnVtableTick` in
   ds_hybrid.cpp. This is a big new capability for driving native calls reliably in-match.
5. **Client-side actor SPAWN via `GameplayStatics::BeginDeferredActorSpawnFromClass` + `FinishSpawningActor`
   WORKS** now (S78 spawned an `ACameraActor` cleanly, no crash). The S72 "spawn crashes" wall was the const-
   FTransform& struct-param ABI, FIXED by the S74 `BuildOutParms`. So manual client-side spawn is no longer a wall.
6. **Anti-tamper is understood + dodged**: `preloader.dll` + the packed-exe `.text` integrity check (NOT a
   commercial AC). NEVER hold a standing `.text` hook (it gets caught — reliably by late-game). Use the transient
   overlay-hide + the vtable hook (both proven crash-free in S78).

## The "hard wall" — REFRAMED as a RECONSTRUCTION task (not a permanent block)
- The real `BP_LokiGameMode_Tutorial` can't run as-is — its native parent (ALokiTutorialGameMode → RoundGameMode →
  GameMode) needs SUPERVIVE's dedicated-server binary + `ULokiServerPlatformInstance` + native round orchestration,
  which only a server-target build has (we have the client only — S73; force-open stalled at `EGP_BeginInit`, S65).
- ★ **BUT this is a REVERSE-ENGINEER-or-REBUILD task, not a dead end.** The round/mission/spawn/drop-in logic lives
  in the shipping exe's `/Script/Loki` native code — we can RE it from the (about-to-be-near-complete) image dump
  and either (a) hand-build the minimal native pieces in the stub (`unreal-stub/`, the way we mirrored GameState /
  PlayerController / WorldSettings), (b) drive the needed subset client-side via the native-call primitive / vtable
  hook, or (c) figure out the smallest set of triggers that starts the round + spawns the hero + advances objectives.
  The key enabler is the near-complete dump below — with the gameplay `.text` decoded, the round/mission machinery
  becomes readable and reconstructable. Don't treat "no server binary" as final; treat it as "reconstruct it."
- The S72 hybrid concluded 4 walls for a client-driven hero: (1) SPAWN — **now DOWN** (S78, BuildOutParms);
  (2) POSSESS via ClientRestart — the exec wrapper no-ops for native (call the C++ `_Implementation`, or use the
  cheat path); (3) CONTROLLER — **now DOWN** (S73 Loki-PC mirror); (4) DROP-IN — gamemode-driven (the open one).

## ★ RECOMMENDED STRATEGY (the most promising path, in order)
**Step 0 — RECREATE the image dump for near-100% `.text` (the RE foundation; DO THIS FIRST).** The dump tools were
updated (dumpimage now writes the `.exports.txt` sidecar; `mergedumps` + `reconstructiat` are built) but the dump
has NOT been re-run with them — the current `/dumps/` are stale (menu-only ~50% `.text`, not reconstructable). The
demand-decrypt gap was always the GAMEPLAY code that never runs at menu — and the DS route now gets the client into
the LIVE tutorial world, so that code finally executes and becomes dumpable. WORKFLOW (one launch = one ASLR base, so
dump all states within a single run): `usmapdump.exe dumpimage SUPERVIVE-Win64-Shipping.exe dumps/login` at login →
`.../dumps/menu` at the menu → `.../dumps/inmatch` IN THE LIVE TUTORIAL WORLD (drive as much gameplay/gamemode/round/
mission/spawn code as possible first — richer state = more `.text`); then `usmapdump.exe mergedumps
dumps/merged.dump.exe dumps` + `usmapdump.exe reconstructiat dumps/merged.dump.exe`. usmapdump is C/SeDebugPrivilege
RPM so it WORKS in-match (the anti-tamper only blocks external ctypes RPM). Load the resulting `*.iat.exe` in Ghidra/
IDA. This near-complete, symbol-friendly dump is what makes RE'ing the tutorial gamemode + round-orchestration +
mission-objective + hero-spawn logic tractable (the reconstruction task above). Memory: `supervive-image-dump-status`.

**Step 1 — spawn a CONTROLLABLE hero via the game's OWN cheat primitives (the biggest quick unlock; identified S74,
not yet attempted).** `ULokiPlayerCheats` (65 fns, live-enumerated `tools/re/cheat_enum.py` →
`docs/session-74-cheat-enum-dump.txt`) has game-native spawn/assign primitives:
`ServerCheatChangeHero(TSubclassOf<...>)`, `CheatChangeHero(FString name)`, `ServerCheatSpawnActor(Class, FVector)`,
`ServerTeleportLocation`, `CheatSetXP`, plus static entry `GetLocalLokiPlayerCheatsBP`. Calling their native thunks
DIRECTLY in-process (via the primitive) runs the `_Implementation` with LOCAL authority — this is the game's real
hero-spawn machinery, routing AROUND the manual spawn+possess walls. Because the local PC is now a real Loki PC
(S73), the spawned/assigned hero should actually engage control. This is the #1 thing to try. Use the NEW vtable
hook (S78) for reliable per-frame game-thread exec, or a transient PI hook for one-shot calls. Resolve the cheat
manager on the local PC (`GetLocalLokiPlayerCheatsBP` or PC->CheatManager / a LokiPlayerCheats instance) then call
`CheatChangeHero("<hero>")` / `ServerCheatChangeHero(<BP_HERO class>)`.
**Step 2 — get control + movement round-tripping.** If the hero spawns but doesn't move, the Loki-PC net-cache
reconstruction (S73: add LokiPlayerController's 60 own net UFUNCTIONs + 1 rep prop as SAME-NAMED stubs so the
FClassNetCache index space aligns — the possession/ServerMove RPCs currently misread) is the scoped fix. Live-RE
the RPC set with `tools/re/netfields_dump.py` (UFunction.FunctionFlags @+0xB8, FUNC_Net=0x40).
**Step 3 — the mission/objective trigger flow.** Once a hero is playable in the world, RE how the FIRST tutorial
mission drives its objectives (the objective state machine + trigger order). Determine whether the objectives are
(a) gameplay-event-driven (fire from player actions once the hero + world sim run), (b) drivable via the cheat/
progression surface, or (c) hard-gated on the missing server gamemode. The mission-PAGE replication (S54,
FMissionProgress) is SEPARATE from in-match tutorial objectives — don't conflate them. Look at
`docs/session-59-progress-bars.txt` / `docs/missions-progression-hookup.md` for the mission model, and the
tutorial map's objective actors (`LVL_Tutorial`, `Comp_GameMode_DropPlane_Tutorial` per S72).

## Recipe to reach the live tutorial world (elevated PS, Steam UP first — else Auth Failure 14005)
1. `ags` `server/internal/interactive/interactive.go`: `ConnectionDetails.address="127.0.0.1:7777"`,
   `forceTutorialMatch=true` (already on disk).
2. Build stub (KILL `UnrealEditor-Cmd` first — LNK1104): `Build.bat LokiEditor Win64 Development
   -Project="…\unreal-stub\Loki.uproject"`; run `UnrealEditor-Cmd.exe "…\Loki.uproject" /Engine/Maps/Entry?listen
   -game -server -Port=7777 -nullrhi -NoSplash -Unattended -abslog=<log>` → wait "listening on port 7777" +
   "swapped WorldSettings → ALokiWorldSettings".
3. Client: `configs\launch-redirect.ps1 -NoHook` (rebuilds ags+certs, Steam-relaunches; find the live pid via
   `Get-Process SUPERVIVE-Win64-Shipping`).
4. At client up ≥35s, inject the shim: `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid.dll`.
   Build the shim: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS ds_hybrid.cpp -o ds_hybrid.dll -lkernel32 -luser32`.

## Gotchas (reconfirmed S78)
- NEVER hold a standing `.text` hook (anti-tamper catches it, reliably by late session) — use the transient
  overlay-hide + the vtable hook.
- In-match anti-tamper blocks EXTERNAL ctypes RPM — drive/inspect via the IN-PROCESS shim + `docs/ds-hybrid-marker.txt`.
  `inject.exe`/`usmapdump` (C, SeDebugPrivilege) still work. Defender flags `tools\inject\inject.exe` (PUP) — needs
  a Defender folder exclusion; rebuild with `go build -o inject.exe .`.
- `GetCameraRotation`/`FindInstClassSub("CameraManager")` resolution VARIES per launch (which instance) — resolve by
  class/reflection, never hardcode a per-launch VA; base is ASLR'd.
- Live testing needs the user's elevated PowerShell + Steam running + the user driving in-game.
- The S78 fly-cam (spectator) is banked/committed (10183d9); its rotation is fast-native (a documented wall) — that's
  a SEPARATE issue from this tutorial goal; ignore it here.
