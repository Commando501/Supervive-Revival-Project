# Next session (S63) — FINISH the playable tutorial: give the force-opened PC a PlayerState

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (read this first, it governs everything)

**We are going to keep working — session after session — until we have a FULLY PLAYABLE tutorial:
the SUPERVIVE tutorial map loads, a controllable hero drops in, and you can actually move/play it.**
This is a long-haul, multi-session effort and that is expected and accepted. Do NOT treat "diagnosed"
or "map loads" or "connected" as done — those milestones are already behind us. "Done" = a hero you can
control in the tutorial. Keep pushing through the native-RE grind; each session make concrete forward
progress and hand off cleanly. The user has explicitly said: no stops until it's playable.

## Read first (don't re-derive — it's all logged)
1. **`docs/session-62-coregame-match-shape.txt`** — the full S62 arc (menu route → DS connect → tutorial
   map loads via session → the FORCE-OPEN pivot → the custom-Login design + why).
2. Memory (auto-loaded index `memory/MEMORY.md`): **`memory/supervive-tutorial-launch-status.md`** — the
   ★★★-blocks at the end are the live frontier (custom-Login built, root cause = PC has null PlayerState,
   PCClass = BP_LokiPlayerController_Dev_C). Also `supervive-dedicated-server-status.md` (the DS route +
   why it can't be the playable path) and `supervive-missions-page-status.md` (the ProcessInternal
   native-call primitive — the shim is built on it).
3. `CLAUDE.md` (launch/run procedure, packer/anti-tamper facts, "what NOT to do").

## WHERE WE ARE — three routes, one playable path

- **MENU route (backend, DONE):** clicking START now fires a real UE NetConnection to the DS address we
  serve (`ags` CoreGamePlayer.MatchID + MatchInfo.ConnectionDetails.address). Purely backend JSON, no
  native hacks. This is a genuine milestone but it needs a *server that hosts the tutorial*, which the
  bare stub can't be.
- **DS-STUB route (parked):** the UE5.4 `unreal-stub/` server connects + the client loads LVL_Tutorial
  WITH a session (past the S61 PlayerState crash!) — but it STALLS on the loading screen: the stub has
  NONE of SUPERVIVE's content/BP logic, can't run BP_LokiGameMode_Tutorial, and un-suppressing the
  divergent GameState/Pawn classes to leave the loading screen is a 136-prop schema-injection lift that
  STILL yields an inert world. So the DS stub CANNOT produce a playable tutorial. (It proved one key
  fact: a valid session clears the PlayerState gate.)
- **FORCE-OPEN route (THE PLAYABLE PATH — current frontier):** the standalone client force-opens
  `LVL_Tutorial?game=BP_LokiGameMode_Tutorial` and instantiates the REAL tutorial gamemode as the
  authority → it runs the actual drop-in/objectives/bots LOCALLY. Two native walls: (1) native
  `ALokiGameMode::Login` reject — CRACKED (GameMode C++ vtable SLOT 285 de-override to stock); (2)
  "PlayerState is null" — ROOT-CAUSED this session, see below. This route runs real tutorial logic, so
  it's the path to actually playing.

## THE EXACT WALL (root-caused S62, proven with an instrumented shim)

We built an **instrumented custom-Login** into `tools/sigbypass-mod/tutorial_launch.cpp`: it replaces
GameMode vtable slot 285 with `CustomLoginTramp` (a naked x64 fn that calls stock `AGameModeBase::Login`
= gmb[285], LOGS the state at Login-return, returns the PC). Live marker:

    [LOGIN1] gm=BP_LokiGameMode_Tutorial_C  PCClass=BP_LokiPlayerController_Dev_C
             pc=0x0  PSClass=BP_LokiPlayerState_C  err='PlayerState is null'

Interpretation (decisive):
- Stock Login SPAWNS the PC fine (SpawnPlayerController OK) but the spawned **BP_LokiPlayerController_Dev_C
  has a NULL PlayerState** → stock `InitNewPlayer` returns "PlayerState is null" → Login returns null → fatal.
- **SUPERVIVE's PlayerController defers PlayerState creation to NETWORK REPLICATION** (server sends it).
  A standalone force-open has no server, so the PC never gets one. (This is EXACTLY why the DS route
  cleared this gate and force-open can't.)
- PlayerStateClass is VALID (`BP_LokiPlayerState_C`) — so it's NOT a missing-class problem; it's a
  "the PC didn't create/receive a PlayerState locally" problem.

## THE FIX TO IMPLEMENT (S63 first task)

Make `BP_LokiPlayerController_Dev_C` create its PlayerState LOCALLY, so stock Login's InitNewPlayer passes
and returns a real PC (with a `BP_LokiPlayerState`). Cleanest = de-override the PC's `InitPlayerState`
(the native AController virtual that spawns `GameMode->PlayerStateClass`) to stock `AController::InitPlayerState`,
IN the trampoline, BEFORE calling stock Login (so `SpawnPlayerController`'s new PC picks up the stock
InitPlayerState during its PostInitializeComponents).

**GOTCHA that blocked finishing S62:** `Default__BP_LokiPlayerController_Dev_C` is **NOT loaded at the
menu** (only during the tutorial travel), so its vtable CANNOT be diffed offline. Find the InitPlayerState
slot AT LOGIN-TIME from inside the shim (the class IS loaded then — CustomLoginTramp has the GameMode, so
`GameMode+0x3D8` = the PC UClass, and its `ClassDefaultObject` gives the C++ vtable).

Concrete plan:
1. **Instrument first:** in `LogLoginResult` (runs at Login-return, class loaded), get
   BP_LokiPlayerController_Dev_C's CDO (walk objects for `Default__BP_LokiPlayerController_Dev_C`, OR
   read `GameMode+0x3D8` UClass → ClassDefaultObject → vtable), diff its C++ vtable vs stock
   `Default__PlayerController`'s vtable (**.text-only, with the vtable-END guard** — `scratchpad/vtdiff2.py`
   already implements this; the GameSession diff bug this session was reading PAST the vtable into .rdata
   strings, DON'T repeat that). DUMP the override slots + a few disasm bytes to the marker.
2. **Identify InitPlayerState** among the overrides: it's the one that references `GameMode->PlayerStateClass`
   (@GM+0x3E0) and calls `SpawnActor` (spawns the PlayerState). If PostInitializeComponents (an AActor
   virtual) is what skips InitPlayerState, de-override THAT instead. (Both are candidates.)
3. **De-override** that slot in the PC class vtable to the stock value, transiently, right before stock
   Login (add an `InstallPCInitPlayerStateDeoverride` alongside the existing `InstallCustomLogin`).
4. **Test:** [LOGIN] should now show `pc != 0x0` and a non-null PlayerState + `err='(empty=approved)'`, and
   the game should NOT crash at "PlayerState is null" — the full BP_LokiGameMode_Tutorial should proceed.

**Fast alternative to try first (cheap sanity check):** in the trampoline, poke `GameMode+0x3D8` = stock
`APlayerController` UClass (= `ClassOf(Default__PlayerController)`, findable in-shim) before stock Login, so
`SpawnPlayerController` makes a STOCK PC (which has stock InitPlayerState → creates the PlayerState). This
gets PAST login immediately and tells you whether a hero then drops in — BUT a stock PC loses Loki input/
camera/hero-possession, so it's a diagnostic, not the final fix. If it works, do the real InitPlayerState
de-override to keep the Loki PC.

## AFTER THE PLAYERSTATE WALL (the rest of "playable")
Once Login returns a real PC, expect the tutorial gamemode to run. Remaining for PLAYABLE:
- **A hero to drop in:** the force-open uses `-NoHook` (no roster), and `hero=` was empty. Inject
  `catalog_store_fix.dll` for a selectable hunter, OR confirm the tutorial spawns its own default hero.
- **Drop-in spawn:** LVL_Tutorial has NO PlayerStart by design; the hero drops via
  `Comp_GameMode_DropPlane_Tutorial`. Verify it fires once the gamemode + PC + PlayerState exist.
- **Verify controllable:** hero visible, movable, tutorial objectives/bots active. That = DONE.

## Key addresses / recipes (build base `0x7FF6B54F0000`, stable across restarts — re-verify each launch)
- ProcessInternal hook rva `0x13454A0`; ExecuteConsoleCommand exec thunk rva `0x395D790`.
- OBJOBJECTS (GUObjectArray) rva `0x9E38930`; NAMEPOOL rva `0x9D81450`.
- Stock AGameModeBase CDO vtable rva `0x806EDD8`; **GameMode Login = C++ vtable SLOT 285** (offset 0x8E8);
  stock Login = gmb[285] = `0x7FF6B8CD0C50` this build.
- Match-mode CDO vtables (slot addr = vtRva + slot*8): Tutorial `0x8A94C48`, Round `0x8A52A98`,
  ALokiGameMode `0x8951FA0`, BattleRoyale `0x88B7CB0`, DropIn `0x8936948`.
- GameMode config member offsets: GameSessionClass@+0x3C8, GameStateClass@+0x3D0,
  **PlayerControllerClass@+0x3D8**, PlayerStateClass@+0x3E0, HUDClass@+0x3E8, DefaultPawnClass@+0x3F0.
- Object layout: Class@+0x18, Name(FName id)@+0x20, Outer@+0x28. UStruct: SuperStruct@+0x40,
  Children(UField)@+0x50, ChildProperties(FField)@+0x58. FField: Next@+0x18, Name@+0x20.
  FProperty Offset_Internal@+0x44. UFunction.Func@+0xE0.
- .text range for the vtable-end guard: rva 0x1000 .. 0x7649000 (above that = .rdata/data, NOT code).

## Tools
- **The shim:** `tools/sigbypass-mod/tutorial_launch.cpp` — has the ProcessInternal native-call primitive,
  the slot-285 GameMode de-override (`InstallCustomLogin`), `CustomLoginTramp` (naked x64: 3-push frame,
  calls stock Login, logs gm/PCClass/pc/PSClass/PC->PlayerState/ErrorMessage), `LogLoginResult`,
  `PropOffset` (walk class+super for a prop offset). Build:
  `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32` (from tools/sigbypass-mod;
  clang at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
  Command source: `kDefaultCommand` is now the FULL tutorial mode (the external `docs/tutorial-launch-cmd.txt`
  read is flaky, so the compiled default is authoritative).
- **Injector (built this session):** `tools/inject/inject.exe mmap SUPERVIVE-Win64-Shipping.exe <dll>`
  (build with `go build -C tools/inject -o inject.exe .` if missing).
- **`scratchpad/vtdiff2.py`** — `.text`-guarded vtable diff, `<PID> <lokiCDOName> <stockCDOName>`.
- **`scratchpad/pm_flags.py` / `poke_gate2.py`** — menu-route gate-2 poke helpers (not needed for force-open).
- **usmapdump** (`tools/usmapdump/usmapdump.exe`): `objects`/`vtdump`/`vtslot`/`disasm`/`peek`/`poke`/
  `strings`/`wstrings` — read-only RPM + `poke` (takes the process NAME). `usmapdump info <name>` for base.

## How to run a test cycle (each pass; game CRASHES at this gate by design)
1. Build the shim (above). Kill stale game: `Stop-Process -Name SUPERVIVE-Win64-Shipping -Force`.
2. **ELEVATED** PowerShell, from repo root: `.\configs\launch-redirect.ps1 -NoHook` (clean, no pi8 racing
   the PI hook; do NOT use `-Verb RunAs` if already elevated — it stalls on a fresh UAC prompt). Wait ~55s
   for the main menu (`WBP_UI_MainMenu` / LVL_LobbyV2 "up for play" in Loki.log).
3. Inject: `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe tools\sigbypass-mod\tutorial_launch.dll`.
4. Read `docs/tutorial-launch-marker.txt` (`[LOGIN...]`, `[VT]`, `[4] CALLED`, `[VEH]` crash lines) and
   `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (Browse/LoadMap LVL_Tutorial, "Game class is
   BP_LokiGameMode_Tutorial_C", "PlayerState is null" / DropPod / Possess / HandleBeforeCrash).
   A fresh mmap gets fresh globals, so you can re-inject into a still-alive menu game to re-run one-shot.

## Gotchas / DON'Ts
- Don't repeat the S62 vtable-diff bug: reading PAST the vtable end returns `.rdata` string pointers, not
  functions (that's why the GameSession de-override crashed InitGame). Always guard with the `.text` range.
- The slot-285 (and any) vtable patch must be TRANSIENT/self-restoring — the ~3-5min code-integrity check
  covers `.rdata` vtables (a persistent 10-vtable patch hard-crashed at menu in ~30s, S61). The shim already
  installs before force-open + restores after; keep that pattern for the PC-vtable de-override too.
- First boot sometimes random-crashes in Vivox init ("Access Token Service Unavailable") BEFORE the menu —
  unrelated, just relaunch.
- Computer-use on the game window is USER-DENIED; the force-open route needs NO menu clicks (it's a native
  console `open`), so this route is fully drivable by you (inject + read markers). The user only needs to
  approve the launcher's elevation.
- The DS stub + menu route are NOT the playable path — don't sink time re-grinding them (see the ceilings
  above). Force-open + PlayerState is the way.

## Live state at end of S62
Game likely EXITED (crashes at the PlayerState gate each pass) → relaunch fresh. `ags` may still be running
(harmless; the force-open route doesn't need it, but launch-redirect rebuilds/restarts it anyway). Shim +
inject.exe + vtdiff2.py are built. `tutorial_launch.cpp` compiles clean with the working custom-Login.
```
