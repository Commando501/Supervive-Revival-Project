# Next session (S68) — FINISH the playable tutorial: spawn/possess a controllable hero via the native-call primitive

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (governs everything)

**Keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a
controllable hero drops in, and you can move/play it.** "Done" = a hero you can control. Don't re-open solved
gates. Make concrete progress each session + hand off cleanly. No stops until playable.

## WHERE WE ARE — everything is set up; the last step is spawn+possess a hero

Read `docs/session-67-spawn-possess-setup.txt` first. The force-open tutorial now RELIABLY loads + runs (S67
fixed the login-hold timing bug that caused the "intermittent" crashes). The real gate (S66) is that
`LokiRoundGameMode` never leaves `EGP_BeginInit`, so the local player's drop-in never fires → dead spectator.
**LEAD B** (force-spawn+possess the hero directly, bypassing the packer-hidden round logic) is fully set up and
**confirmed callable** — S68 just has to build the call.

Two S67 fixes you inherit (both important):
- **Login-hold fix:** the slot-285 CustomLogin is held until Login actually fires (`open` is deferred, Login runs
  ~7s later). Force-open now reliably passes login + the tutorial STAYS alive (spectator).
- **SuperStruct offset fix:** `UStruct::SuperStruct` is `@+0x48` this build (was wrongly 0x40). All super-walks
  are fixed, so probes now resolve inherited funcs/props (that's how `Possess` + `PlayerState` were finally found).

## S68 GOAL: get the local player a controllable hero. Build the native call. Try OPTION 1 first.

The ProcessInternal primitive already calls a UFunction on the game thread (`OnPI` does it for
`ExecuteConsoleCommand`). Adapt it to call `Possess` (and optionally `SpawnDefaultPawn*`) with a params buffer.

**OPTION 1 (simplest — possess an EXISTING hero). Try first.**
The tutorial already spawns hero pawns (AI bots — ~166 live `LokiCharacter` actors). Find a live hero PAWN
(class contains "Hero" / is a `LokiCharacter` pawn, NOT a "*Component"/"Comp_*"), then call
`Controller::Possess(Context = local PC, InPawn @0x0 = that pawn)` on the game thread via the primitive. If the
player then controls that hero → **PLAYABLE** (even if it started as a "bot" hero). One native call — lowest risk.
- Find the local PC: non-Default `BP_LokiPlayerController_Dev_C` instance (DumpPCFuncs/DumpPawns find PCs).
- Resolve `Possess`: it's on `AController` (a super of the PC) — walk the PC class's super chain (FIXED @+0x48)
  and find the `Possess` UFunction (thunk @+0xE0, ChildProperties @+0x58 for params; `InPawn` is param 0 @0x0).

**OPTION 2 (spawn a fresh hero, then possess).**
Call on the gamemode instance (found by DumpGameModeFuncs):
- `SpawnDefaultPawnFor(NewPlayer @0x0 = PC, StartSpot @0x8 = <a live map actor: CapturePoint/RespawnBeacon/bot>)`
  → `ReturnValue @0x10` = pawn. (Easiest — StartSpot is just an actor pointer; find one on the island.)
- OR `SpawnDefaultPawnAtTransform(NewPlayer @0x0 = PC, SpawnTransform @0x10 = <FTransform>)` → `ReturnValue @0x70`.
  FTransform is LWC doubles: FQuat(4d) + FVector translation(3d) + FVector scale(3d); reuse a live actor's
  transform or use SpawnDefaultPawnFor to avoid building it.
Then `Controller::Possess(PC, pawn)`.

**Primitive recipe** (proven — missions s55/56/58): build a params buffer, place each param at its FProperty
`Offset_Internal @+0x44`; OUT/ReturnValue via `FFrame.OutParms @+0x80`; frame `Node`=UFunction, `Object`=Context,
`Code`=NULL, `Locals`=buf, `PropertyChainForCompiledIn @+0x88` = Function.ChildProperties; call the thunk
`(UFunction.Func @+0xE0)(Context, &frame, &result)`. Run it on the GAME THREAD from the ProcessInternal hook (same
as `OnPI` does for the force-open). `CallNative` in the shim already does the frame build.
**Verify:** PC->Pawn set, the per-frame `DeadSpectatorCameraLock ... not ready` spam STOPS, hero is movable.

## THE WORKING CONFIG (keep it)
- **ags** hybrid (`server/internal/interactive/interactive.go`): `forceTutorialMatch=true` + `ConnectionDetails.
  address=""` — builds a valid `CoreGameMatchModel` at idle + parks locally. Build/restart reuses certs.
- **shim** `tools/sigbypass-mod/tutorial_launch.dll` = durable force-open build with BOTH S67 fixes + probes
  (`DumpCoreGameState`, `FindCoreGameManager`, `DumpClassFuncs`, `DumpParams`, `DumpPawns`, `DumpFeatureToggles`,
  `DumpGameModeFuncs`, `DumpPCFuncs`). `kFixMode=FIX_TARGETED_INITPS`; `kInvestigateOnly=false` (force-open) /
  `=true` (read-only census). Build: `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32`.

## REPRODUCE (autonomous when shell is elevated)
1. **Kill any prior game** (`Stop-Process -Name SUPERVIVE-Win64-Shipping -Force`) — launch-redirect doesn't.
   Then `.\configs\launch-redirect.ps1 -NoHook` (background). Wait ~55s.
2. Client auto-arms the match (~1min → pre-game lobby; the model is valid).
3. Force-open (shim kInvestigateOnly=false): `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe
   tools\sigbypass-mod\tutorial_launch.dll` (rebuild inject.exe if missing: `go build -C tools/inject -o inject.exe .`).
   Tutorial loads + STAYS (login-hold fix). Then do the spawn/possess (a 2nd inject with the OPTION-1 call).
4. Read `Loki.log` + `docs/tutorial-launch-marker.txt`.

## Key addresses / offsets (base `0x7FF6B54F0000`; re-verify with `usmapdump info`)
- ProcessInternal hook rva `0x13454A0`. GUObjectArray rva `0x9E38930`; NAMEPOOL rva `0x9D81450`.
- Obj: Class@+0x18, Name@+0x20, Outer@+0x28. **UStruct: SuperStruct@+0x48 (FIXED)**, Children(UField funcs)@+0x50
  (Next@+0x30), ChildProperties(FField)@+0x58 (Next@+0x18, Name@+0x20). FProperty Offset_Internal@+0x44.
  UFunction.Func@+0xE0. FFrame OutParms@+0x80, PropertyChainForCompiledIn@+0x88.
- GameMode Login = C++ vtable slot 285. Loki PC InitPlayerState slots 260/273. GameMode config
  PlayerControllerClass@+0x3D8, DefaultPawnClass@+0x3F0. CoreGameManager.CoreGameMatchModel@+0x6E0.
- Callable (confirmed live): gamemode `SpawnDefaultPawnFor`(NewPlayer@0x0,StartSpot@0x8→ret@0x10) /
  `SpawnDefaultPawnAtTransform`(NewPlayer@0x0,SpawnTransform@0x10→ret@0x70); PC `Controller::Possess`(InPawn@0x0).

## Gotchas / DON'Ts
- Kill the prior SUPERVIVE process before relaunching (launch-redirect leaves it → 2 games + polluted Loki.log).
- The force-open login patch must stay installed until Login fires (~7s after `open`) — the S67 hold does this; don't
  shorten it.
- Static string→code xref (`usmapdump xrefstr`) does NOT work on this packer — use in-shim RUNTIME probes.
- Keep the ags hybrid on (forceTutorialMatch + empty address). Keep vtable/.rdata patches transient.
- Computer-use on the game window is USER-DENIED — drive via inject + markers + logs.

## Live state at end of S67
Game left alive (pid varies; spectator in the tutorial, round at BeginInit). `ags` up with the hybrid config.
`tutorial_launch.dll` = durable force-open build with both fixes + all probes. Preserved: scratchpad
`marker-s67-survey.txt`.
