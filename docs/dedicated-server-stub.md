# Dedicated server stub — design notes for next session

This document captures everything we know about what a SUPERVIVE Revival
dedicated server stub needs to do, written when starting the dedicated-server
work for the first time. Source-of-truth for the GOAL; all the implementation
will be empirical (capture → mimic → iterate).

## Why we need one

Final diagnostic (2026-06-29 G1-G2 result, in
[docs/lokiassetmanager-vtable-dump.md](lokiassetmanager-vtable-dump.md)):

- The Missions modal queries `UMissionsModel.GetActiveMissionModel(fpaid)` /
  `GetClaimableMissionModel(fpaid)` — both NATIVE methods on UMissionsModel.
- Both iterate a TSet at `UMissionsModel+0x30` containing `UMissionModel*`
  pointers.
- That TSet is populated ONLY via `OnPSMissionsUpdated` (FName 0x0058FF4F),
  which fires from **UE Network Replication on `LokiPlayerState_Missions`**.
- At the menu there is NO live `LokiPlayerState_Missions` actor instance
  (CDO-only — confirmed via findptr on its vtable, twice across restarts).
  Hence no missions, hence empty modal.
- Enriching `PUT /progression/players/{id}/mission` response with full
  MissionData payload was tested and confirmed to NOT trigger UMissionModel
  creation — the HTTP path is for write-back, not read.

The same architecture likely blocks Store, Cosmetics, Hunters grid, and
in-match features — all rely on data delivered through UE replication or
asset registration paths the original devs controlled.

## What the stub must do (eventually)

This is the long-arc goal — early sessions only need to satisfy the
"client establishes connection" subgoal before missions can flow.

1. **Accept a UE5.4 NetConnection** from the client. UE's networking is a
   custom binary protocol over UDP (default; can also be WebSocket if
   `NetDriver` is `WebSocketNetDriver`). The client decides which driver
   based on `Engine.ini` or the join URL scheme.

2. **Complete the login handshake**: respond to `NMT_Hello`,
   `NMT_Login`, `NMT_Welcome`, `NMT_Join` control-channel messages with
   plausible values. This establishes the GameNetDriver session.

3. **Spawn the server-side world**: create a UWorld + GameMode + GameState
   that the client will replicate. For menu-only mission delivery the
   world can be minimal (no actors visible to the player), but it has to
   exist as the network owner.

4. **Spawn `ALokiPlayerState` (or its `LokiPlayerState_Missions`
   sub-component)** for the connecting client. Populate its mission
   fields with the data the player should see (daily/weekly/seasonal/
   onboarding/PCBang missions per `WBP_UI_MissionModalCategory_C`'s
   `PoolAsset` references).

5. **Replicate the PlayerState to the client**. The client's UE
   networking layer creates the corresponding actor instance, fires
   `OnRep_*` callbacks, which trigger `OnPSMissionsUpdated`, which
   populates `UMissionsModel`'s TSet, which makes
   `GetActive/GetClaimableMissionModel` return UMissionModel objects,
   which finally makes the modal render.

The TRIGGER for the client to connect to our dedicated server is
likely the matchmaking flow — the client polls `/party/matchmaking/*`
and `/core-game/players/{id}`; when our backend returns a `MatchInfo`
with a server URL + connect-token, the client opens a NetConnection
to that URL.

## Realistic implementation paths

### Path A — Build a UE5.4 dedicated server project from scratch

Pros: speaks UE replication natively; can use the engine's reflection
to construct actors correctly; matches the wire protocol by definition.

Cons:
- Requires UE5.4 source + a substantial C++ project setup.
- We need to recreate `ALokiPlayerState_Missions` and `UMissionModel`
  classes in our project, matching the cooked client's UClass NAMES
  (so NetGUIDs resolve) and FIELD LAYOUT (so replicated values land at
  the right offsets).
- "Recreate" is bounded: we've already RE'd most of the class shapes
  in `docs/lokiassetmanager-vtable-dump.md`. Property lists are also
  available via the FModel JSON export at
  `docs/exports/WBP_UI_MissionModalCategory.json`.
- UE 5.4 dedicated server build is supported but requires the engine
  source (or the installed editor). Pure binary install ships with
  client-only and editor binaries; dedicated server needs `Target.cs`
  with `Type = TargetType.Server`.

### Path B — Write a UE5-netcode emulator (Go or C++ outside of UE)

Pros: zero UE dependency; matches the rest of the project's "stdlib-only
Go" aesthetic.

Cons:
- UE's replication protocol is large and not formally documented. The
  community has partial implementations (e.g., UE pseudo-server projects
  for various games) but matching SUPERVIVE's specific replicated
  classes requires per-class encoding logic.
- NetGUIDs are computed from path+class hashes. We'd have to derive
  them from the cooked client's UObjectArray, which is doable but
  finicky.
- The cleanest known reference: UE source `Engine/Source/Runtime/Engine/Private/NetConnection.cpp`,
  `Engine/Source/Runtime/Engine/Private/DataChannel.cpp`. Reading these
  tells us exactly what bytes go on the wire.

### Path C — Hybrid (probably the right answer)

1. Build a minimal UE5.4 dedicated server in C++ — only the classes
   needed to replicate `LokiPlayerState_Missions` with mission data.
2. Have our existing Go `ags` backend hand the client this server's
   URL via the matchmaking response, so the client opens a
   NetConnection to it.
3. The C++ server replicates the PlayerState; missions appear in
   the menu modal.

Smaller per-component scope than Path A (only mission classes need
to match), and reuses our existing Go backend for everything that's
already working.

## What we already know about the matchmaking/connect flow

From the HTTP capture log + binary recon:
- The client calls `GET /core-game/players/{id}` repeatedly — currently
  returns `{hasActiveMatch:false, matchInfo:null, player:null}`.
- When a match starts, this is supposed to return `matchInfo` with
  server connection info — quote from `server/internal/interactive/interactive.go`:
  "When a match starts, this is where the match + server connection
  info goes."
- The exact shape of `matchInfo` is unknown — needs RE. Likely fields:
  server IP/port, session token, match ID.
- The client also polls `/party/matchmaking/customGameModes` and
  `/party/matchmaking/info`.

For menu-mission delivery we might need to ALWAYS return a "phantom
match" matchInfo pointing at our stub server, even outside actual
matches. That tells the client "you're in a session with the server"
and the PlayerState replication starts. Worth investigating whether
this works without entering a real match map.

## Key technical anchors (from this session's RE)

UMissionsModel layout — what the dedicated server's replication needs
to fill on the CLIENT side once connected:

```
UMissionsModel
  +0x30 : TSet<UMissionModel*>  ← populate via OnPSMissionsUpdated
  +0x80 : TMap (empty in both seen instances)
  +0xD0 : TMap (empty)
  +0x120: TArray (populated on UProgressionManager-owned mm2,
                  empty on UEndOfGameModel-owned mm1)
  +0x130: TArray (same pattern)
  +0x140: TArray (same pattern)
  +0x160: 32 bytes of hash/state data

UMissionModel
  +0x40, +0x48 : FPrimaryAssetId PoolId — the lookup key
                  GetActiveMissionModel filters by this
  +0xB8, +0xB9 : flag bytes — both must be 0 to qualify as
                  "active" / "claimable" per the disasm
```

Per-category pool wiring (from FModel JSON export of
`WBP_UI_MissionModalCategory.uasset`):

| Category | PoolAsset BP classes (these are FPrimaryAssetIds when looked up) |
|---|---|
| Dailies | DA_MissionPoolDailyEasy_C, DailyChallenge_C, DailyEasy_Planbee_C, DailyChallenge_Planbee_C |
| Weekly | DA_MissionPoolWeekly_C, WeeklyChallenge_C, Weekly_Planbee_C, WeeklyChallenge_Planbee_C |
| Seasonal | DA_MissionPool_Tournament_C |
| Onboarding | DA_MissionPoolOnboardingPlanbee_C, MissionPoolOnboarding_C |
| PCBang | DA_MissionPoolDailyPCB_C, DA_MissionPoolDailyPCB_Armory_C |
| ArmoryTest (hidden) | DA_MissionPoolArmoryOnboarding_C |

For a smoke test, even 1 UMissionModel with PoolId =
MissionPool:DA_MissionPoolDailyEasy + flags=0 would make the Dailies
tab render that 1 entry.

## First-session goals (suggested)

1. Survey UE5.4 dedicated server build options. Does the user have UE5.4
   engine source installed (typically G:\UE_5.4 or similar)? Or only
   the Epic Games Launcher binary install (which doesn't include server
   targets)?
2. Capture the exact protocol the client uses when handed a match
   server URL. Modify the existing `handleCoreGamePlayer` to return a
   fake matchInfo pointing at some test server (even a port that
   nothing's listening on yet) — observe Loki.log for what the client
   tries to do next. That tells us the protocol surface to implement.
3. Decide between Path A / B / C based on what's tractable in 1-2
   sessions of bring-up work.

## Out of scope for the dedicated server work

- The actual GAMEPLAY (kill collision, ability casts, networking
  120Hz, anti-cheat). The stub only needs to deliver the menu-time
  data (missions, hero ownership replication, etc.).
- Real matchmaking. We're not connecting multiple players to the
  same session — single-player phantom session per connecting client
  is the right scope.
- Server authoritative anything (game logic). Just enough state for
  the client's menu views to populate.

## Related project state

Branch: `claude/assetregistry-primary-assets-w7pljz`. Commits from this
session are local-only; user pushes via their `gh auth` shell.

Existing tools:
- `tools/usmapdump` — external RPM toolkit (read-only + 1 write
  `poke` subcommand). Useful for verifying the client's state during
  bring-up tests.
- `tools/extractor` — CUE4Parse-based, including `bpdump` for
  inspecting cooked BP assets (no BP bytecode for this build's
  IoPackage, but property names are exposed).
- `tools/inject` — manual-map DLL injector (for in-process shims).
  Already used for the AddDynamicAsset registration_shim.
- FModel at `G:\Tools\FModel` (set up for SUPERVIVE GAME_UE5_4) —
  exports assets to JSON with full property names.

Existing Go server: `server/cmd/ags` + per-package handlers in
`server/internal/*`. Plays the HTTP/HTTPS + WebSocket roles for the
client's REST surface; dedicated-server work would extend this OR
launch as a sibling process.
