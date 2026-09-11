# Next session (S66) — FINISH the playable tutorial: initialize ULokiGameFeatureToggles so the round drops in a hero

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (governs everything)

**Keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a
controllable hero drops in, and you can move/play it.** Multi-session is expected. "Done" = a hero you can
control. The gates behind us are NOT done — don't re-open them. Make concrete progress each session + hand off
cleanly. No stops until it's playable.

## WHERE WE ARE — the real tutorial gamemode now RUNS (S65 breakthrough). One subsystem gates the hero.

Read `docs/session-65-path1-hybrid.txt` first. Gate ladder:
- **[DONE] travel+load; Login (slot-285); PlayerState (InitPlayerState 260/273, Loki PC); WaitingForClientsReady.**
- **[DONE — S65] the post-"ready to play" REVERT.** Beaten by giving the client a COMPLETE, valid
  `CoreGameMatchModel` (S64 found the revert was init gracefully handling an *invalid* model). There's no
  factory UFunction to call, so we used the **HYBRID**: `ags` arms a match (`forceTutorialMatch=true` +
  empty `ConnectionDetails.address`), the client's OWN parser builds a complete valid model
  (`bIsValid=1, MatchState=5, MatchInfo` populated) and parks locally; then the force-open shim opens
  LVL_Tutorial. Result: `LogLokiGameModeInitializer` runs to **FINISHED** — no revert, no crash, real
  `BP_LokiGameMode_Tutorial` + `BP_LokiGameState_Tutorial_C` + `BP_LokiPlayerController_Dev_C`, 166 live
  hero/character actors present. Farthest the project has ever reached.
- **[NEXT — THE GATE] `ULokiGameFeatureToggles` never initializes.** After "Finished", `LogLokiRoundGameMode`
  stays at `EGP_BeginInit` (no drop-in, no possess), and every frame logs
  `LogTemp: Error: ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready`
  (X = DeadSpectatorCameraLock, CursorCharacterAim, AttachAudioListenerToHero, BonfireUAVs, WinterEvent, ...;
  45,000+ errors, ZERO "ready"). The player is in a **spectator camera** state; hero control/aim/camera — and
  very likely the round's advancement past BeginInit to drop-in — are gated OFF because this subsystem was
  never populated. It's normally set at proper match start (server-replicated and/or backend config); the
  force-open path bypasses that.

## S66 GOAL: make `ULokiGameFeatureToggles` "ready" (and populated), so the round advances to drop-in + hero

1. **Find what populates it.** `ULokiGameFeatureToggles` is a subsystem/singleton with a "ready" flag + a toggle
   map. Investigate the source (in this order of likelihood):
   - **Backend config**: check `GET /configuration/client` (S60 added it, serves `clientVersions`) and
     `/configuration/public` — does the client read feature toggles / feature flags from there? Trace the
     client-config → toggles path. If ags can serve a toggles payload, that's the cleanest fix (pure backend).
     Watch `docs/capture.log` for a config/feature-flag fetch; the client-config host is also redirected.
   - **Server replication**: in a real match the DS replicates the toggles. Our force-open has no server — so
     this may be why they're "not ready." If so, the toggles must be set locally (native/shim) or via backend.
   - **Native init**: a native call that loads/sets the toggles at match start.
2. **Set them via the runtime path (missions-style) if backend alone doesn't do it.** Use the in-shim probes:
   find the live `ULokiGameFeatureToggles` instance (walk GUObjectArray by class name — `DumpClassFuncs`/the
   object-walk helpers are in `tools/sigbypass-mod/tutorial_launch.cpp`), dump its props (a "bReady"/"bInitialized"
   bool + a toggle `TMap`/`TArray`), then set ready=true and populate the map. The ProcessInternal native-call
   primitive is available if a native/UFunction setter exists. (Mirror the S65 `DumpCoreGameState` approach:
   dump the class props/functions first, then poke/populate.)
3. **Verify progression:** with toggles ready, expect `LogLokiRoundGameMode` to advance past `EGP_BeginInit`,
   the drop-in (`Comp_GameMode_DropPlane_Tutorial` / `BP_DropPod_Tutorial`) to fire, and the PC to **Possess**
   a hero. Then confirm the hero is controllable (movement/camera/aim) = **PLAYABLE**.
   CAVEAT: if toggles-ready still doesn't advance the round, the round may need another match-start signal —
   investigate `LokiRoundGameMode`'s BeginInit→next-phase condition (in-shim runtime, since static RE is dead).

## THE WORKING CONFIG (keep it; this is what makes the tutorial run)
- **ags** (`server/internal/interactive/interactive.go`): `forceTutorialMatch=true` + `ConnectionDetails.address=""`
  (the hybrid). Build: `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`.
  Restart REUSES certs (no cacert re-append) — kill `ags`, start with:
  `-http :8080 -https :443 -log <repo>\docs\capture.log -certs <repo>\certs` (WorkingDirectory `<repo>\server`).
  NOTE: with the hybrid on, the client AUTO-enters the pre-game lobby at boot (~1min) — that's intended for the
  tutorial workflow (revert both knobs to false for normal menu use).
- **shim** `tools/sigbypass-mod/tutorial_launch.dll` = durable force-open build (`kFixMode=FIX_TARGETED_INITPS`
  = login slot-285 + PlayerState 260/273; `kInvestigateOnly=false`; `kPokeMatchModel=false`). Build:
  `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32` (clang at
  `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
  Probes: `DumpCoreGameState` (CoreGameManager + match model), `FindCoreGameManager`, `DumpClassFuncs` (class
  UFunctions), `DumpPawns` (hero census). Set `kInvestigateOnly=true` for a read-only census at the menu (no
  force-open) — the pattern to reuse for probing `ULokiGameFeatureToggles`.

## REPRODUCE (fully autonomous when shell is elevated)
1. Relaunch: elevated shell -> `.\configs\launch-redirect.ps1 -NoHook` (skips its own re-elevation when admin;
   run in background — it blocks on the game). Wait ~55s. (Steam must be up.) `ags` already has the hybrid baked in.
2. At the menu the client auto-arms the match (~1min) — verify the model is valid: inject the shim with
   `kInvestigateOnly=true` (read-only) and check `[MM0] bIsValid=1 MatchState=5 MatchInfo populated`.
3. Inject the shim with `kInvestigateOnly=false` -> force-opens LVL_Tutorial -> initializer Finishes; the game
   runs the tutorial (spectator until toggles are fixed). Read `Loki.log` (`Transitioning ... to Finished`, the
   `ULokiGameFeatureToggles ... not ready` spam) + `docs/tutorial-launch-marker.txt`.
   Inject: `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe tools\sigbypass-mod\tutorial_launch.dll`
   (rebuild inject.exe if missing: `go build -C tools/inject -o inject.exe .`).

## Key addresses / offsets (base `0x7FF6B54F0000`, stable; re-verify with `usmapdump info`)
- ProcessInternal hook rva `0x13454A0`; ExecuteConsoleCommand exec thunk rva `0x395D790`. GUObjectArray rva
  `0x9E38930`; NAMEPOOL rva `0x9D81450`. Obj: Class@+0x18, Name@+0x20. UStruct: SuperStruct@+0x40,
  Children(UField funcs)@+0x50, ChildProperties(FField)@+0x58. UField.Next(func)@+0x30; FField.Next@+0x18,
  Name@+0x20; FProperty Offset_Internal@+0x44. UFunction.Func@+0xE0.
- GameMode Login = C++ vtable SLOT 285 (stock `0x7FF6B8CD0C50`); match vtables Tutorial `0x8A94C48` etc.
- Loki PC vtable rva `0x8A1AEE0`; InitPlayerState slots 260/273. CoreGameManager.CoreGameMatchModel @0x6E0;
  model bIsValid@0x30 / MatchState@0x48 / MatchInfo@0xB0. .text range `0x1000`..`0x7649000`.

## Gotchas / DON'Ts
- Static string->code xref (`usmapdump xrefstr`) does NOT work on this packer (0 hits even for live code) — use
  in-shim RUNTIME probes (object-walk + reflection), the method that got every win.
- Keep the ags hybrid (forceTutorialMatch + empty address) — it's what builds the valid model. Don't set a
  non-empty address (client connects to a dead DS -> 20s timeout -> login bounce, model torn down).
- Keep vtable/.rdata patches transient/self-restoring (~3-5min integrity check covers .rdata).
- Computer-use on the game window is USER-DENIED — drive via inject + markers + logs (force-open needs no clicks).
- Don't re-open SOLVED gates (Login, PlayerState, the revert). Build on top.

## Live state at end of S65
Game left ALIVE running the tutorial (spectator, round stuck at BeginInit on the toggle gate). `ags` up with the
hybrid config. `tutorial_launch.dll` = durable force-open build. Preserved: scratchpad
`marker-s65-path1-success.txt`, `Loki-S65-path1-tutorial-runs.log`.
