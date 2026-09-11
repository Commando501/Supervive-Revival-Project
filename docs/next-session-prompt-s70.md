# Next session — DS route: schema-inject ALokiGameState so the client leaves the loading screen

Paste this whole file as the first message of a fresh Claude session.

---

## ✅ STATUS (updated 2026-07-11): the mirror is WRITTEN, WIRED, and COMPILES. The task below is now the LIVE TEST.
The `ALokiGameState` mirror + all wiring are DONE and build clean (`Build.bat LokiEditor` exit 0, `-WarningsAsErrors`):
- `unreal-stub/Source/Loki/LokiGameStateStub.{h,cpp}` — `ALokiGameState : AGameStateBase` (path
  `/Script/Loki.LokiGameState`), all 43 replicated props in the S69 field order + nested
  `FLokiSharedMatchStartDetails`/`FSharedMatchStartParticipant` + `ELokiRoundPhase`/`ELokiDayNightStateMirror` enums.
- `LokiStubGameMode`: `GameStateClass = ALokiGameState` + `InitGameState()` seeds a PLAYING state
  (`CurrentPhase=EGP_SpawnSelect(4)`, RoundStartTime, NumTeams=1, a MatchStartDetails.MatchID).
- `LokiNetDriver::IsClassNetCacheDivergent`: `AGameStateBase` term REMOVED (un-suppressed).
- `Loki.cpp`: boot `DumpClassNetCacheLayout(ALokiGameState::StaticClass())` added.

**So the next session is purely: run the live test (recipe below), read the logs, and iterate on any desync.**
Expected outcomes: (a) client logs `Entering game state` for the tutorial + the loading screen clears → the
`InitGameState` seed's phase may need tuning (try `EGP_Combat=7`); (b) `ReceivedBunch: Invalid replicated field N in
GameState` → a RepLayout desync at cmd N — first suspects are the two enum widths and the nested MatchStartDetails
element format; re-dump with `tools/re/rep_expand_class.py` and compare to the boot `DumpClassNetCacheLayout` output in
`docs/ds-server.log`. FIRST-run tip: to isolate "does the 43-prop layout even ALIGN" from "does the phase clear the
screen", you can comment out the seed body in `InitGameState` and ship a default GameState — a clean accept proves the
schema, then re-enable the seed. Verify the boot dump shows GameStateBase's 4 reps then LokiGameState's 43 (ServerState
still injected on AActor@10).

---

## THE MISSION (unchanged)
Keep working, session after session, until the SUPERVIVE tutorial is FULLY PLAYABLE (map loads, a controllable
hero drops in, you can move/play it). "Done" = a hero you can control. Make concrete progress + hand off cleanly.

## WHERE WE ARE (S69 — step 1 DONE, step 2 fully de-risked)
The DS route works up to the loading screen and the stall is ROOT-CONFIRMED. Read `docs/session-69-ds-loadingscreen.txt`
FIRST (it has the complete captured schema + plan) and memory `supervive-dedicated-server-status`.

- ags serves `MatchInfo.ConnectionDetails.address="127.0.0.1:7777"` (already set) → the menu-route client connects to
  the stub, the stub rewrites travel to LVL_Tutorial, and **Join succeeds** — reproduces every launch, autonomously,
  readable entirely from logs (no computer-use needed; screenshots are user-gated but the logs tell the story).
- **THE GATE:** after Join the client sits on "DROP IN, GEAR UP… LOADING" forever. There is NO `LogLokiGameState:
  Entering game state` for the tutorial ⇒ the client has NO replicated GameState, because the stub's
  `LokiNetDriver::IsClassNetCacheDivergent` SUPPRESSES `AGameStateBase` (+ DefaultPawn + WorldSettings). Its native
  match-ready check never fires → loading screen never clears.

## THE TASK (step 2 — all schema already captured, no re-discovery needed)
Un-suppress + schema-inject a native `ALokiGameState` mirror so the client's replica hydrates → it leaves the loading
screen (spectator view of the live tutorial world = the first real milestone). Follow the proven
`LokiPlayerState_Missions.{h,cpp}` by-path mirror pattern (native UCLASS named `LokiGameState` → path
`/Script/Loki.LokiGameState` → client binds its own class; member-wise USTRUCTs; engine `FPrimaryAssetId`; NO custom
serializer unless a live desync demands it).

The **exact 43-property replicated layout is in `docs/session-69-ds-loadingscreen.txt`** (GameStateBase = stock 4 net
props; LokiGameStateBase = 0; LokiGameState = 43 props / 67 leaf cmds incl. `CurrentPhase`(enum), phase/round-time
fields, and a nested `MatchStartDetails`). Steps:
1. `unreal-stub/Source/Loki/`: add `ALokiGameState : public AGameStateBase` (UCLASS → `/Script/Loki.LokiGameState`)
   mirroring the 43 net props in EXACT field order + `GetLifetimeReplicatedProps` listing all 43. Define the nested
   `FLokiSharedMatchStartDetails` + `FSharedMatchStartParticipant` USTRUCTs (fields in the doc).
2. `LokiStubGameMode`: `GameStateClass = ALokiGameState::StaticClass()` (currently stock AGameStateBase).
3. `LokiNetDriver::IsClassNetCacheDivergent`: remove the `AGameStateBase` term (un-suppress) — ONLY after step 2, else
   a stock-schema GameState bunch desyncs. Keep WorldSettings + DefaultPawn suppressed.
4. `Loki.cpp`: add `DumpClassNetCacheLayout(ALokiGameState::StaticClass())` at boot to verify 43 reps headlessly.
5. `LokiStubGameMode::PostLogin` (or a BeginPlay hook): seed the GameState to a PLAYING state — set `CurrentPhase` to a
   deploy/playing value, real `RoundStartTime`/`GameStartWorldTime`, `ReplicatedNumRemainingPlayers`, and populate
   `MatchStartDetails` (MatchID + one Participant = the local player). Bisect which value flips the loading screen.

## RECIPE (elevated PS; Steam running; start the STUB first)
1. Rebuild stub (~240s; KILL `UnrealEditor-Cmd` first — LNK1104): `Build.bat LokiEditor Win64 Development
   -Project=...\unreal-stub\Loki.uproject`.
2. Run stub: `UnrealEditor-Cmd.exe ...\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=<repo>\docs\ds-server.log`; poll for "IpNetDriver listening on port 7777".
3. Client: `.\configs\launch-redirect.ps1 -NoHook` (elevated, RUN IN BACKGROUND — it blocks on the game; the shipping
   exe's `& $exe` returns early via Steam relaunch, so the launcher task "completes" while the game runs on). It
   rebuilds ags (address already 127.0.0.1:7777), regens certs, sets the redirect. Client auto-arms the match (~1 min).
4. Read `docs/ds-server.log` (stub) + `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (client). SUCCESS =
   client logs `Entering game state` for the tutorial + the loading screen clears. Desync = `ReceivedBunch: Invalid
   replicated field N` → a RepLayout mismatch at cmd N (usual suspects: the enum bit-widths, the nested
   MatchStartDetails element format — iterate exactly like the S54 missions desync using `tools/re/rep_expand_class.py`
   / `field_walk.py`).

## REMAINING LIVE-RE (grab first launch, ~2 min)
`DayNightState` + `CurrentPhase` underlying enum + max value (bit width) so the EnumProperty cmds align, and confirm
the `MatchStartDetails` leaf order. Tooling: `tools/re/find_uclass.py <PID> <BASE> <Name> Class` (BASE = game module
base, ASLR — `Get-Process ... MainModule.BaseAddress`) → feed the UClass addr to `rep_expand_class.py` (raise its
`i<40` field cap; LokiGameState has 136 fields).

## GOTCHAS
- Manual ags rebuild: `go build -C server -o ags.exe ./cmd/ags` (the CLAUDE.md `-o server\ags.exe` form writes to
  server\SERVER\ags.exe by hand — the launcher is fine, it uses an absolute -o).
- Kill a prior `SUPERVIVE-Win64-Shipping` AND the running stub before a new test (launch-redirect doesn't kill the
  game; the stub can't relink while running).
- The usmap LIES about replicated container types — verify against live RPM (that's why S69 captured the layout live).
- At S69 handoff the diagnostic run may still be LIVE (game on loading screen, stub listening, ags up) — kill all
  three before the step-2 test.
