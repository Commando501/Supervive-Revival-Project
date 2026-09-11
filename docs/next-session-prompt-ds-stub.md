# Next session — PLAYABLE tutorial via the DEDICATED-SERVER route (leave the loading screen)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (governs everything)

**We keep working — session after session — until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a
controllable hero drops in, and you can move/play it.** Multi-session is expected. "Done" = a hero you can
control. Make concrete progress each session + hand off cleanly. No stops until it's playable.

## WHY WE'RE ON THE DS ROUTE NOW (the force-open route hit its ceiling)

The client-side **force-open** route got very far (login bypass, PlayerState fix, the menu-revert, the gamemode
initializer reaching "Finished") but has a hard ceiling: the tutorial gamemode is **server-authoritative**, so on
a client-only force-open the round never starts (`EGP_BeginInit` forever), the feature toggles never become
"ready" (gating hero input/camera), and the gamemode won't resolve/spawn/control a hero. S68 exhausted four
explicit spawn+possess methods — all failed. Details: `docs/session-68-spawn-possess.txt`,
`docs/session-6{3,4,5,6,7}-*.txt`, memory `supervive-tutorial-launch-status`. **Do not re-grind force-open.**

The **dedicated-server route** works WITH the engine's netcode instead of against the packer, and it already
clears the force-open's hardest walls **for free** (a server-provided session gives the client a valid
PlayerState + Login). Read `supervive-dedicated-server-status.md` and `docs/dedicated-server-stub.md` first.

## WHERE THE DS ROUTE IS (grounded — S62 live-verified)

The UE5.4 **dedicated-server stub** lives in `unreal-stub/Source/Loki/` (git branch `dedicated-server-stub`).
~40 sessions built its netcode: StatelessConnect handshake, login/Welcome/Join, PC spawn, and class-net-cache-
divergence **suppression** (`LokiNetDriver::IsClassNetCacheDivergent`) + `NetworkChecksumMode=None` to keep the
connection alive despite schema differences. **S62 breakthrough:** the client reaches the DS **cleanly via the
real menu** (no more crash-prone `browse_hook`) — `ags` serves `MatchInfo.ConnectionDetails.address=127.0.0.1:7777`,
the client's TravelManager connects, the stub's `ULokiGameInstance::ModifyClientTravelLevelURL` rewrites the
travel to `/Game/Loki/Maps/Tutorial/LVL_Tutorial`, and:

  START → StatelessConnect handshake → LoadMap **LVL_Tutorial** → "Bringing World up for play" → **Join succeeded**
  → NO "PlayerState is null", NO "failed to Login", stable 90s+.

**So the DS session CLEARS the force-open PlayerState/Login wall.** BUT: the client then **STALLS on the SUPERVIVE
loading screen** ("DROP IN, GEAR UP… LOADING…") and never transitions into the world.

## THE GATE (this route's frontier): leave the loading screen

The client loaded the level + Joined, but it **waits for the server to make the match READY** before revealing the
world — i.e. it needs a valid **`LokiGameState` replicated in a playing state** (+ eventually a possessed pawn +
the drop-in trigger). The bare stub provides none of it.

**The fundamental tension (this is the crux):** the stub keeps the connection alive by **suppressing** the
divergent classes (GameState / Pawn / PlayerState) in `LokiNetDriver::IsClassNetCacheDivergent` — but those are the
**same classes the client needs replicated** to leave the loading screen. So the fix is the deferred **Option-B
class-net-cache-divergence SCHEMA-INJECTION** work: un-suppress a target class and mirror its replicated schema so
the client's replica hydrates correctly (the connection stays up AND the client gets real state).

**There is a proven pattern for this** (do NOT reinvent it):
- `FPoolableActorServerState` (S41) — schema-injected a struct so NetIndices align → PC replicates.
- `LokiPlayerState_Missions` (S54) — mirrored a native class by path (`/Script/Loki.<Name>`, both modules "Loki",
  client binds the class NetGUID by path — NO IoStore overlay) + a member-wise USTRUCT whose RepLayout cmd stream
  is byte-identical to the client's. Live-verified: bunch accepted, replicated, client stable.
  Tools that RE the client's exact rep layout live: `tools/re/{rep_expand_class,rep_expand,struct_probe,field_walk,
  objprop_probe,field_off_probe}.py`. The usmap is REPEATEDLY WRONG for replicated containers — verify against
  live RPM.

## THE PLAN (S-next)

1. **Diagnose the exact loading-screen-exit condition.** Relaunch the DS + client (recipe below), get to the
   loading-screen stall, and determine WHAT the client is waiting for. Read the client `Loki.log` at the stall
   (what does it poll/expect? a GameState phase? a possessed pawn? a "match ready" flag?) and the stub log (what
   is it NOT replicating). Likely answer: the client's `LokiGameState` replica is suppressed/un-hydrated, so its
   match-state check (e.g. `IsBattleRoyaleBP` / a match phase) never goes "ready".
2. **Un-suppress + schema-inject `LokiGameState`.** Remove `LokiGameState` from `IsClassNetCacheDivergent`'s
   suppression, then mirror the class so its replica hydrates with a valid PLAYING state — the
   FPoolableActorServerState / LokiPlayerState_Missions pattern (RE the client's rep layout with the `rep_expand`
   tools, mirror cmd-for-cmd). Goal: client leaves the loading screen into the tutorial world (even as a spectator
   first is a WIN — it means the world is live).
3. **Then a pawn + drop-in.** Once the world is up, replicate/possess a hero pawn (server-side, via the stub's
   `LokiStubGameMode::PostLogin`/`RestartPlayer`) and trigger the tutorial drop-in. This is where the DS route
   pays off: the SERVER runs the real spawn/possess/round logic the force-open couldn't.

## CONFIG (what to set before running)

- **ags** (`server/internal/interactive/interactive.go`): the S68 force-open hybrid left
  `ConnectionDetails.address=""`. For the DS route, set it back to **`"127.0.0.1:7777"`** (in `buildTutorialMatchInfo`)
  so the client connects to the stub. Keep `forceTutorialMatch=true` (auto-arms the match at idle — no START click
  needed) and `CanDisassociate=true`. Rebuild: `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`.
- **stub** (`unreal-stub/`): `ULokiGameInstance::ModifyClientTravelLevelURL` was retargeted to `LVL_Tutorial` in
  S62 — verify it's still that. `LokiStubGameMode` `bSeedFinalProgress=false`/`bSeedMissions=false` (missions are
  irrelevant to the tutorial; clean baseline).
- **No client-side shim** — the DS route is pure backend + server. (The `tutorial_launch.dll` force-open shim is
  NOT used here.)

## RECIPE (elevated PowerShell; Steam running; start the STUB first so the connect succeeds, not times out)

1. Build the stub (~240s; kill any running `UnrealEditor-Cmd` first — can't relink while running, LNK1104):
   `& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' LokiEditor Win64 Development -Project=<abs>\unreal-stub\...\Loki.uproject`
   (confirm the exact `.uproject` path under `unreal-stub/`).
2. Run the stub:
   `& 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' <abs>\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi -NoSplash -Unattended -abslog=<repo>\docs\ds-server.log`
   Wait for **"IpNetDriver listening on port 7777"** (or run it in the background and poll the log).
3. Rebuild+restart `ags` (address=127.0.0.1:7777), then launch the client via the menu route:
   `.\configs\launch-redirect.ps1 -NoHook` (elevated; run in background — it blocks on the game). The client auto-arms
   the match (~1 min) and connects to the stub.
4. Observe: stub log ("Join succeeded", what it replicates) + client `Loki.log`
   (`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`: LoadMap LVL_Tutorial, "up for play", and what it
   waits for). Screenshot is user-gated; the logs tell the story (loading-screen stall vs world transition).

## HONEST SCOPE

This is a **large, multi-session UE-netcode effort** — recreating enough server-side match state (GameState, then
pawn/drop-in) via schema injection. But it's the architecturally-correct path: it works with the engine, reuses a
proven schema-injection pattern (S41/S54), and already clears the walls that cost the force-open route many
sessions. Expect to spend the first session on step 1 (diagnose) + starting step 2 (LokiGameState). A spectator
view of a LIVE tutorial world (client leaves the loading screen) is the first real milestone.

## KEY FILES / TOOLS / GOTCHAS

- Stub source: `unreal-stub/Source/Loki/` — `LokiNetDriver.{h,cpp}` (IsClassNetCacheDivergent suppression, InitBase
  NetworkChecksumMode=None), `LokiStubGameMode.{h,cpp}` (PostLogin), `LokiStubPlayerController.{h,cpp}`,
  `LokiGameInstance.{h,cpp}` (ModifyClientTravelLevelURL→LVL_Tutorial), `LokiStatelessConnect`/`LokiIpConnection`
  (handshake), `LokiReplicatedStructs.h` + `Loki.cpp` (FPoolableActorServerState schema-inject + boot rep-layout
  dumpers `DumpClassNetCacheLayout`/`DumpMissionProgressRepCmds`), `LokiPlayerState_Missions.{h,cpp}` (the S54 mirror
  pattern to copy).
- Live-RPM rep-layout RE tools: `tools/re/{rep_expand_class,rep_expand,struct_probe,field_walk,objprop_probe,
  field_off_probe,parse_minidump}.py`. Crash dumps: `<GameRoot>\Loki\.sentry-native\reports\*.dmp`.
- Handshake constants (S5/S62): EngineNetworkVersion 34, GameNetworkVersion 0, NetworkChecksum 3716198887.
- GOTCHAS: kill `UnrealEditor-Cmd` before rebuilding the stub (LNK1104); start the stub BEFORE the client;
  the ~103s "garbage-thread" client crash was tied to a half-hydrated replica (correct schema cured it in S54 —
  watch for it, correct typing is the cure); an intermittent pre-Join menu-load read-AV is the known-flaky one
  (just relaunch); the usmap lies about replicated container types — verify with the live rep-expand tools.
- Don't run `launch-redirect.ps1 -Revert` casually (strips hosts + cacert). Kill a prior `SUPERVIVE-Win64-Shipping`
  before relaunching (launch-redirect doesn't).

## STATE AT HANDOFF
Force-open work is fully documented + banked (2 reusable fixes: login-hold + SuperStruct@0x48). `ags` currently has
the force-open hybrid (`address=""`); flip it to `127.0.0.1:7777` for the DS route. Stub is on branch
`dedicated-server-stub`, S62 state (ModifyClientTravelLevelURL→LVL_Tutorial). No game/stub running.
