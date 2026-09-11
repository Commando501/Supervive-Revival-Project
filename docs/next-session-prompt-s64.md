# Next session (S64) — FINISH the playable tutorial: get the gamemode to STAY in the match (beat the server-orchestration revert)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (read this first, it governs everything)

**We keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map
loads, a controllable hero drops in, and you can move/play it.** This is a long-haul, multi-session effort
and that is expected. "Done" = a hero you can control in the tutorial. Do NOT treat "login works",
"map loads", or "gamemode runs" as done — those are behind us now. Each session make concrete forward
progress and hand off cleanly. The user has said: no stops until it's playable.

## WHERE WE ARE (S63 cleared two big gates — read `docs/session-63-playerstate-fix.txt` first)

The force-open route now gets FAR into the real tutorial gamemode. Gate ladder:
- **[DONE] travel + load** LVL_Tutorial with BP_LokiGameMode_Tutorial (S60).
- **[DONE] native Login reject** — GameMode C++ vtable **slot 285** de-override to stock (S61).
- **[DONE] "PlayerState is null"** — **S63 fix**: de-override the Loki PC's **InitPlayerState** (vtable
  slots **260 + 273** on `BP_LokiPlayerController_Dev_C`) to stock, so the PC creates its own
  `BP_LokiPlayerState` LOCALLY. Force-open login is **APPROVED with the REAL Loki PC** (not a stock stub).
- **[DONE] WaitingForClientsReady** — with the real Loki PC the log shows `LogLokiGameMode: Display:
  Client is ready to play.` + `TryUIReady SUCCESS` (the stock-PC A2 diagnostic got stuck here; the Loki PC
  clears it).
- **[NEXT — THE WALL] server-side match orchestration.** ~184ms after "Client is ready to play", the
  gamemode does a **raw `Browse` to `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent`** (back to the menu),
  logging **`LogLokiGameMode: Error: failed to get ULokiServerPlatformInstance`**, then crashes ~3s later
  at the menu (an incidental UMG crash from the abnormal transition, not the gate).

**Root cause of the revert (decisive, S63):** the ags HTTP capture during the tutorial shows the client
polled ONLY `/storefront/battlepass/progressiontracks` + `/mmr/leaderboard?queueId=tutorialNew`, **NEVER
`/core-game/players`** → the revert is **NOT backend-driven**. It's a **client-side, server-authority
bail**: `BP_LokiGameMode_Tutorial` is server-authoritative and, on a pure-client force-open, lacks
`ULokiServerPlatformInstance` (a dedicated-server platform singleton), so once the client is ready the
server-side match progression can't proceed and it browses to the lobby. This is the **match-setup / server
layer** — it converges with the DS route (`docs/dedicated-server-stub.md`).

## S64 GOAL: make BP_LokiGameMode_Tutorial STAY in the match after "Client is ready to play"

The PlayerState fix is baked into `tutorial_launch.dll` (FIX_TARGETED_INITPS), so every force-open now
reaches this revert frontier directly. Attack it:

1. **RE the revert trigger.** Find what runs between `Client is ready to play` and the `Browse LVL_LobbyV2`.
   - String-xref `"failed to get ULokiServerPlatformInstance"` (usmapdump `strings`/`wstrings` + `xref`) to
     find the lookup site; disasm what consumes its NULL result and whether that path calls the browse/
     travel-to-lobby. The relevant code IS committed during travel (it ran) — but the process crashes ~3s
     after, so capture in-shim while the game thread is held (see the ProcessInternal primitive), or read
     RPM fast.
   - Also check `LogLokiRoundGameMode` phase logic (it reached `EGP_BeginInit`): what advances/aborts the
     round phase, and does the abort browse to the lobby.
2. **Identify + satisfy `ULokiServerPlatformInstance`.** What class/singleton is it (a GameInstance
   subsystem only created for dedicated servers? a `ULokiServerPlatform*`)? Options: stub/create one via a
   shim so the getter returns non-null; OR neutralize the check so the gamemode proceeds without it.
3. **In-shim instrument at "ready to play".** The game thread is reachable via the ProcessInternal
   native-call primitive (see `docs/session-55-native-call-primitive.txt` + the missions shims). Add a
   hold/dump right after the tutorial world is up to sample the gamemode/round state and confirm WHY it
   browses (which object/flag). The S63 shim already has the object-walk + FName helpers.
4. **When it STAYS:** verify drop-in (`Comp_GameMode_DropPlane_Tutorial`) fires; inject
   `catalog_store_fix.dll` for a selectable hero; confirm a controllable pawn = **PLAYABLE**.

## THE SHIM (`tools/sigbypass-mod/tutorial_launch.cpp`) — reworked in S63, builds clean
- Slot-285 Login now points at a plain C++ **`CustomLogin(gm,np,rr,portal,options,uid,err)`** (Win64 ABI
  matches the vtable call site — no naked asm). `CustomLogin` = `PrepareLogin(gm)` → stock Login →
  `LogLoginResult` → `RestoreLoginPatches`.
- **`PrepareLogin`** (runs INSIDE Login, game thread paused — no sampling race): (1) diffs the Loki PC C++
  vtable vs stock APlayerController's, `.text`-guarded, flags override slots whose STOCK fn references
  `GM+0x3E0` (PlayerStateClass) = InitPlayerState candidates; (2) applies `kFixMode`:
  - `FIX_TARGETED_INITPS` (CURRENT, the durable fix): de-override the PS-candidate slots (260, 273) → stock.
  - `FIX_A2_STOCKPC`: poke `GM+0x3D8` PlayerControllerClass → stock APlayerController (diagnostic; loses
    Loki PC behavior — it parks at WaitingForClientsReady).
  All patches TRANSIENT (restored right after stock Login). `kOverrideSlots={285}` still de-overrides the
  GameMode Login. `kDefaultCommand` = the FULL tutorial mode (`open LVL_Tutorial?game=BP_LokiGameMode_Tutorial`).
- Build: `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32` (from
  `tools/sigbypass-mod`; clang at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
- Marker: `docs/tutorial-launch-marker.txt` (`[PREP]`,`[DIFF]`,`[FIX]`,`[LOGIN1]`,`[DIAG]`,`[VEH]`,`[5] done`).

## Key addresses / data (build base `0x7FF6B54F0000`; re-verify each launch)
- ProcessInternal hook rva `0x13454A0`; ExecuteConsoleCommand exec thunk rva `0x395D790`.
- OBJOBJECTS (GUObjectArray) rva `0x9E38930`; NAMEPOOL rva `0x9D81450`. Obj layout Class@+0x18, Name@+0x20.
- Stock AGameModeBase CDO vtable rva `0x806EDD8`; **GameMode Login = slot 285**; stock Login `0x7FF6B8CD0C50`.
  Match-mode CDO vtables: Tutorial `0x8A94C48`, Round `0x8A52A98`, ALokiGameMode `0x8951FA0`, BattleRoyale
  `0x88B7CB0`, DropIn `0x8936948`.
- GameMode config: GameStateClass@+0x3D0, **PlayerControllerClass@+0x3D8**, PlayerStateClass@+0x3E0.
- **BP_LokiPlayerController_Dev_C** C++ vtable rva `0x8A1AEE0`; stock APlayerController vtable rva `0x81A82F8`;
  overrideCount 18; **InitPlayerState candidate slots 260 (stockRva 0x36E1D40) + 273 (stockRva 0x36DEE20)**.
  (De-overriding BOTH cleared the login gate; refine which single slot is InitPlayerState if you want.)
- `.text` range for the vtable-end guard: rva `0x1000` .. `0x7649000`.

## Tools
- **Injector:** `tools/inject/inject.exe mmap SUPERVIVE-Win64-Shipping.exe <dll>` (needs the elevated shell;
  the game runs elevated).
- **usmapdump** (`tools/usmapdump/usmapdump.exe`, takes the process NAME): `strings`/`wstrings`/`xref`/`disasm`/
  `peek`/`poke`/`objects`/`vtdump`/`vtslot`. `usmapdump info <name>` for base. Read-only RPM + `poke`.
- The ProcessInternal native-call primitive (game-thread) — `docs/session-55-native-call-primitive.txt`.

## How to run a test cycle (fully autonomous when the shell is elevated + game is at the menu)
1. First check: is the shell elevated (`[Security.Principal.WindowsPrincipal]...IsInRole(Administrator)`) and
   is `SUPERVIVE-Win64-Shipping` alive at the menu (Loki.log shows `WBP_UI_MainMenu`/heroes fetched, working
   set ~500MB)? If yes, you can inject directly — **no user clicks needed** (force-open is a native `open`).
2. If the game is down: relaunch. Shell is elevated, so run `.\configs\launch-redirect.ps1 -NoHook` directly
   (do NOT `-Verb RunAs` when already elevated — it stalls on a UAC prompt). It blocks until the game exits,
   so run it in the background; wait ~55s for the menu. (Steam must be up, or Auth Failure 14005.)
3. Build the shim (above). Inject: `tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe tools\sigbypass-mod\tutorial_launch.dll`.
4. Read `docs/tutorial-launch-marker.txt` (`[LOGIN1]` should show `pc=...BP_LokiPlayerController_Dev_C`,
   `err='(empty=approved)'`) and `Loki.log` (`Client is ready to play` → then the `Browse LVL_LobbyV2` revert +
   `failed to get ULokiServerPlatformInstance`). The force-open **crashes the game each pass** at/after the
   revert by design → relaunch fresh for the next attempt.

## Gotchas / DON'Ts
- The force-open crashes the game shortly after the revert (menu UMG crash) — expect to relaunch each pass.
- Keep vtable/`.rdata` patches TRANSIENT/self-restoring (the ~3-5min integrity check covers `.rdata`).
- The revert is NOT backend-driven (client didn't poll `/core-game` during the tutorial) — don't sink time
  into ags match-shape changes for THIS gate; it's a client-side server-authority bail on the missing
  `ULokiServerPlatformInstance`.
- Computer-use on the game window is USER-DENIED, but this route needs no clicks — you drive it fully via
  inject + markers + logs. The user only needs to approve the launcher's elevation (or leave a game at the
  menu). If your shell is already elevated and a menu game is up, you need nothing from the user.
- Don't re-open the SOLVED gates (login slot-285, PlayerState 260/273) — they work; build on top.

## Live state at end of S63
Game CRASHED (post-revert menu crash) → relaunch fresh. `ags` PID 2360 still up (harmless; force-open
doesn't need it). `tutorial_launch.dll` on disk = the FIX_TARGETED_INITPS build (durable login+PlayerState
fix). Preserved in scratchpad: `marker-A2-success.txt`, `marker-targeted-loki-pc.txt`, `Loki-S63-both-runs.log`.
