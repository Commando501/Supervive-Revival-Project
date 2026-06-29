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

## Session 1 (2026-06-29, branch `dedicated-server-stub`)

### Setup

- Created branch `dedicated-server-stub` from the tip of
  `claude/assetregistry-primary-assets-w7pljz` (88a4e36). The old branch
  name was misleading once the AR-repack route closed; new branch reflects
  this chapter's actual scope and carries all design docs forward.
- UE5.4 install located at `H:\Unreal Engine\UE_5.4` (Epic Games Launcher
  install, but includes `Source/Runtime/Engine` + UnrealBuildTool). That's
  sufficient to build a custom Server target via UBT — **Path A is fully
  viable now**. (Previously assumed Path A would need engine-source clone;
  the Launcher install already exposes what UBT needs for server builds.)

### Probes #1 + #2 — HTTP `/core-game/players/{id}` is NOT the trigger

Two staged probes of `handleCoreGamePlayer` returning
`hasActiveMatch=true` with phantom matchInfo at `127.0.0.1:7777`:

| Probe | State           | Result                                                                  |
|-------|-----------------|-------------------------------------------------------------------------|
| #1    | `Allocating`    | Response parses cleanly (zero LogJson errors). No client action.        |
| #2    | `AwaitingReady` | Response parses cleanly (zero LogJson errors). No client action.        |

Critical observations across both probes (verified via fresh Loki.log
post-relaunch):

- **Zero LogNet*, NetConnection, NetDriver, or port-7777 traffic** in
  Loki.log. The client is not attempting a NetConnection.
- **Menu state visually identical to baseline** in both runs. No
  "preparing match" overlay, no degraded UI.
- **Server capture log confirms client IS polling** `/core-game/players/{id}`
  ~3×/sec, receiving 200s from our handler — the response is being
  CONSUMED, just not acted on.

**Conclusion:** the HTTP `/core-game/players/{id}` response is the
"rejoin" channel, not the primary connect trigger. Advancing State alone
through `Allocating` → `AwaitingReady` produces no NetConnection attempt,
even with full payload (Address/Port/ServerUrl/SessionToken/MatchId).

Code state at end of session: `phantomMatchState = ""` (probe disabled,
menu in known-clean state). Toggle constant in
`server/internal/interactive/interactive.go:267` to re-enable.

### Binary recon — `AccelByteModelsServerClaimedNotification` is the trigger

Grepped the shipping exe for AccelByte-style notification model names
and found:

```
AccelByteModelsServerClaimedNotification    <- THE PUSH WE NEED
AccelByteModelsDSClaimedPayload             <- inner payload
AccelByteModelsDsNotice                     <- classic AccelByte DS notice
AccelByteModelsDSMSession                   <- DSM session model
AccelByteModelsDSMServer                    <- DSM server model
AccelByteModelsDSMClient
AccelByteModelsDSBackfillProposal{Accepted,Received,Rejected}Payload
AccelByteModelsDSGameClient{Joined,Left}Payload
AccelByteModelsDSHub{Connected,Disconnected}Payload
AccelByteModelsDSRegisteredPayload
AccelByteModelsDSUnregisteredPayload
AccelByteModelsSessionEndedNotification
```

Plus PascalCase field-name hits in the binary (matches AccelByte SDK
JSON conventions): `Status`, `Address`, `GameMode`, `Port`, `Region`,
`MatchId`, `SessionId`, `ServerID`, `ServerName`, `PartyId`,
`GameSessionId`, `Namespace`, `IpAddress`.

This pins the architecture:

```
SUPERVIVE matchmaking architecture (now understood):
  Theorycraft's bespoke /party REST API drives the matchmaking-start
  UX. Once a match is allocated, the lobby/notification WebSocket
  pushes AccelByteModelsServerClaimedNotification carrying the DS
  IP/port/session info. UE NetConnection then opens to that DS.
```

The push surface uses AccelByte SessionV2 + DSM messages even though
the request surface is bespoke. That's a known AccelByte integration
pattern: overlay your own party/matchmaking UX, rely on the SDK's
lobby-to-DS bridge.

### Confirmed: the client never sends matchmaking WS frames

Cross-checked capture.log: across the entire session, the client's only
distinct WS TEXT messages are `listOfFriendsRequest`,
`listIncomingFriendsRequest`, `listOutgoingFriendsRequest`,
`setUserStatusRequest`, plus empty heartbeats. **The client does NOT
initiate matchmaking over WS.** Either matchmaking-start is HTTP-only
(via Theorycraft's `/party/.../startSoloMode` or `/party/joinQueue`,
neither captured yet because of upstream gates), OR matchmaking can be
triggered server-side without any client-initiated message — the server
just pushes `ServerClaimedNotification` and the client honors it.

That second possibility is what makes the next probe so cheap: **push
an unsolicited `AccelByteModelsServerClaimedNotification` on /lobby**
when the client connects, see if the client opens a NetConnection on
the supplied IP/port. If YES, we've established the trigger end-to-end
and Path A's scope crystallizes around what to put on the DS side.

## Path decision (post-Session 1)

**Recommended: Path C** (hybrid Go backend + UE5.4 dedicated server).

Why Path A's pure-UE approach is overkill: our existing Go `ags` already
handles every menu HTTP endpoint and the WebSocket channels. Adding the
`ServerClaimedNotification` push to the Go lobby handler is small. The
UE5.4 server only needs to (eventually) replicate `LokiPlayerState_Missions`
to incoming clients. Splitting responsibility this way keeps each side
small.

Why Path B (pure-Go netcode emulator) loses: UE replication protocol is
large and version-coupled; matching SUPERVIVE's specific replicated
classes (UMissionModel field offsets, FName-ID compatibility) requires
either reading UE 5.4 source for the wire format OR running a real UE
client/server pair side-by-side to capture and mimic. The "match real
UE" reading work that Path B would require is the same work that lets
Path C just *use* UE5.4 directly.

## Next-session concrete first moves

1. **Probe #3: unsolicited push of `AccelByteModelsServerClaimedNotification`
   on /lobby.** Implement in `server/internal/lobby/lobby.go` — when a
   WS client connects to `/lobby`, push the notification after a short
   delay (~2 seconds, so we're sure the WS handshake has fully settled).
   Use the AccelByte SDK's JSON shape (the SDK is open source —
   `Plugins/AccelByteUe4Sdk/Source/AccelByteUe4Sdk/Public/Models/AccelByteSessionModels.h`
   has the full struct definition). Phantom DS at `127.0.0.1:7777`, same
   as the HTTP probes; the connection failure mode in Loki.log
   (LogNet*) is the signal.

2. **If probe #3 triggers a NetConnection:** the SUPERVIVE-side recon
   is essentially done. Begin scaffolding the Path C UE5.4 project:
   - New UE5.4 C++ project under `unreal-stub/` in the repo
   - `Target.cs` with `Type = TargetType.Server`
   - Minimal `ALokiPlayerState_Missions` class with the field shape we've
     RE'd (PoolId, flag bytes, etc.) — UClass NAME must match the cooked
     client's expectation so NetGUIDs resolve

3. **If probe #3 does NOT trigger NetConnection:** the missing piece is
   probably a prior client-initiated message we need to handle first
   (e.g., `partyStartMatchmakingRequest` or session-join). Capture the
   exact Loki.log activity around the push, then iterate the WS protocol
   surface (likely a few-message handshake before the DS push lands).

4. **Either way:** once the trigger is end-to-end, the actual stub
   server work begins. Multi-session from there. Treat the next session's
   probe #3 as the milestone gate between "we don't know the protocol"
   and "we know the protocol, now we build."

### Key files for next session's start

- `server/internal/lobby/lobby.go` — add the `ServerClaimedNotification`
  push. Existing structure: `Service.Handle` runs the read loop,
  `respondText` builds typed replies; the new push is server-initiated
  (no client request to reply to), so write it from a goroutine spawned
  at WS connect time with a small delay.
- AccelByte UE4 SDK source: search for
  `FAccelByteModelsServerClaimedNotification` in the public SDK repo at
  https://github.com/AccelByte/accelbyte-unreal-sdk-source (or similar
  fork) to confirm the JSON field shape. The SDK serializes via UE's
  `JsonObjectStringToUStruct`, so field names match the UStruct exactly.
- `server/internal/interactive/interactive.go:267` — `phantomMatchState`
  constant still in place; leave at `""` while running probe #3 so the
  HTTP/WS variables are isolated.
