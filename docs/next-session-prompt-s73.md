# Next session — SUPERVIVE playable tutorial: the DS route hit its ceiling; decide the content-overlay route (or pivot)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (unchanged, honest)
Get the SUPERVIVE tutorial FULLY PLAYABLE: map loads, a controllable hero drops in, you can move/play it. Multi-session.
BUT read the "WHERE WE ARE" section before doing anything — the two obvious routes (client-side force-open, and the
dedicated-server + shim hybrid) are now BOTH exhausted, and the only remaining path is large and uncertain. Your first
job is to internalize that and either commit to the remaining route with eyes open, or help the user decide to bank the
milestone. Do NOT re-grind the closed routes.

## WHERE WE ARE (read these first, in order)
1. `memory/supervive-dedicated-server-status.md` — the full DS-route history (S53→S72), including the S72 dead-end.
2. `memory/supervive-tutorial-launch-status.md` — the force-open route (S60→S68) and its ceiling.
3. `docs/session-70-gamestate-loadingscreen-cleared.txt` — ★ THE MILESTONE.
4. `docs/session-71-pawn-replication-possession-wall.txt` + `docs/session-72-hybrid-shim-foundation.txt` — the walls +
   the definitive dead-end reasoning.

### The milestone that IS achieved (S70)
The dedicated-server route puts the client into the **LIVE tutorial world with a valid replicated `LokiGameState`**:
menu → client connects to the stub (127.0.0.1:7777) → travels to `LVL_Tutorial` → Join → the stub replicates a native
`ALokiGameState` mirror (schema-injected, `unreal-stub/Source/Loki/LokiGameStateStub.{h,cpp}`) → the client accepts it,
enters its own `LokiGameState`, runs `BeginPlay`, primes the gameplay actor pools, and sits **stable as a spectator in
the live tutorial world**. The loading-screen wall that blocked this for many sessions is GONE. This is the
reasonable-effort ceiling and a real, demonstrable result.

### Why a CONTROLLABLE HERO is a dead end via shims/injection (S71+S72 — do NOT re-attempt these)
Four independent hard walls, each confirmed LIVE:
1. **Spawn**: client-side actor spawn via the native-call primitive `__fastfail`-crashes for even a stock pawn
   (GameplayStatics `BeginDeferredActorSpawnFromClass` `const FTransform&` struct-param ABI — unsolved across S68+S72).
2. **Possess**: `ClientRestart` via the primitive is the exec wrapper (routes through ProcessEvent, a no-op for native),
   not the C++ `_Implementation`.
3. **Controller**: even a working possess on the STOCK networked PC won't drive a hero — SUPERVIVE's own code logs
   "TryGetLocalLokiController null"; it needs a LOKI PlayerController, which the stub can't provide (S41 RPC-sig wall).
4. **Drop-in**: server-authoritative + gamemode-driven (`Comp_GameMode_DropPlane_Tutorial`); neither route runs the real
   `BP_LokiGameMode_Tutorial` (BP content the stub can't run).

## THE ONLY REMAINING ROUTE — run the real BP_LokiGameMode_Tutorial server-side (content overlay)
A controllable hero needs SUPERVIVE's real match machinery (gamemode + Loki PC + hero + drop-in) running
authoritatively. The stub can't reproduce it by hand (walls above). The one path that could work: **get the game's
Blueprint content (the `/Game/Loki/...` cooked assets: `BP_LokiGameMode_Tutorial_C`, `BP_LokiPlayerController_*`, the
hero pawns, `Comp_GameMode_DropPlane_Tutorial`) loaded into the dedicated-server stub**, so the server runs the actual
tutorial gamemode and the existing S70 replication carries the real state to the client.

### KNOWN, LOAD-BEARING findings before you touch this (don't rediscover)
- `docs/trackb-assetregistry-route.md` — loose-file AR.bin deployment is **INERT** in this IoStore build (UE ignores
  the loose file even when valid). Deployment requires an **IoStore mod-pak overlay** — non-trivial.
- `docs/findings.md` + `docs/r2-findings.md` — IoStore catalog + usmap RE; the non-standard UObjectBase layout
  (nameOff=0x20, classOff=0x18). `docs/game-map.md` — the 68,228-asset catalog.
- The stub is a SEPARATE minimal UE5.4 project (`unreal-stub/`); it does NOT have the game's cooked content. Making it
  load `/Game/Loki/...` assets is the crux (mount the game's paks/IoStore into the stub, or build a mod-pak the stub
  mounts). This is a large IoStore/cooking effort and has been repeatedly deferred as non-trivial.

### First moves for the content-overlay route (scoping, cheap first)
1. **Feasibility spike, not a build**: can the stub (UnrealEditor-Cmd, editor build) MOUNT the shipping client's
   `Loki/Content/Paks/*.utoc/.pak` at startup and resolve `/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.
   BP_LokiGameMode_Tutorial_C`? Try `FCoreDelegates::OnMountPak` / `IPluginManager` / a `-pak` mount in
   `ULokiGameInstance::Init`, then `StaticLoadObject` the gamemode class and log success/fail. If it resolves, this
   route is alive; if IoStore signing/encryption or the missing `.uexp`/name-map blocks it, that's the wall to assess.
2. If it mounts: set the stub's `LVL_Tutorial` travel to use the REAL `BP_LokiGameMode_Tutorial` (not `LokiStubGameMode`)
   and see how far Login/round-init gets server-side (the S53 class-net-cache suppression + S70 GameState mirror are the
   scaffolding; the real gamemode replacing the stub gamemode is the change).
3. Honest gate: the shipping paks may be signed/encrypted such that an editor build won't mount them; if so, the overlay
   route may itself be blocked, in which case a PLAYABLE tutorial is likely not achievable with the current toolchain —
   report that plainly so the user can decide to bank the S70 spectator milestone as the final result.

## CONFIG / STATE (as left after S72 cleanup)
- `ags` (`server/internal/interactive/interactive.go`): `buildTutorialMatchInfo` `ConnectionDetails.address =
  "127.0.0.1:7777"` (DS route), `forceTutorialMatch=true`. Rebuild: `go build -C server -o ags.exe ./cmd/ags` (NOTE:
  the CLAUDE.md `-o server\ags.exe` form is WRONG by hand — it writes server\SERVER\ags.exe; use `-o ags.exe`).
- Stub (`unreal-stub/`, branch `dedicated-server-stub`): `ALokiGameState` mirror + un-suppressed GameState (S70), a
  DefaultPawn spawn+possess in `LokiStubGameMode::PostLogin` (S71), `ModifyClientTravelLevelURL → LVL_Tutorial`,
  `GameStateClass = ALokiGameState`, `net.IsPushModelEnabled=0` attempted in `Config/DefaultEngine.ini` (did NOT take).
- Nothing is running (S72 cleanup killed stub + ags). The hosts-file + cacert redirect is STILL in place (not reverted —
  don't run `launch-redirect.ps1 -Revert` unless the user asks).

## RECIPE (elevated PS; Steam running; stub FIRST — unchanged from S70)
1. Build stub (~240s; kill `UnrealEditor-Cmd` first — LNK1104): `Build.bat LokiEditor Win64 Development
   -Project=<abs>\unreal-stub\Loki.uproject -WaitMutex`.
2. Run stub: `UnrealEditor-Cmd.exe <abs>\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=<repo>\docs\ds-server.log` (poll for "IpNetDriver listening on port 7777"; do NOT
   `Remove-Item` the abslog path — a sandbox guard blocks it, UE truncates on open anyway).
3. Client: `.\configs\launch-redirect.ps1 -NoHook` (background; the shipping exe's `& $exe` returns early via Steam
   relaunch, so the launcher "task" completes while the game runs on). Auto-arms the match ~1 min.
4. Verify S70 baseline: client `Loki.log` (`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`) →
   "Entering game state LokiGameState" + "[ALokiGameState::BeginPlay]" + actor-pool priming = client in the live world.

## REUSABLE ASSETS (built across S69–S72)
- Live RPM tooling: `tools/re/find_uclass.py` (UClass by object name), `tools/re/obj_by_class.py` (live instances by
  class substring, takes the ASLR base arg), `tools/re/rep_expand_class.py`/`rep_expand.py` (client rep layout).
- The schema-injection PATTERN (S41/S54/S70): mirror a native class by path `/Script/Loki.<Name>`; DON'T call an engine
  base's GetLifetimeReplicatedProps in this runtime-ClassReps-rebuild stub — register base props BY NAME non-push;
  strip stock props the client doesn't replicate (`Loki.cpp StripReplicatedFlag`); verify with the boot
  `DumpClassNetCacheLayout` BEFORE launching.
- `tools/sigbypass-mod/ds_hybrid.cpp` — the native-call PRIMITIVE + census PROVEN to work in the DS-networked client
  (census/possess/spawn modes). Reusable if any client-side driving is ever needed again (but note S72's 4 walls).

## HONEST FRAMING FOR THE USER
The DS route achieved a genuine milestone (client in the live tutorial world, S70). A controllable hero via
shims/injection is a confirmed dead end (S72). The content-overlay route is the only remaining path and is large +
possibly blocked by IoStore signing/encryption. Recommended first action: the cheap feasibility spike (can the stub
mount the shipping paks + resolve the tutorial gamemode class?). If that's blocked, a playable tutorial is likely not
reachable with the current toolchain, and the S70 spectator view is the honest ceiling — surface that clearly rather
than grinding.
