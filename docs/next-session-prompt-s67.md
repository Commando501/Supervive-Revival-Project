# Next session (S67) — FINISH the playable tutorial: spawn + possess a controllable hero (beat the round-start gate)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (governs everything)

**Keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a
controllable hero drops in, and you can move/play it.** Multi-session is expected. "Done" = a hero you can
control. Don't re-open solved gates. Make concrete progress each session + hand off cleanly. No stops until playable.

## WHERE WE ARE — the tutorial fully loads + runs; ONE gate left: the player has no hero

Read `docs/session-66-round-start-gate.txt` then `docs/session-65-path1-hybrid.txt`. Gate ladder:
- **[DONE] travel+load; Login (slot-285); PlayerState (InitPlayerState 260/273, Loki PC); WaitingForClientsReady;
  the post-"ready" REVERT (S65 hybrid); gamemode initializer FINISHED; real BP_LokiGameMode_Tutorial +
  BP_LokiGameState_Tutorial_C + BP_LokiPlayerController_Dev_C; AI bots spawn.**
- **[NEXT — THE GATE] `LokiRoundGameMode` is stuck at `EGP_BeginInit`** and never advances, so the LOCAL
  player's drop-in / `RestartPlayer` never fires → **no possessed hero → the game runs as a dead spectator**
  (hence the per-frame `ULokiGameFeatureToggles::Get DeadSpectatorCameraLock ... not ready` spam — that spam is a
  SYMPTOM, not the gate; the feature-toggle store isn't even a UObject, and game-feature plugins load fine).
  A **valid hero IS served** (ags `selectedHero` → Ronin default in `PlayerInfo.HeroAssetID`) — the player just
  never gets one spawned.

## S67 GOAL: get the local player a controllable hero. Two leads — try LEAD B first.

**LEAD B (recommended) — force-spawn + possess the hero directly, bypassing the packer-hidden round logic.**
Use the proven ProcessInternal game-thread native-call primitive (the one that drove missions:
`docs/session-55/56/58-*`, `supervive-missions-page-status`) to spawn + possess a hero for the local PC:
- Best bet: **`SpawnDefaultPawnAtTransform(Controller, FTransform)`** on the tutorial gamemode (it's a UFunction —
  see the inventory) with the local PC + a hand-picked map transform (ChoosePlayerStart fails "NO PLAYERSTART"
  by design, so pass an explicit transform on the island), then **Possess** the returned pawn (call the PC's
  `Possess`/`K2_Possess`, or the gamemode path that possesses).
- Or **native `RestartPlayer(AController*)`** (AGameModeBase; spawns default pawn + possesses in one) — it's
  native (not in the BP list) so find its thunk; if reachable, it's the cleanest one-call spawn+possess.
- Find the local PC instance (the non-spectator `BP_LokiPlayerController_Dev_C`; DumpTutorialState/DumpPawns
  find PCs). The gamemode instance is found by DumpGameModeFuncs. Build the Controller/Transform params the
  missions way (each param at its FProperty Offset_Internal@+0x44; OUT param via FFrame.OutParms@+0x80).
- Verify: a hero pawn possessed by the PC, movable/aimable = **PLAYABLE**. (Feature-toggle "not ready" may still
  degrade some hero features — if control is broken after possession, revisit the toggle store then, not before.)

**LEAD A (fallback) — force the round to advance past `EGP_BeginInit`.** The phase advance is native
(`ALokiRoundGameMode`), server-authoritative, packer-hidden. Angles: find a native `SetPhase`/`SetRoundPhase`/
`AdvancePhase` (walk the gamemode's UFunctions incl. native; the round CDO/vtable) and call it to push
BeginInit → the deploy/drop phase so the normal drop-in fires; or determine what condition it waits on
(countdown / min-players / a match-start signal). Harder than LEAD B because it's native + packer-hidden.

## THE GAMEMODE FUNCTION INVENTORY (BP_LokiGameMode_Tutorial_C, from DumpGameModeFuncs — reusable)
`ModeSupportsDropPlane, SpawnBots, SpawnMonster, "Spawn AI Hero Bot", GetTeamIndexForPIEPlayer,
SpawnDefaultPawnAtTransform, SpawnDefaultPawnFor, ChoosePlayerStart, K2_OnRestartPlayer, ClearDelaySpawn,
ReceiveBeginPlay, SetPlayerStartName, BP_OnRoundRestart, BP_OnNewPhase, OnPlayerSpawned_BP, GrantStarterItems`.
(Use `kInvestigateOnly=true` + DumpGameModeFuncs to re-dump live; broaden the filter in DumpClassFuncs if needed.)

## THE WORKING CONFIG (keep it — this is what makes the tutorial load + run)
- **ags** hybrid (`server/internal/interactive/interactive.go`): `forceTutorialMatch=true` +
  `ConnectionDetails.address=""`. The idle client auto-fetches the match, its parser builds a COMPLETE valid
  `CoreGameMatchModel`, and it parks locally in the pre-game lobby. Build:
  `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`. Restart REUSES certs
  (no cacert re-append): kill `ags`, start with `-http :8080 -https :443 -log <repo>\docs\capture.log -certs
  <repo>\certs` (WorkingDirectory `<repo>\server`).
- **shim** `tools/sigbypass-mod/tutorial_launch.dll` = durable force-open build (`kFixMode=FIX_TARGETED_INITPS`
  = login slot-285 + PlayerState 260/273; `kInvestigateOnly=false`; `kPokeMatchModel=false`). It has the PI
  native-call primitive + probes: `DumpCoreGameState`, `FindCoreGameManager`, `DumpClassFuncs`, `DumpPawns`,
  `DumpFeatureToggles`, `DumpGameModeFuncs`. Build: `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll
  -lkernel32` (clang at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).

## REPRODUCE (fully autonomous when shell is elevated)
1. **Kill any prior game first** (`Stop-Process -Name SUPERVIVE-Win64-Shipping -Force`) — launch-redirect does NOT
   kill it, and two games pollute Loki.log. Then `.\configs\launch-redirect.ps1 -NoHook` (elevated shell; run in
   background — it blocks on the game). Wait ~55s. (Steam must be up.)
2. At the menu the client auto-arms the match (~1min). Optionally verify with a read-only census (rebuild shim
   `kInvestigateOnly=true`, inject): `[MM0] bIsValid=1 MatchState=5 MatchInfo populated`.
3. Force-open (shim `kInvestigateOnly=false`): `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe
   tools\sigbypass-mod\tutorial_launch.dll` (rebuild inject.exe if missing: `go build -C tools/inject -o inject.exe .`).
   The tutorial loads, initializer Finishes, round sits at BeginInit (spectator). Then do the LEAD-B spawn work
   (a 2nd inject running the native-call spawn+possess).
4. Read `docs/tutorial-launch-marker.txt` + `Loki.log` (`Setting Phase to 1 (BeginInit)`, no advance; Possess/
   RestartPlayer/OnPlayerSpawned once LEAD B fires).

## Key addresses / offsets (base `0x7FF6B54F0000`, stable; re-verify with `usmapdump info`)
- ProcessInternal hook rva `0x13454A0`; ExecuteConsoleCommand thunk rva `0x395D790`. GUObjectArray rva `0x9E38930`;
  NAMEPOOL rva `0x9D81450`. Obj: Class@+0x18, Name@+0x20, Outer@+0x28. UStruct: SuperStruct@+0x40, Children(UField
  funcs)@+0x50 (Next@+0x30), ChildProperties(FField)@+0x58 (Next@+0x18, Name@+0x20). FProperty Offset_Internal@+0x44.
  UFunction.Func@+0xE0. FFrame OutParms@+0x80.
- GameMode config: PlayerControllerClass@+0x3D8, PlayerStateClass@+0x3E0, DefaultPawnClass@+0x3F0.
- CoreGameManager.CoreGameMatchModel @0x6E0; model bIsValid@0x30 / MatchState@0x48 / MatchInfo@0xB0.
- Loki PC vtable rva `0x8A1AEE0`; InitPlayerState slots 260/273. .text range `0x1000`..`0x7649000`.

## Gotchas / DON'Ts
- Kill the prior SUPERVIVE process before relaunching (launch-redirect leaves it running → 2 games + polluted log).
- Static string→code xref (`usmapdump xrefstr`) does NOT work on this packer — use in-shim RUNTIME probes.
- Keep the ags hybrid on (forceTutorialMatch + empty address) — it builds the valid model. Non-empty address =
  DS connect → 20s timeout → login bounce.
- Keep vtable/.rdata patches transient/self-restoring (~3-5min integrity check).
- Computer-use on the game window is USER-DENIED — drive via inject + markers + logs (force-open needs no clicks).
- The feature-toggle "not ready" spam is a symptom of no-hero — don't chase it as the gate; get the hero spawned first.

## Live state at end of S66
Game left alive (spectator, round at BeginInit). `ags` up with the hybrid config. `tutorial_launch.dll` = durable
force-open build with all the new probes. Preserved: scratchpad `marker-s66-gamemode-funcs.txt`,
`marker-s65-path1-success.txt`, `Loki-S65-path1-tutorial-runs.log`.
