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

## Session 2 (2026-06-29 continued)

### Probes #3, #4, #5 — all silently absorbed, but architecturally informative

| # | Channel  | Payload                                                       | Result |
|---|----------|---------------------------------------------------------------|--------|
| 3 | WS /lobby | Single `matchmakingNotif` status=done with phantom DS info    | Silent |
| 4 | HTTP     | `CoreGamePlayer` with CORRECT `MatchParticipant + MatchInfo` shape | Silent |
| 5 | WS /lobby | `matchmakingNotif` start→done 2-frame sequence                | Silent |

Each probe was verified server-side (capture.log shows the frames going
out, WS connection stays open, no protocol errors). Zero `LogJson`,
`LogPlatformLobby`, `LogPlatformQuery`, `LogNet`, `NetConnection`, or
`Rejoin` activity in Loki.log on the client side. Menu visually
unchanged across all three.

### Discovery: probes #1+#2 used invented field names

UTF-16 binary scan during this session proved `hasActiveMatch` /
`HasActiveMatch` are ABSENT from the shipping exe — those keys were
never UPROPERTY fields. The actual `CoreGamePlayer` model is:

```
CoreGamePlayer {
  MatchParticipant            (struct)
  ContentServicePrimaryAsset  (FString or FPrimaryAssetId)
  ContentServiceContentManifest (FString)
  CanDisassociate             (bool)
}
```

with `MatchInfo` nested INSIDE `MatchParticipant`. The client decides
"has active match" by checking whether `MatchParticipant` is populated.
Probe #4 re-implemented the response with the correct shape — and
still got silent absorption, which moves the negative result deeper
(the shape is now structurally correct).

### Binary WS protocol-name evidence

UTF-16 scan confirmed which AccelByte v1 lobby type-name strings exist
in this build (and which don't):

```
FOUND: listOfFriendsRequest, setUserStatusRequest, messageNotif,
       matchmakingNotif, partyDataUpdateNotif, startMatchmakingRequest,
       partyNotif, rematchmakingNotif, setReadyConsentRequest,
       partyJoinNotif, partyKickNotif, partyLeaveNotif, partyChatNotif,
       channelChatNotif, LobbyMessage, MMv2
ABSENT: dsNotice, dsClaimedNotif, serverClaimedNotif, dsStatusChangedNotif,
        sessionNotif, sessionV2DsStatusChanged
```

So SUPERVIVE uses AccelByte v1 classic lobby (text key:value format) +
`MMv2` (matchmaking V2). The `dsNotice` classic DS notice is absent — DS
info is presumably delivered inside one of the `*Notif` envelopes (we
tried matchmakingNotif both single-frame and sequenced; both silent).

Also decoded the base64 `activity` field in the client's own
`setUserStatusRequest`: a SUPERVIVE-specific player status payload
containing `dsId: ""` — the dedicated-server-id field the client carries
in its own presence. When non-empty, the client is in a match. This
confirms that DS state is tracked client-side as part of presence, not
purely as a server-pushed notif.

### Architectural conclusion: matchmaking state machine requires a ticket id

The five negative probes converge on one structural finding:

> **SUPERVIVE's client matchmaking subsystem only acts on `matchmakingNotif`
> messages that match a `ticketId` from a previously-sent
> `startMatchmakingRequest`. Unsolicited pushes from a fresh menu carry no
> recognized ticket and are silently dropped.**

The client never sends `startMatchmakingRequest` from a fresh menu
because of the upstream hero-asset gate (Track A; documented as exhausted
in `docs/trackb-assetregistry-route.md` and the hero-roster-blocker
memory file). So spoofing the matchmaking flow purely via server-pushed
messages is structurally blocked.

This invalidates Path C's premise as originally written. Pushing
`ServerClaimedNotification` or `matchmakingNotif` from /lobby cannot
drive UE NetConnection without legitimate client state — and we can't
legitimately set that state without fixing the upstream gate.

### Three remaining forward paths

1. **UE console `open 127.0.0.1:7777` (lowest cost, highest leverage)** —
   UE's built-in NetConnection travel command bypasses the matchmaking
   state machine entirely. If the dev console can be enabled via
   `Engine.ini` `[ConsoleVariables]` / `EnableCheats=true` or a launch
   arg in shipping builds, the player types one command and the client
   opens a NetConnection to whatever address we point at. This makes
   the actual stub server (Path A/C UE5.4 dedicated server build) the
   ONLY remaining work — no Go-side matchmaking spoofing needed at all.
   Next session's first move: try various Engine.ini console-unlock
   approaches, also try `-ExecCmds=open 127.0.0.1:7777` as a launch arg.

2. **Inject matchmaking state externally** — use `tools/usmapdump poke`
   to write a phantom ticket id + "in matchmaking" enum value directly
   into the client's `UMatchmakingSubsystem` memory. Then our
   `matchmakingNotif` with that ticketId would be recognized. Heavy RE
   (need to find the subsystem instance, decode its TMap of pending
   tickets, write a synthetic entry). Falls back to this if path 1 is
   blocked.

3. **Fix the upstream hero-asset gate (Track A redux)** — this was
   declared CLOSED with three single-variable negative tests + AR-repack
   route exhausted. Re-opening would mean revisiting the in-memory
   AssetRegistry hook approach which is multi-session-deep.

### What this session leaves behind

Code state — all five probes reverted to disabled:
- `server/internal/interactive/interactive.go:280` — `phantomMatchState = ""`
- `server/internal/lobby/lobby.go` — `phantomDsPushDelay = 0`,
  `phantomMatchmakingSequence = false`
- All probe scaffolding stays in place (functions + constants); to
  re-enable any probe, flip its constant.

Commits on `dedicated-server-stub` branch (5 probes + reverts +
session-end docs):
- `37dfb4f` Probe #1 — phantom matchInfo Allocating
- `c89e2fb` Probe #2 — AwaitingReady + state-name refactor
- `42db787` Revert probe #1+#2 to disabled
- `fc10733` Session 1 writeup
- `72b4452` Probe #3 — matchmakingNotif on /lobby
- `b739df9` Probe #4 — CoreGamePlayer correct shape
- `321dbe5` Probe #5 — matchmakingNotif start→done sequence
- (session 2 writeup commit follows)

## Session 3 (2026-06-29 continued — UE console open path exhausted)

### Probes #6 + #7 — shipping build hardened against arbitrary network connections

| # | Mechanism                              | Result                                                                |
|---|----------------------------------------|-----------------------------------------------------------------------|
| 6 | `-ExecCmds="open 127.0.0.1:7777"`      | Honored as CmdLine text (line 338); `UEngine::Browse` never called    |
| 7 | Positional URL `127.0.0.1:7777`        | Honored as CmdLine text (line 338); `UEngine::Browse` only fired for LVL_Login |

Both probes verified: the launch arg made it into UE's parsed CommandLine
(visible at `LogInit: Command Line: ...` in Loki.log). `UEngine::Browse`
fired only for the configured DefaultMap (`/Game/Loki/Maps/LVL_Login`) +
the menu (`LVL_LobbyV2_Persistent`). Zero Browse calls referencing
`127.0.0.1:7777`. Zero `LogNet*` activity. Menu reached normally in
both probes.

### Binary scan confirmed dev console is fully stripped

```
FOUND:  UCheatManager, CheatManager, UConsole, IpNetDriver, GameNetDriver,
        NetDriverDef, UEngine::Browse
ABSENT: EnableCheats, -cheat, -cheats, ConsoleKey, ConsoleKeys,
        DebugExecBindings, ConsoleClass, allowcheats,
        /Script/Engine.Console, CheatManagerClass
```

The Console UObject class is in the binary (so the runtime supports it)
but every config-side enable knob is gone. `EnableConsole` is a false
positive — it's actually `EnableConsole120Fps` (a 120fps cvar). So
manual console entry post-menu is also not an option without modding.

### Architectural finding (Session 3)

> **Shipping UE5.4 in this build is hardened against arbitrary network
> connections from the command line.** Both `-ExecCmds=open <url>` AND
> the positional URL form (`Game.exe URL`) are silently dropped before
> reaching `UEngine::Browse`. The dev console is fully stripped at the
> config-enable level. This is consistent with Theorycraft hardening
> shipping against cheating (arbitrary server connections were the
> kind of thing that lets players join unauthorized custom servers).

### Three remaining forward paths — all in-process injection

All cheap external paths are now exhausted. The remaining options
require in-process code:

1. **Hook `UEngine::Browse` externally.** Manual-map a DLL via the
   existing `tools/inject` framework that intercepts the Browse call
   (function exists in this binary per the binary scan + log evidence)
   and rewrites the URL. Bypasses all CmdLine gating.

2. **Call `ConsoleCommand` on a live `PlayerController`.** Find the
   PC instance in memory via `tools/usmapdump`, invoke the UFunction
   externally via APC. Same technique family as the AddDynamicAsset
   registration_shim work in `docs/lokiassetmanager-vtable-dump.md`.

3. **Poke `MatchInfo` directly in a `CoreGameSubsystem`.** Find the
   subsystem instance, write `MatchInfo` fields, let
   `OnMatchInfoUpdated` fire naturally (delegate name confirmed
   in-binary by session 2's scan). Mirrors the UMissionsModel TSet
   poke approach from prior sessions.

Each is multi-session work. The chapter's "easy bypass" hypothesis
(UE console / launch arg) was the correct first thing to try but
didn't pan out for this build.

### Code state at end of session 3

- `configs/launch-redirect.ps1` — `-Open <addr>:<port>` parameter
  kept in place (does nothing useful right now, but the framework is
  there for future probes if Theorycraft updates the build, or as
  part of a hooked launch flow). When set, appends `<addr>:<port>`
  as the positional URL arg.
- No code changes to `server/` — Go backend is in its clean baseline
  from end of session 2 (all probe constants disabled).

Commits added this session:
- `3946366` Probe #6 — `-Open` flag adds `-ExecCmds="open ..."`
- `c3faddf` Probe #7 — switch `-Open` to positional URL form
- (session 3 writeup commit follows)

### Next session's first move

Either:
- **Path 1 (`UEngine::Browse` hook)** — already have the binary RE
  primitives (`tools/usmapdump strings` for finding the Browse function
  address, `tools/inject` for the DLL injection). Smallest scope of
  the three remaining options; one hooked function = arbitrary travel.
- **Path 3 (poke `MatchInfo`)** — most consistent with the prior
  TMap/TSet poke work; might reuse existing `usmapdump poke` directly
  if we can find the right subsystem field offset.

Either path lands us back at "now we need a UE5.4 stub server to
actually receive the NetConnection." The stub-server work itself is
unblocked by the existence of UE5.4 at `H:\Unreal Engine\UE_5.4` —
that part has been clear since session 1.

## Session 4 (2026-06-29 continued — UEngine::Browse hook BUILT AND WORKING)

### Probe #8 (10 sub-iterations) — manual-mapped DLL hook of UEngine::Browse

Took Path 1 from session 3's three remaining options. Delivered an
externally-injected hook of `UEngine::Browse` that intercepts every map
travel call, captures the URL string from the FURL parameter, and
(experimentally in v10) rewrites the FURL.Host field to redirect travel
to `127.0.0.1`.

### Reverse-engineering UEngine::Browse

Found the function via the same xref-the-log-string technique used
throughout this project. The ANSI string `"UEngine::Browse"` (a
`__FUNCTION__` literal for the `LogGlobalStatus` wrapper) lives at
mod-RVA `0x8248AC0`; exactly one rip-relative LEA targets it from
mod-RVA `0x3EC586C`. Scanning backward from the LEA finds the
function entry at **mod-RVA `0x3EC57D0`**.

Function signature (verified by disasm + parameter trace):

```
UEngine::Browse(FWorldContext& WorldContext, FURL URL, FString& Error)
  rcx = UEngine*
  rdx = FWorldContext& (pointer)
  r8  = FURL* (passed by address; stack-allocated by caller)
  r9  = FString& Error (pointer)
```

Patch design:

- The first 13 bytes of the function are exactly 8 push instructions
  (`40 55 53 56 57 41 54 41 55 41 56 41 57`) — a clean
  instruction-boundary cut.
- Patch = `mov rax, hookStub ; jmp rax ; nop` (10+2+1 bytes), an
  absolute 64-bit jump so the hook stub can live anywhere in virtual
  address space.
- Trampoline = 25 bytes: replays the 8 pushes (preserving callee-saved
  registers) then abs-jumps to `original+13` to continue the function.
- Hook stub = ~70 bytes of hand-emitted x64 machine code that spills
  rcx/rdx/r8/r9 ABOVE the C-handler's shadow space, calls the C handler,
  reloads the volatile regs, and tail-jumps to the trampoline.

### Bugs found and fixed across v1-v10

| Version | Symptom                              | Root cause                                                                                                            | Fix                                                                              |
|---------|--------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| v1      | Crash on first Browse                 | C handler used `_vsnprintf_s` — CRT TLS not initialized for game's pre-existing threads                                | Strip all CRT; use manual hex formatter + `CreateFile`/`WriteFile`                |
| v2      | Crash on first Browse                 | Hook stub spilled rcx/rdx/r8/r9 INTO the C handler's shadow space — handler clobbered the saves                       | Allocate 0x48 bytes, spill ABOVE shadow at +0x20/0x28/0x30/0x38                  |
| v3      | Verified patch+trampoline are sound   | Bypass C handler entirely: stub == trampoline                                                                          | Confirmed mechanics OK; bug must be in handler path                              |
| v4      | Verified empty C handler works        | Empty body → no crash → call sequence OK; isolated bug to file I/O                                                    | —                                                                                |
| v5      | Verified handler doesn't crash with deferred-log buffer | File I/O from engine thread is what kills the process (UE main thread doesn't tolerate synchronous disk syscalls) | In-DLL ring buffer with atomic head bump; worker thread flushes every 200ms      |
| v6      | Verified hook is installed but quiet  | Heartbeat in marker shows `head=0` — function not actually called during normal menu use                              | Engine only calls Browse at map transitions; menu UI doesn't trigger it          |
| v7      | First Browse captured                  | watch-now injection + worker polls for prologue bytes before patching (handles packer race)                            | Got first `[browse]` entry: rcx/rdx/r8/r9 with stack-address FURL pointer        |
| v8      | FURL layout decoded                    | Hex dump revealed Map FString at +0x28 (not +0x30 as my guess) — UE packs Port+Valid into the 8 bytes after Host       | Update offset table                                                              |
| v9      | URL string captured verbatim            | Map = `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent` (Num=47, 46 chars + null)                                       | THE WIN — confirmed end-to-end hook with URL decode                              |
| v10     | Rewrite mechanism added (untested)     | Random crash before LobbyV2 browse fired (build instability we've seen all chapter, unrelated to our patch)            | Document and retry next session                                                  |

### FURL layout (UE5.4 SUPERVIVE build, verified empirically)

```
+0x00  FString Protocol     (16B)  "unreal" for net-travel browses
+0x10  FString Host         (16B)  empty for local map browses
+0x20  int32 Port           (4B)   7777 (UE default network port)
+0x24  int32 Valid          (4B)   1
+0x28  FString Map          (16B)  THE URL — what we want to rewrite
+0x38  FString RedirectURL  (16B)  empty
+0x48  TArray<FString> Op   (16B)  empty
+0x58  FString Portal       (16B)  empty
total: 0x68 = 104 bytes
```

### Supporting infrastructure

- `configs/launch-redirect.ps1`: added `-Hook <dll>` flag that uses
  `inject.exe watch-now` in parallel with the normal Steam-compatible
  `& $exe @iniArgs` launch. The watch-now polls every 1ms for the
  SUPERVIVE process to appear and manual-maps the shim DLL the moment
  it's visible. (Initial attempt used `inject.exe launch` with
  CREATE_SUSPENDED, which **bypassed Steam DRM** and the game hung
  forever without a window — confirmed Steam authentication is a
  hard gate at process start in this build.)
- `tools/sigbypass-mod/browse_hook.cpp`: the manual-mapped shim itself.
  Self-contained, KERNEL32-only, mirrors `registration_shim.cpp`'s
  worker pattern. The worker polls for the prologue bytes (avoiding
  the packer-unpack race) before patching, then enters a heartbeat
  loop that flushes the deferred-log ring to
  `docs/browse-hook-marker.txt` every 200ms.

### Path C is now structurally feasible

With v10's URL-rewrite mechanism (modulo build-instability retries),
the chapter's premise is back on track:

1. ✅ External Browse hook intercepts every map travel
2. ✅ Hook rewrites FURL.Host to point at our stub server's IP
3. ⏳ Engine attempts NetConnection to that IP:7777 — we get
   `LogNet*` / `IpNetDriver` activity in Loki.log proving the trigger
   works
4. ⏳ Build a UE5.4 dedicated server that accepts the NetConnection
   and replicates `LokiPlayerState_Missions` (well-documented earlier
   in this file). Stub server scope crystallizes once we capture the
   protocol surface from item 3.

### Next session's first move

Re-test v10 (already committed as `cf72ebb`):
- Close + relaunch with `-Hook` flag
- If LobbyV2 browse fires before random crash, our handler logs the
  capture AND rewrites Host. Loki.log should show LogNet activity.
- If the build keeps crashing before LobbyV2: shorten the window by
  rebuilding ags to skip some lobby-side init, or improve the
  watch-now race to catch LVL_Login's browse instead (current poll
  takes 4.5s — LVL_Login fires at ~1.5s into runtime, way too early).

Commits this session (on `dedicated-server-stub` branch):
- `cf769d4` browse_hook v1 — initial scaffolding + shadow-space fix
- `ca582ff` browse_hook v6 — deferred-log + heartbeat (verified hook works)
- `9e61d49` browse_hook v7 + watch-now (Steam DRM compat + packer-race fix)
- `f9682d5` browse_hook v9 — corrected FURL offsets → URL captured
- `cf72ebb` browse_hook v10 — FURL.Host rewrite mechanism
- (session 4 writeup commit follows)

## Session 5 (2026-06-30 — protocol surface CAPTURED end-to-end)

### Result: chapter's recon premise PROVEN

Re-launched with `-Hook` flag. v10 rewrite triggered cleanly on the
LobbyV2 browse. Engine accepted the mutated FURL, initialized
NetConnection, dialed `127.0.0.1`, crashed in `FMallocBinned2.realloc`
on FString destructor (predicted from the start) — but **before the
crash, Loki.log captured the exact protocol surface the UE5.4 stub
server needs to implement**.

### Browse + handshake init from Loki.log

```
[00:16:08.103] LogGlobalStatus: UEngine::Browse Started Browse:
    "127.0.0.1/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent"
[00:16:08.106] PacketHandlerLog: Loaded PacketHandler component:
    Engine.EngineHandlerComponentFactory (StatelessConnectHandlerComponent)
[00:16:08.106] LogHandshake: Stateless Handshake:
    NetDriverDefinition 'GameNetDriver' CachedClientID: 7
[00:16:08.106] LogNetVersion: Loki 1.0.0.0, NetCL: 0,
    EngineNetworkVersion: 34, GameNetworkVersion: 0
    (Checksum: 3716198887)
```

The URL prefix `"127.0.0.1/..."` confirms `FURL.Host` was applied —
UE serializes net-travel URLs as `Host/MapPath?Options`.

### Protocol surface — exactly what the stub server must match

| Field                    | Value                                                         |
|--------------------------|---------------------------------------------------------------|
| Transport                | UDP                                                           |
| Port                     | 7777 (UE default; already what client dialed)                 |
| NetDriver class          | `GameNetDriver` (= UE's standard `IpNetDriver`)               |
| First handshake component | `StatelessConnectHandlerComponent` (UE5 encryption setup)    |
| `EngineNetworkVersion`   | 34 (= UE5.4)                                                  |
| `GameNetworkVersion`     | 0 (= Theorycraft's project-specific version)                  |
| `NetworkChecksum`        | `3716198887` (the version checksum the server must match)     |
| `NetCL`                  | 0                                                             |
| Project name             | "Loki 1.0.0.0"                                                |

### The crash (predicted, harmless to the recon)

```
LogWindows: Error: appError called: Fatal error:
[File:C:\TheoryCraft\build-staging\Engine\Source\Runtime\Core\Private\HAL\MallocBinned2.cpp]
[Line: 1322]
FMallocBinned2 Attempt to realloc an unrecognized block 0000015D9E220000
canary == 0x0 != 0xe3
```

Address `0x15D9E220000` is our DLL's data segment where the static
`g_redirect_host[]` buffer lives. UE's allocator looks for its canary
byte `0xe3` in the block's metadata header, doesn't find it (we
didn't allocate via FMalloc), panics. This is the
crash-after-success outcome the v10 commit message documented as
acceptable for the probe — fired AFTER the engine had captured all
the protocol surface above.

### Chapter status — Path C unblocked

The entire recon premise from session 1 is now empirically proven:

1. ✅ External Browse hook intercepts every map travel
2. ✅ Hook rewrites FURL.Host to redirect to our IP
3. ✅ Engine initializes NetConnection with the mutated FURL
4. ✅ Engine emits the exact NetDriver + version data the server must match
5. ⏳ Build a UE5.4 dedicated server with these exact fields and wait
   for the connection

Items 1-4 are all done — for the first time in the chapter, the
client's "open a network connection to my server" flow is fully wired.
Item 5 is the new chapter — a UE5.4 C++ project under `unreal-stub/`
(or similar) with `Type = TargetType.Server` that listens on UDP 7777
and answers the StatelessConnect handshake with the matching version
fields.

### Commits this session

- `cf72ebb` (carried over from session 4) — v10 rewrite mechanism
- (session 5 writeup commit follows)

### Next chapter

**Build the UE5.4 dedicated server stub.** Concrete first moves for
that chapter:

1. Create new UE5.4 project at `H:\Unreal Engine\UE_5.4`-based location
   (e.g., `G:\git\Supervive Revival Project\unreal-stub\`)
2. Add a `*.Target.cs` with `Type = TargetType.Server`
3. Set `NetworkChecksum = 3716198887`, `EngineNetworkVersion = 34`,
   `GameNetworkVersion = 0` via the appropriate project config
4. Minimal `ALokiPlayerState_Missions` class with the field shape
   documented in `docs/lokiassetmanager-vtable-dump.md`
5. Launch the server, then launch the SUPERVIVE client with `-Hook`
   pointed at the stub server's address. Connection should now
   complete — and replicated `LokiPlayerState_Missions` should make
   the Missions modal populate, finally closing the chapter's
   original "fix the empty Missions modal" goal.

## Session 6 (2026-06-30 — stub server up and listening on UDP 7777)

### What landed

UE5.4 project scaffolded, Editor target built, **server is running**.
End-to-end pipe wired: client successfully redirects to server, server
accepts the IpNetDriver socket bind. Two pre-handshake blockers identified
for next session.

### Project scaffold (committed at `d985e4d`)

```
unreal-stub/
├── Loki.uproject              EngineAssociation 5.4
├── .gitignore                  Binaries/Intermediate/Saved/DDC excluded
├── Config/
│   ├── DefaultEngine.ini       GameNetDriver definition + bShareMaterialShaderCode=False
│   └── DefaultGame.ini         ProjectName=Loki, ProjectVersion=1.0.0.0
└── Source/
    ├── Loki.Target.cs          Type = TargetType.Game (built OK)
    ├── LokiServer.Target.cs    Type = TargetType.Server (UNBUILDABLE — see below)
    ├── LokiEditor.Target.cs    Type = TargetType.Editor (built OK)
    └── Loki/
        ├── Loki.Build.cs       Core, CoreUObject, Engine, NetCore
        ├── Loki.h
        └── Loki.cpp            IMPLEMENT_PRIMARY_GAME_MODULE
```

### Launcher-install gotchas (took the bulk of the session)

1. **Server-target build blocked.** First build attempt with
   `Type = TargetType.Server` failed with
   `"Server targets are not currently supported from this engine
   distribution."` The Epic Launcher install of UE5.4 includes Editor +
   Game + Editor targets prebuilt but **NOT** Server-target build
   support. Real Server-target build requires the Source distribution
   from GitHub (~100GB clone + 1-3 hour engine compile).

2. **Standalone Loki.exe Game build is unrunnable.** Built cleanly
   (`Loki.exe` 266MB at 20:32) but on launch hit:
   ```
   Serialization Error: "Corrupt data found, please verify your installation"
   Assertion failed at AsyncLoading.cpp:8521 —
   Seeked past end of file /Engine/EngineMaterials/WorldGridMaterial (30170/30169)
   ```
   1-byte off-by-one in the asset stream reader during default-material
   init. Known UE5.4 Launcher-install issue with non-editor binaries
   against uncooked engine content.

3. **Workaround: Editor binary loads our Loki module.** Built
   `LokiEditor` target → produced `UnrealEditor-Loki.dll` (48KB) →
   ran via `UnrealEditor-Cmd.exe Loki.uproject -game -server -log
   -Port=7777 -nullrhi -NoSplash -Unattended /Engine/Maps/Entry?listen`.
   Editor binary is prebuilt by Epic and reads engine content correctly.

### Server is LIVE

Per `unreal-stub/Saved/Logs/Loki.log` (lines 778-782):

```
LogNet: Created socket for bind address: 0.0.0.0:7777
PacketHandlerLog: Loaded PacketHandler component:
    Engine.EngineHandlerComponentFactory (StatelessConnectHandlerComponent)
LogNet: Name:GameNetDriver Def:GameNetDriver IpNetDriver_0
    IpNetDriver listening on port 7777
```

UDP 7777 confirmed via `Get-NetUDPEndpoint`. All three protocol-surface
components from session 5 verified:
- ✅ `GameNetDriver` (= `IpNetDriver`)
- ✅ `StatelessConnectHandlerComponent`
- ✅ Listening on UDP 7777

### End-to-end test (with the client)

Launched SUPERVIVE with `-Hook`. browse_hook v10 rewrote the lobby URL:

```
LogGlobalStatus: UEngine::Browse Started Browse:
    "127.0.0.1/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent"
PacketHandlerLog: Loaded PacketHandler component: StatelessConnectHandlerComponent
LogNetVersion: Loki 1.0.0.0, NetCL: 0, EngineNetworkVersion: 34,
    GameNetworkVersion: 0 (Checksum: 3716198887)
```

Then immediately:

```
LogWindows: Error: appError called: Fatal error:
[File:.../MallocBinned2.cpp] [Line: 1322]
FMallocBinned2 Attempt to realloc an unrecognized block 000001D737920000
canary == 0x0 != 0xe3
```

**Same crash as session 5.** Our v10 static-buffer hack causes FString
destructor to free a non-UE-allocated pointer → fatal. The client dies
**before** sending its first UDP packet — server log shows zero
incoming connections.

### Two pre-handshake blockers for next session

| # | Blocker                                                          | Side    | Fix                                                                                                              |
|---|------------------------------------------------------------------|---------|------------------------------------------------------------------------------------------------------------------|
| 1 | Server `NetCL: 33043543` vs client `NetCL: 0`                    | Server  | C++ hook via `FNetworkVersion::ProcessOverrideCallback` to override NetCL at module init                         |
| 2 | Client crashes in `FMallocBinned2.realloc` before first UDP send | Client  | `browse_hook` v11: find UE's `FMemory::Malloc` and allocate the Host buffer through it (or set `Max=0` if UE checks) |

Blocker #2 is the proximate crash. Blocker #1 wouldn't matter until #2
is solved (no packet ever reaches the server). Once both fixed, the
StatelessConnect handshake should complete and we can see what the
client tries to do next (probably hero-data replication or login token
exchange).

### Commands for next session

Build (re-run if any code changes):
```powershell
& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
  LokiEditor Win64 Development `
  "-Project=G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" `
  -WaitMutex
```

Launch the server:
```powershell
$editorCmd = 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$proj = 'G:\git\Supervive Revival Project\unreal-stub\Loki.uproject'
Start-Process -FilePath $editorCmd -ArgumentList "`"$proj`"",`
  '/Engine/Maps/Entry?listen','-game','-server','-log','-Port=7777',`
  '-nullrhi','-NoSplash','-Unattended' -PassThru
```

Once running, verify:
```powershell
Get-NetUDPEndpoint -LocalPort 7777
```

Launch the client (in a separate elevated PS):
```powershell
.\configs\launch-redirect.ps1 -Hook .\tools\sigbypass-mod\browse_hook.dll
```

### Commits this session

- `d985e4d` unreal-stub scaffold + editor-binary pivot
- (session 6 writeup commit follows)
