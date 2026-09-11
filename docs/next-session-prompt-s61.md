# Next session (S61) — make the force-launched TUTORIAL playable (match-setup phase)

Paste this whole file as the first message of a fresh Claude session.

---

## Goal
The tutorial MAP now force-loads and renders (S60 breakthrough). Make it actually **playable**:
a controllable hero that drops in, a working GameState, and the tutorial objectives running. This is
the "match-setup" layer — distinct from "map loads", which is already solved.

## Read first (do NOT re-derive — it's all logged)
1. Memory: **`memory/supervive-tutorial-launch-status.md`** (the full S60 chain + every dead end + the
   exact next-phase leads). Also `memory/MEMORY.md` line for the one-line summary.
2. `CLAUDE.md` (launch/run procedure, "what NOT to do", the packer/anti-tamper facts).
3. `memory/supervive-hero-roster-blocker.md` + `memory/supervive-missions-page-status.md` — the
   ProcessInternal game-thread native-call primitive (S55–S58) that the force-launch shim reuses.

## Where we are (state, verified live)
- **Menu route (committed backend fixes, keep):** `server/internal/interactive/interactive.go` serves
  `/party/matchmaking/info` as `QueueInfo{Queues:[]QueueDetails,ETag,LastUpdated}` (usmap was WRONG —
  Queues is a STRUCT array, not strings), `/party/matchmaking/customGameModes`, and a seeded party
  `targetQueueId`; `server/internal/loki/loki.go` routes `/configuration/client`. Result: BATTLE/PRACTICE/
  TUTORIAL tabs populate and **Basic Training selects** with a live START button. `queueIDs` was trimmed to
  {tutorialNew,training,practice,bots} because `CanControlQueue`'s `GetLevelGameFeatureUnlocked` loop fails on
  level-gated queues at account-level 0 (full-tabs fix = serve a high account level).
- **START is a native dead-end:** clicking START calls native `PartyManager.TryStartSoloMode`, which bails
  (region gates only the FIND MATCH matchmaking path; tutorial is solo). So we PIVOTED to force-launch.
- **★ FORCE-LAUNCH WORKS — the tutorial map loads + renders, no crash ★** via
  `tools/sigbypass-mod/tutorial_launch.cpp` → injects
  `ExecuteConsoleCommand(WorldContext=live ProgressionManager, "open LVL_Tutorial?game=<GameMode>", null)`
  through the ProcessInternal primitive (hook PI @base+0x13454A0, capture a live FFrame, call the UFunction
  thunk directly; param recipe from `missions_nativecall_probe9.cpp`). Live log proof: `UEngine::Browse
  Started Browse .../LVL_Tutorial` → LoadMap → WorldPartition init → "Bringing World LVL_Tutorial up for play".

## The wall to break (match-setup tension — PROVEN by test)
| `?game=` mode | Login | Match setup |
|---|---|---|
| **BP_GameMode_BasicTraining** (= DefaultEngine.ini alias `TutorialMode`, the OFFICIAL tutorial mode) | ✅ loads | ❌ `FindPlayerStart: NO PLAYERSTART`, `ALokiGameState::IsBattleRoyaleBP failed to find game state` (repeats) — no hero, blown-out spectator view |
| **BP_LokiGameMode_Tutorial** (full machinery: Comp_BP_BotSpawner + DropPlane_Tutorial + DeathCircle + TutorialObjectives PC) | ❌ crashes `ALokiGameMode::Login failed to Login` (UnrealEngine.cpp:15551) | ✅ has it |

Both inherit `ALokiGameMode::Login`, yet BasicTraining's succeeds and the full mode's crashes ⇒ Login gates on
a PER-GAMEMODE flag/BP-override. Since BasicTraining IS how the real game launches a *playable* tutorial, the
missing piece is the **match context/URL options** the front-end (native `TryStartSoloMode`) passes to
BasicTraining to create the LokiGameState + start the match + trigger the DropPod/DropPlane hero drop-in.
DISASM of that native path is PACKER-BLOCKED (`.text` commits on-demand; the code only exists during the
crashing travel — xrefstr/findptr on the Login strings @.rdata 0x…BE00FCB8 = 0 hits at the menu).

## Concrete next-phase leads (pick one to start)
1. **Dump BasicTraining's CDO classes** to explain "no game state": extractor `dump` needs the FULL path —
   `& "$env:ProgramFiles\dotnet\dotnet.exe" run --project tools/extractor/extractor -c Release -- dump "Loki/Content/Loki/Core/GameModes/BP_GameMode_BasicTraining"`
   then read GameStateClass / DefaultPawnClass / PlayerControllerClass. If GameStateClass isn't an
   ALokiGameState, that's why the tutorial spawners fail.
2. **Find the match-start / drop-in trigger** — how BasicTraining starts the match and fires the DropPlane/
   DropPod spawn (BP_DropPod_Tutorial, DropPlane_Tutorial). Consider calling the trigger via the primitive.
3. **Inject the roster fix for the hero** — `tools/sigbypass-mod/catalog_store_fix.dll` so the hunter resolves
   and can spawn. (This launch was `-NoHook` so no hero resolved regardless.)
4. **Login-approve shim** — let the FULL `BP_LokiGameMode_Tutorial` run by making `ALokiGameMode::Login`
   approve. Hard (packer timing: Login code only commits during the travel, crash is immediate on failure).
   Reference the sig-bypass timing lessons in `docs/hero-roster-attempts.md`.

## How to run / retest (exact)
- Launch/relaunch (ELEVATED, self-elevates; Steam must be running): from repo root
  `.\configs\launch-redirect.ps1 -NoHook`  (`-NoHook` skips catalog_store_fix + mainmenu_refresh_pi8; the
  latter ALSO hooks ProcessInternal and would BLOCK tutorial_launch's hook — always relaunch `-NoHook` for
  force-launch work, then inject catalog_store_fix manually if you need the hero).
- It kills ags/go but NOT the game — kill a stale/stuck game first (`Stop-Process -Name SUPERVIVE-Win64-Shipping -Force`).
- Build the shim: `clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32` (from tools/sigbypass-mod).
- Inject ONLY when the game is at a STABLE menu (injecting mid-boot/into a hung proc no-ops):
  `.\tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe tools\sigbypass-mod\tutorial_launch.dll`
  Marker: `docs/tutorial-launch-marker.txt`. Watch `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`.
- ags rebuild/hot-swap: `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags` then
  Stop-Process ags + relaunch (it's non-elevated, Stop-Process works). ags serves :8080 HTTP + :443 HTTPS.

## Gotchas
- Module base this build = `0x7FF6B54F0000` (stable across restarts, but re-verify each launch:
  `.\tools\usmapdump\usmapdump.exe objects SUPERVIVE-Win64-Shipping.exe` — takes the process NAME not PID).
- The shim's `kObjObjectsRva=0x9E38930 / kNamePoolRva=0x9D81450 / kPiRva=0x13454A0` are current for this build.
- Don't re-grind: region/QoS (only gates FIND MATCH, not the tutorial), `?listen` (negative — fails to Listen +
  Login still rejects), the menu-route START (native dead-end). Force-launch is the route.
