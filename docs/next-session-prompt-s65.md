# Next session (S65) — beat the post-"ready to play" revert: flow-manager match-model (PATH 1) or the DS route (PATH 2)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (governs everything)

**Keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a
controllable hero drops in, and you can move/play it.** Multi-session is expected. "Done" = a hero you can
control. The gates already behind us (travel, Login, PlayerState, WaitingForClientsReady) are NOT done — do
not re-open them. Each session make concrete forward progress + hand off cleanly. No stops until it's playable.

## READ FIRST (don't re-derive — it's logged)
1. `docs/session-64-server-orchestration.txt` — the current frontier, hypotheses ruled out, the strategic fork.
2. `docs/session-63-playerstate-fix.txt` — how login + PlayerState were solved (the fixes are baked into the shim).
3. Memory `memory/supervive-tutorial-launch-status.md` (S63 + S64 blocks = the live frontier).
   Also `supervive-dedicated-server-status.md` (the DS route) + `supervive-missions-page-status.md` (the
   ProcessInternal native-call primitive — the tool for PATH 1).

## WHERE WE ARE — one wall left before the match runs

Force-open of `BP_LokiGameMode_Tutorial` now clears travel + Login + PlayerState + WaitingForClientsReady (the
Loki PC logs `Client is ready to play`). Then, ~200-300ms later and SILENTLY, it does a **raw `UEngine::Browse`
back to `LVL_LobbyV2`** (the lobby) with `LogLokiGameMode: Error: failed to get ULokiServerPlatformInstance`.
- It's a RAW Browse (NOT ClientTravel/ReturnToMainMenu/TravelFailure — none log) => the **client-side front-end
  FLOW MANAGER** browsing home, most likely because the client has **no valid match context**
  (`CoreGameManager.CoreGameMatchModel` is null — we bypassed the menu match flow).
- It's Loki-PC-specific: a stock PC (S63 A2) never reports ready and just parks at WaitingForClientsReady.
- RULED OUT (S63/S64): backend-driven (client never polled `/core-game` in-match), `?listen`/net-context
  (failed to Listen, reverted identically), feature-toggles-not-ready (incidental, present without causing revert).
- **STATIC RE IS DEAD on this packer** (calibrated): `usmapdump xrefstr` finds 0 refs even for a live,
  currently-running menu-UI string. Do NOT try to locate `UEngine::Browse` / the revert code via string xref.
  All progress must be RUNTIME (in-shim during travel via the ProcessInternal primitive) or behavioral.

## THE FORK — pick a path (recommend starting with PATH 1's determination step)

**PATH 1 — build a COMPLETE, consistent CoreGameMatchModel (runtime state, missions-style). Try first.**
S64 already did the determination (via the in-shim DumpCoreGameState probe — kept in the shim). RESULT:
- The live `CoreGameManager` PERSISTS from the menu; its `CoreGameMatchModel @0x6E0` is **NON-NULL** during the
  tutorial (so it's NOT a missing-model problem). The model is **INVALID**: `bIsValid @0x30 = 0`,
  `MatchState @0x48 = 0` (PreHeroSelect), `MatchInfo @0xB0 = null` (SelfModel@0x60 / TeamMembers@0x68 non-null;
  TeamSize@0x78 = 1). => the revert is the tutorial-init GRACEFULLY handling "match model invalid -> browse to lobby."
- POKE test (S64): a tight loop forcing `bIsValid=1` (with or without `MatchState=5`) CRASHED init ~2s after
  world-up, BEFORE "ready to play" — init takes the "valid match -> proceed" branch and derefs the INCOMPLETE
  model (null MatchInfo). So **a byte-poke won't work**; the model must be COMPLETE and consistent.
So the task: construct/populate a FULL valid `CoreGameMatchModel` and its `MatchInfo` (19 props: ID/Version/
Created/GameConfig/State/StateEnum/GameVersion/PlayerInfo/QueueID/Region/ConnectionDetails/TeamInfo/HeroSelect*
Seconds/ChampionTeamDetails/OwnerID/CustomGameDetails — shapes in `docs/session-62-coregame-match-shape.txt`),
plus whatever else the "proceed" branch reads, then set bIsValid=true + MatchState=InProgress(5). Use the
ProcessInternal native-call primitive to construct/populate (the missions recipe that built + swapped
MissionsModel — `docs/session-55/56/57/58` + `supervive-missions-page-status`). Model offsets recovered:
CoreGameManager.CoreGameMatchModel @0x6E0; bIsValid @0x30; MatchState @0x48; SelfModel @0x60; TeamMembers @0x68;
TeamSize @0x78; ChampionTeamDetails @0x80; MatchInfo @0xB0. Tooling: the shim's `DumpCoreGameState` dumps the
model live; `FindCoreGameManager` caches the manager; `PokeMatchModelLoop` (DISABLED, kPokeMatchModel=false —
crashes) shows how to write the model. Timing is NOT the issue (the model persists; populate it before/around
travel), consistency IS.
- **CAVEAT (why PATH 1 may not be the end):** even past the revert, the gamemode logs "failed to get
  ULokiServerPlatformInstance" (server-side). PATH 1 may beat the revert but then stall on the server platform
  for the actual drop-in/bots. If a fully-valid model still can't run the match, pivot to PATH 2. The two
  converge on "the tutorial wants a server."

**PATH 2 — the DEDICATED-SERVER route (heavier, but may be the only route that truly runs the tutorial).**
`ULokiServerPlatformInstance` is a SERVER-side singleton; a client-only force-open can't have it. A real DS HAS
it and runs the server-authoritative match-advance; the client connects + plays. S62 PROVED the MENU route
delivers the client to a real UE NetConnection at 127.0.0.1:7777 cleanly (no force-open, no native patches).
Blockers that were open are now down: the DS menu-load crash was solved (S53); the browse_hook is irrelevant
(menu triggers the connect natively). So: stand up the UE5.4 DS (`unreal-stub/`) hosting `LVL_Tutorial` +
`BP_LokiGameMode_Tutorial`, answering the S62 handshake (EngineNetVer 34, GameNetVer 0, NetworkChecksum
3716198887). Caveat (S62 ceiling): the bare stub lacks SUPERVIVE content/BP, so it can't RUN
BP_LokiGameMode_Tutorial as-is — the real lift is a DS that can host the actual tutorial gamemode (the same
server-platform problem from the server side). Weigh this vs PATH 1.

## THE SHIM (`tools/sigbypass-mod/tutorial_launch.cpp`) — durable, builds clean
- Slot-285 Login -> C++ `CustomLogin` (PrepareLogin -> stock Login -> LogLoginResult -> RestoreLoginPatches).
  `PrepareLogin` de-overrides the Loki PC InitPlayerState (vtable slots 260+273) to stock (FIX_TARGETED_INITPS)
  so the PC creates its BP_LokiPlayerState locally. All patches transient. `kOverrideSlots={285}` de-overrides
  GameMode Login. `kDefaultCommand` = `open LVL_Tutorial?game=BP_LokiGameMode_Tutorial` (plain full mode).
- Has the ProcessInternal native-call primitive, GUObjectArray walk, FName/vtable helpers, DumpTutorialState.
- Build: `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32` (from tools/sigbypass-mod;
  clang at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
- Inject: `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe tools\sigbypass-mod\tutorial_launch.dll`
  (needs the elevated shell; the game runs elevated). Marker: `docs/tutorial-launch-marker.txt`.

## Key addresses / data (build base `0x7FF6B54F0000`, stable; re-verify each launch via `usmapdump info`)
- ProcessInternal hook rva `0x13454A0`; ExecuteConsoleCommand exec thunk rva `0x395D790`.
- GUObjectArray rva `0x9E38930`; NAMEPOOL rva `0x9D81450`. Obj: Class@+0x18, Name(FName id)@+0x20, Outer@+0x28.
- GameMode Login = C++ vtable SLOT 285; stock Login `0x7FF6B8CD0C50`; stock AGameModeBase vtable rva `0x806EDD8`.
  Match-mode vtables: Tutorial `0x8A94C48`, Round `0x8A52A98`, ALokiGameMode `0x8951FA0`, BR `0x88B7CB0`, DropIn `0x8936948`.
- GameMode config: GameStateClass@+0x3D0, PlayerControllerClass@+0x3D8, PlayerStateClass@+0x3E0.
- Loki PC (`BP_LokiPlayerController_Dev_C`) C++ vtable rva `0x8A1AEE0`; stock APlayerController vtable rva
  `0x81A82F8`; InitPlayerState candidate slots 260 + 273.
- .text range `0x1000`..`0x7649000`. UFunction.Func@+0xE0; FProperty Offset_Internal@+0x44; FField Next@+0x18, Name@+0x20.

## How to run a test cycle (autonomous when shell is elevated + game at menu)
1. Check: elevated shell? game alive at menu (Loki.log `WBP_UI_MainMenu_MenuRootV2`, working set ~500MB)? If so,
   inject directly — NO clicks needed (force-open is a native `open`).
2. If down: relaunch. Shell is elevated, so run `.\configs\launch-redirect.ps1 -NoHook` (it skips its own
   re-elevation when already admin; run it in the background — it blocks on the game). Wait ~55s for the menu.
   (Steam must be up.)
3. Build + inject the shim. Read `docs/tutorial-launch-marker.txt` (`[LOGIN1]` should show the Loki PC,
   `err='(empty=approved)'`) and `Loki.log` (`Client is ready to play` -> the `Browse LVL_LobbyV2` revert +
   `failed to get ULokiServerPlatformInstance`). Force-open crashes/reverts each pass -> relaunch as needed.

## Gotchas / DON'Ts
- Static string->code xref (`usmapdump xrefstr`) does NOT work on this packer — proven (0 hits on live code). Do
  not spend time trying to find `UEngine::Browse` / the revert code that way; use runtime (in-shim) methods.
- The revert is NOT backend-driven and NOT `?listen`-fixable — both ruled out. Don't re-test them.
- Keep any vtable/.rdata patches TRANSIENT/self-restoring (the ~3-5min integrity check covers .rdata).
- Computer-use on the game window is USER-DENIED; the force-open route needs no clicks — drive it via inject +
  markers + logs. The user only needs to leave a game at the menu (or approve the launcher's elevation).
- Don't re-open the SOLVED gates (Login slot-285, PlayerState 260/273). Build on top.

## Live state at end of S64
`tutorial_launch.dll` on disk = the durable FIX_TARGETED_INITPS build (plain full mode). Game may be alive at a
lobby state (the last S64 run reverted without crashing) — relaunch fresh for a clean pass. `ags` still up.
Preserved in scratchpad: `marker-A2-success.txt`, `marker-targeted-loki-pc.txt`, `Loki-S63-both-runs.log`,
`marker-s64-listen.txt`, `Loki-S64-listen-run.log`.
