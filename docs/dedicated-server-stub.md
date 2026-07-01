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

## Session 7 (2026-06-30 — diagnostic confirms blocker #2 is pre-send)

### Recon: FMemory::Malloc address in SUPERVIVE shipping exe

Pursued blocker #2 from session 6 (browse_hook v11 needs UE's allocator
so FString destructor frees cleanly). What we found:

- **`FMallocBinned2::Realloc` body at mod-RVA `0xFE25A9`.** Canary check
  at `0xFE25FD` (`cmp al, 0xe3`) followed by `jz +0x21` at `0xFE25FF`
  to canary-OK path or fall through to the fatal log call at `0xFE261D`.
  Verified by tracing `xrefstr` on the FStaticLogRecord at `0x76A0C00`
  (which references the "FMallocBinned2 Attempt to realloc an
  unrecognized block" wstring at `0x76A0C20`).
- **`FMallocBinned2::Free` body at mod-RVA `0xFDFE70`.** Entry `test
  rdx, rdx; jz <skip>; ...`. Located via `xrefstr` on the FStaticLogRecord
  at `0x76A0AB0` referencing the "Attempt to free an unrecognized" wstring.
- **`GMalloc` symbol exists in the binary as a class-debug wstring**
  (`"GMalloc_CLASS=%d (should be set as 1...)"` at mod-RVA `0x81C3AE2`),
  but only used in a debug dump path. Not directly cross-referenceable
  to a usable global address.

Critical limitation: `findptr` and `callxref` both returned **zero hits**
for `0xFE25A9` and `0xFDFE70`. Both Realloc and Free are devirtualized
AND inlined into every call site. The function bodies exist but nothing
references them via vtable or direct call — they're orphan compiler
artifacts. So `vtslot` can't locate the FMallocBinned2 vtable, and we
can't trace from a known caller's vtable load to GMalloc.

To find GMalloc cleanly, the next session would need to:
- Scan for the byte pattern `48 8B 05 ?? ?? ?? ??` (mov rax, [rip+disp])
  followed by `48 85 C0` (test rax, rax) followed by `48 8B 00`
  (mov rax, [rax]) — that's the FMemory::Malloc inlined pattern
- Find the most-common rip-rel target across all such patterns → GMalloc

### Diagnostic UDP listener test

To confirm whether browse_hook v11 is actually required (vs. e.g.
"crash happens AFTER first send, ignore-and-continue might work"):

1. Started a PowerShell UDP listener bound on `:7777`
   (`unreal-stub/udp7777-listener.ps1`).
2. Launched SUPERVIVE with `-Hook` (v10 redirect active).
3. Client reached login, attempted LobbyV2 browse → crashed.

**Listener received ZERO UDP packets.** The FMallocBinned2 crash fires
strictly BEFORE the engine sends a single byte to our server. The
StatelessConnect first-send happens AFTER FString destruction of the
mutated FURL, which crashes before reaching the wire.

### Conclusion: v11 work cannot be skipped

The pre-handshake order is:

```
1. browse_hook fires           [done -- v10]
2. FURL.Host mutated to 127.0.0.1   [done -- v10]
3. Browse body runs            [done]
4. FURL destructor fires       [done]
5. FString destructor frees Host.Data via FMallocBinned2  [CRASH HERE -- v10's static buffer]
6. ... never reaches:
7. NetDriver opens UDP socket and sends first StatelessConnect packet
8. Server receives + responds
```

Item 5 IS the bottleneck. Until v11 allocates Host.Data through UE's
allocator, items 6-8 never happen. No diagnostic shortcut bypasses this.

### Next session's first move

Find GMalloc via byte-pattern scan:

1. Use `usmapdump` (or a small custom Go tool) to scan main module's
   executable pages for the inlined `FMemory::Malloc` pattern (3-5
   instructions starting with `mov rax, [rip+disp]; test rax, rax`).
2. Collect all `[rip+disp]` targets, sort by frequency.
3. The most-common target is GMalloc.
4. Use `peek` on the GMalloc address to read the FMalloc* pointer.
5. Read its vtable (first 8 bytes of the FMallocBinned2 instance).
6. Find the Malloc slot via disasm of one of the inlined sites.

Then update `browse_hook.cpp` to call `GMalloc->Malloc(size, alignment)`
for the Host buffer.

### Commits this session

- `c9d74b3` Session 6 close (carried over)
- (session 7 writeup commit follows)

The `udp7777-listener.ps1` script lives at `unreal-stub/` for future
diagnostic re-runs.

## Session 8 (2026-06-30 — devirtualization proven; v12 Realloc-patch route blocked by suspected packer integrity check)

Session 8 attacked blocker #2 (FString destructor frees Host.Data via
FMallocBinned2 → canary panic) on two fronts. Both were exhausted; we
exit session 8 with a new pattern-scan utility, a v11 wrap-and-restore
Browse hook design, a v12.x Realloc whitelist hook architecture with
thread suspension + RIP-check, hosts-lock retry in the launch script,
and a strong empirical case that PACKER_VERSION 3 has runtime integrity
checks on FMallocBinned2::Realloc that detect any patch and kill the
process before UE's own fatal log can fire.

### Front 1: byte-pattern scan for GMalloc — falsified

Built `tools/usmapdump/pattern.go` (new `pattern` subcommand) implementing
the prompt's recommended strategy: scan for inlined `FMemory::Malloc`
pattern `48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 00 ... FF 60 ??`,
collect rip-rel global-load targets, the most-common is GMalloc.

Three pattern variants tested:
1. Loose prefix only (15 bytes): 56 hits, top target NULL pointer (not
   GMalloc — generic singleton-with-null-check pattern, not FMalloc).
2. Strict prefix + `FF 60 ??` tail-call: 0 hits.
3. Two-pass (find `48 8B 00 ... FF (60|A0) ??` then trace backward for
   `48 8B 05 ?? ?? ?? ??`): exactly **1 hit** across 47MB of unpacked
   executable memory, and that target dereferenced to NULL too.

The build's devirtualization is comprehensive. Almost no virtual dispatch
through global singletons survives in the unpacked code. GMalloc-via-
byte-pattern is dead for this build. Conclusion captured in
`memory/supervive-hero-roster-blocker.md` and in the pattern.go file
header comment.

### Front 2: browse_hook v11 wrap-and-restore — disproved session 7's crash hypothesis

`tools/sigbypass-mod/browse_hook.cpp` extended from v10 to v11: changed
the hook stub from JMP-tail to CALL-then-POST so we wrap Browse. PRE
mutates URL.Host to our static `g_redirect_host` buffer; POST zeroes
URL.Host to `{Data=nullptr, Num=0, Max=0}` before the FURL destructor
fires. The theory: Browse's `Pending->URL = URL` copies our buffer via
FString::operator= which calls FMemory::Malloc → proper FMallocBinned2
allocation; after Browse returns we restore URL.Host to empty so its
destructor short-circuits on null Data.

End-to-end test: SUPERVIVE crashed at the SAME FMallocBinned2 canary
fatal as v10. Crashstack (clearer this time because we wrapped) revealed
the truth: the crash is at mod-RVA `0x3EC6312` (= +0xB42 inside
UEngine::Browse), with our hook stub at offset 0x44 (the byte right
after `call trampoline`). **Browse internally frees URL.Host via Realloc
BEFORE returning to our POST handler.** Session 7's model
(`FURL destructor frees Host.Data → CRASH`) was wrong; the realloc
fires mid-Browse, not after. POST-handler restoration cannot fix this
because the destructive call has already happened.

Positive byproduct: Loki.log now shows `LogHandshake: Stateless
Handshake: NetDriverDefinition 'GameNetDriver' CachedClientID: 7`
and `LogNetVersion: Loki 1.0.0.0, NetCL: 0, EngineNetworkVersion: 34,
GameNetworkVersion: 0 (Checksum: 3716198887)` BEFORE the crash — the
engine reaches NetConnection + StatelessConnect handler init and assigns
a ClientID. We're past v10's reach.

### Front 3: browse_hook v12.x Realloc whitelist — blocked, suspected packer integrity check

Pivoted to patching `FMallocBinned2::Realloc` (RVA 0xFE25A9) at entry to
make calls with `rdx == &g_redirect_host[0]` return NULL immediately
(no canary check, no fatal). Function entry verified via disasm: 13-byte
clean cut at `sub rsp, 0x78; mov rax, rdx; push rbx; push rsi;
push rdi; push r14`. `FMallocBinned2::Free` is at RVA 0xFDFE70 (confirmed
via `test rdx, rdx; jz 0xFE00EB; mov r11, rsp; ...`).

Six iterations:
- **v12.0**: install at worker-thread time. Game crashed before reaching
  LobbyV2 → race condition (engine threads mid-Realloc during patch
  write).
- **v12.1**: defer install to first PRE handler call. Game still crashed
  immediately after install — race with non-engine threads (render,
  audio, worker pools) doing Realloc.
- **v12.2**: SuspendThread on every other process thread before the
  patch write. Suspended 136 threads on a typical test. Still crashed —
  some suspended thread's RIP was inside the 13-byte patch range and
  executed corrupted bytes on resume.
- **v12.3**: extended v12.2 with GetThreadContext RIP-check on every
  suspended thread; retry suspend if any RIP in `[reallocAddr,
  reallocAddr+13)`. Marker showed RIP-check passed in one attempt
  (148 threads, none in range), patch applied cleanly → game still
  crashed.
- **v12.4**: added synchronous `Marker()` diagnostic calls at every
  PRE phase boundary (entered, /Game detected, Install returned,
  URL.Host mutated, AppendBytes done, returning). **Critical finding:**
  PRE completes ALL phases successfully and writes "[PRE] returning to
  hook stub" to disk; POST handler's "[POST] entered" never fires.
  The crash is in Browse body AFTER PRE returns.
- **v12.5**: rewrote trampoline + hook stub to use `r10` (volatile
  scratch) instead of `rax` for the jump-target register, preserving
  the original prologue's `mov rax, rdx` semantics through the jump.
  Identical crash pattern as v12.4 — rax preservation wasn't the bug.
- **v12.6**: added byte-dump of trampoline and hook stub to the marker
  immediately after construction. Both confirmed bytes-perfect against
  the intended encoding. So the patch is what we think it is.

**Hypothesis: PACKER_VERSION 3 (Theorycraft's anti-tamper, per
Loki.log) has runtime integrity verification of
FMallocBinned2::Realloc.** Evidence:
- v11 produces a clean UE_LOG fatal ("Attempt to realloc an unrecognized
  block ...") visible in Loki.log.
- v12.x produces a HARD CRASH (silent termination, only Sentry crashpad
  catches it) — no Fatal/FMalloc/Critical/Callstack lines in Loki.log.
  A different failure category than v11.
- The Browse function we patched (RVA 0x3EC57D0) has no equivalent
  protection — the v10/v11 Browse hook has fired thousands of times
  across sessions without integrity-check repercussions.
- Realloc is a frequently-instrumented function in anti-cheat /
  anti-tamper systems because it's a common hook target for cheats.

If correct, no amount of trampoline/encoding tuning will bypass v12.
Need a different attack surface.

### Tooling delivered

- `tools/usmapdump/pattern.go` — new `pattern` subcommand. Scans exec
  memory for the inlined `FMemory::Malloc` shape, reports rip-rel
  targets sorted by hit count, samples a call site per target, includes
  helpful next-step `peek`/`disasm`/`vtdump` commands at the end. Three
  match-strictness levels in the code: loose prefix, +vtable-jmp tail,
  and two-pass (anchor on `48 8B 00 ... FF 60`, trace backward for
  `48 8B 05`).
- `configs/launch-redirect.ps1` — hosts-file write now retries up to
  20 times at 250ms intervals on `IOException`. Defender/SmartScreen
  intermittently holds an exclusive scan handle on hosts; the retry
  loop hides it. Previously failed launches 4-5 times per session;
  with the retry it succeeds first try every time.
- `tools/sigbypass-mod/browse_hook.cpp` — v12.6 source with the full
  Realloc whitelist infrastructure: pre-built trampoline + hook stub
  (r10-based jumps, byte-dump on construction), `SuspendOtherThreads` +
  `AnyRipInRange` + `ResumeOtherThreads` helpers, `InstallReallocPatchOnce`
  with up-to-20-attempt RIP-check loop, synchronous diagnostic markers
  throughout PRE/POST. The Realloc install itself is currently behind
  the "no apparent bug but still crashes" wall; the infrastructure is
  reusable for any future entry-patch hook.

### Possible next-session strategies

1. **Patch the canary check site instead of function entry.** RVA
   0xFE25FD is `cmp al, 0xE3`. Inserting a whitelist check there only
   affects realloc/free failures (rare), not every Realloc call (vast).
   If the packer's integrity scope is narrower than the whole function
   body, this might evade it. Requires more disasm to size the patch.
2. **GMalloc via `GMalloc_CLASS=%d` wstring xref.** Session 7 dismissed
   this as "not directly cross-referenceable" but didn't actually run
   `xrefstr 0x81C3AE2`. Even an obscure debug-dump path is a thread to
   pull on — the loader of that string accesses GMalloc somehow.
3. **Hook UNetConnection downstream.** Instead of mutating URL.Host
   (which forces us into the FString-buffer-lifetime mess), hook the
   socket-creation or address-resolution path so the engine resolves to
   127.0.0.1 without us touching FString. Requires FURL.Host to be
   non-empty for the engine to enter NetConnection at all — chicken-and-
   egg, but maybe solvable by hooking earlier (URL parser).
4. **Find a less-protected memory-API entry.** FMemory::Free,
   FMallocBinned2::Trim, FMallocBinned2::OOMShutdownActions etc. might
   be less integrity-checked than Realloc. If we can intercept any
   allocation path with the same effect (no-op our buffer), we're done.

### Commits this session

- (session 8 writeup commit follows)
- The chapter's tail end is now: blocker #2 is structurally harder than
  expected; blocker #1 (NetCL mismatch) remains queued for after #2
  resolves.

## Session 9 (2026-06-30 — BLOCKER #2 RESOLVED: client UDP packets reach the stub server)

The chapter's defining win. Session 9 closes blocker #2 (FMallocBinned2
canary crash on URL.Host destruction) by switching from "patch
FMallocBinned2 in place" to "USE FMallocBinned2 to allocate our buffer."
The SUPERVIVE client now successfully reaches StatelessConnect
handshake send and the UE5.4 stub server LOGS INCOMING UDP PACKETS from
the client. Only blocker #1 (NetCL mismatch — server NetCL=33043543 vs
client NetCL=0) remains, and its fix is well-scoped (register
`FNetworkVersion::ProcessOverrideCallback` in the Loki module).

### Frontline negative results (eliminate stale assumptions)

1. **GMalloc-via-`GMalloc_CLASS=%d` string xref is truly dead** (vs
   session 7's "dismissed without test"). Found the wstring at mod-RVA
   0x81C3A60 (full string starts at +0xA60, not +0xAE2 as session 7 cited
   for the mid-string match), and its FStaticLogRecord at mod-RVA
   0x81C3A40. xrefstr AND findptr on every variant (string addr, struct
   addr, unpacked copies in private memory) return 0 hits. The
   debug-dump function that would use this log isn't unpacked in this
   shipping build (cheats=0, console=0 per Loki.log) and may never run.

2. **Patching the canary check at RVA 0xFE25FD is logically
   insufficient.** After the canary cmp at 0xFE25FD, Realloc's body
   continues with `movzx r15d, [rbp]`, `movzx ecx, [rbp+2]`, etc. —
   multiple FMallocBinned2 metadata reads at offsets relative to
   pool_base. For our static buffer those reads return garbage from our
   DLL's memory; bypassing only the canary leaves the metadata-read
   crashes intact. Bypassing the canary doesn't fix the bug.

### The breakthrough — tracing UNetConnection downstream found GMalloc

The v11 crashstack pointed at mod-RVA 0x3EC6312 (Browse+0xB42). At that
address, Browse calls a function at mod-RVA 0x32BCB70. That function is
a destructor-like cleanup that frees FURL fields' FString.Data via a
helper at mod-RVA 0xFF9302. Disasm of 0xFF9302 revealed it as
**FMemory::Free** — a callable wrapper that:

```
0xFF9302: mov [rsp+0x20], rax            ; (shadow space)
0xFF9307: push rdi
... (more saves) ...
0xFF931A: mov rbx, rcx                    ; save Ptr arg
0xFF931D: mov rcx, [rip+0x8D4FE5C]        ; LOAD GMALLOC  ←←←
0xFF9324: test rcx, rcx
0xFF9327: jnz 0xFF9335
0xFF9329: call GCreateMalloc              ; init if null
0xFF932E: mov rcx, [rip+0x8D4FE4B]        ; reload
0xFF9335: mov rax, [rcx]                  ; vtable
0xFF9338: mov rdx, rbx                    ; arg
0xFF933B: call [rax+0x48]                  ; FMalloc::Free (slot 9)
```

Computing the GMalloc address from the rip-rel load:
- `0xFF9324 + 0x08D4FE5C = 0x09D49180`
- So **GMalloc is at mod-RVA 0x9D49180**. Peeking at runtime confirmed:
  the qword there holds the FMallocBinned2* instance pointer
  (`0x000002300935B9E0` on the test launch — varies per-launch due to
  heap ASLR).

### FMallocBinned2 vtable layout (verified via `usmapdump vtdump`)

Vtable at mod-RVA 0x76A0370 (in .rdata). 20-slot dump:

```
slot 0  = ~FMalloc (dtor)
slots 1–4 = shared empty-impl  (Exec / GetAllocatorStats defaults / etc.)
slot 5  = TryMalloc        (real body — sub rsp, …; mov esi, r8d; …)
slot 6  = Malloc           (thunk: mov rax,[rcx]; jmp [rax+0x28] — calls slot 5)
slot 7  = TryRealloc       (real body)
slot 8  = Realloc          (thunk: mov rax,[rcx]; jmp [rax+0x38] — calls slot 7)
slot 9  = Free             (real body — verified by FMemory::Free dispatching [rax+0x48])
slots 10–19 = Trim/Setup/etc.
```

Calling slot 6 (Malloc) from outside the engine works because slot 6 is
itself a thunk forwarding to slot 5 (TryMalloc). The Realloc function
that session 8's v12 hooked at 0xFE25A9 was NOT in this vtable — it's
an orphan function, possibly an unused ICF-merged copy of the original
FMallocBinned2::Realloc. That's why v12.x's hook installed cleanly but
didn't intercept the engine's actual realloc traffic (different code
path → unrelated crash AFTER PRE returned, exactly as v12.4 markers
showed).

### v13 design — read GMalloc + call its allocator

`tools/sigbypass-mod/browse_hook.cpp` v13:
- At DLL init (in the worker, after the Browse page unpacks), poll for
  GMalloc page committed, then read the FMalloc* instance pointer.
- Cast the qword at `[instance]` to the vtable, look up slot 6 (Malloc),
  emit a Win64-ABI indirect call: `vtable[6](GMalloc, 20, 16)`.
- Returned buffer is a real FMallocBinned2 allocation. Write L"127.0.0.1\0"
  into it.
- PRE handler points `URL.Host.Data` at this engine-allocated buffer
  (10 wchars including null, with Num=10, Max=10).
- Engine destructor eventually calls Realloc(buf, 0, _) on it; canary
  check passes (we got it from FMallocBinned2), pool lookup works (it
  IS in the pool), Free succeeds.
- POST handler still zeroes URL.Host as a belt-and-suspenders cleanup,
  but the engine's natural destructor would have handled it fine.

**Zero function-entry patches.** We only READ and CALL the engine's
own code — no instruction stream modifications. No packer integrity
concerns.

### End-to-end test result (CONCLUSIVE WIN)

Marker file traversal (synchronous diagnostic Markers from v12.4 still
in place):
```
[GM] GMalloc=00007FF68C7C9180 instance=0000021764866CE0
     vtable=00007FF68A120370 Malloc=00007FF683A8FE80
[GM] engine-allocated host buffer @ 00000217E49F6AA0 ("127.0.0.1\0", num=10)
[5] engine-host buffer READY after 1 poll(s)
[PRE] entered r8=0xECE71DF450
[PRE] /Game/ map detected; mutating URL.Host -> 0x217E49F6AA0
[PRE] URL.Host mutated to engine buffer; appending
[PRE] AppendBytes done; PRE returning to hook stub
[POST] entered (mutated=1)         ← FIRST TIME POST EVER RAN!
[POST] returning                    ← Browse completed cleanly!
[REWRITE] FURL.Host = engine-allocated 127.0.0.1 buffer (FMallocBinned2-tracked)
[RESTORE] FURL.Host zeroed; destructor will short-circuit on null Data
```

Client Loki.log:
```
LogGlobalStatus: UEngine::Browse Started Browse:
    "127.0.0.1/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent"
PacketHandlerLog: Loaded PacketHandler component: StatelessConnectHandlerComponent
LogHandshake: Stateless Handshake: NetDriverDefinition 'GameNetDriver' CachedClientID: 7
LogNetVersion: Loki 1.0.0.0, NetCL: 0, EngineNetworkVersion: 34,
    GameNetworkVersion: 0 (Checksum: 3716198887)
```

UE5.4 stub server log (`unreal-stub/Saved/Logs/Loki.log`):
```
LogNet: NotifyAcceptingConnection accepted from: 127.0.0.1:54710
LogHandshake: IncomingConnectionless: Error reading handshake packet.
[1s later] LogNet: NotifyAcceptingConnection accepted from: 127.0.0.1:54710
[1s later] (3rd retry)
[1s later] (4th retry — then client gives up)
```

**The client successfully sent four UDP handshake attempts to the stub
server's port 7777.** The server's "Error reading handshake packet"
fails are blocker #1 (NetCL mismatch — see Session 6 close): the server
reports NetCL=33043543, the client reports NetCL=0; StatelessConnect
rejects the protocol mismatch. The client retries 4× over 4 seconds,
then a connect-timeout fires and Sentry catches the resulting crash.

This is a **different failure category** from the v11 FMallocBinned2
fatal — the client got past Browse and into NetConnection-runtime; the
crash is a normal handshake-failure path, not memory corruption. Blocker
#2 IS resolved.

### Infrastructure delivered

- `tools/sigbypass-mod/browse_hook.cpp` v13: GMalloc-aware allocator
  use. The v12.x patch infrastructure (SuspendOtherThreads, AnyRipInRange,
  trampoline+stub builders) is preserved under `#if 0` for future
  function-entry-patch needs. Includes `ms_abi` typedef pattern for
  Win64-ABI vtable calls from clang.
- Diagnostic Markers from v12.4 still in place — confirmed PRE+POST
  full traversal on first test. (Bonus: gives us a great template for
  any future hook work.)

### Next session: blocker #1 fix (server-side)

The fix has been queued since Session 6: register
`FNetworkVersion::ProcessOverrideCallback` in the Loki module's
`StartupModule()` to force NetCL=0. With that, the server reports the
same NetCL as the client, the handshake parser accepts the packets,
and we should see the next stage of NetConnection setup (Open Channel,
etc.) — or hit whatever blocker comes next.

This is normal UE5.4 module init code; touches `unreal-stub/Source/Loki/`
only, no client-side work.

### Commits this session

- (session 9 writeup commit follows)
- v13 is the milestone artifact. Future sessions extend from this base.

## Session 10 (2026-06-30 — blocker #1 peeled: MagicHeader byte 0xBB solved; deeper packet customization remains)

Session 9's `v13` win held: the SUPERVIVE client successfully sends UDP
to the stub server on every test. Session 10 attacked blocker #1 (the
"server can't parse client's handshake packet" failure) on multiple
fronts. We peeled the OUTER layer (MagicHeader, the 8-bit prefix
the client adds to every packet) and identified that the inner
packet body has Theorycraft-customized fields beyond stock UE5.4.

### Server-side fix #1: FNetworkVersion overrides — in place but not the bottleneck

Added `unreal-stub/Source/Loki/Loki.cpp`'s `FLokiModule::StartupModule()`
that binds:
- `FNetworkVersion::GetLocalNetworkVersionOverride` → returns
  `3716198887` (the client's captured checksum from Session 5)
- `FNetworkVersion::IsNetworkCompatibleOverride` → returns `true` for
  any (local, remote) pair (belt-and-suspenders for future client builds)

Rebuilt the Loki module via `UnrealBuildTool` ("Build.bat LokiEditor
Win64 Development" — 85s build). Server log confirms: `Loki stub: NetCL
overrides bound. Local checksum forced to 3716198887; IsNetworkCompatible
accepts any remote.`

This fix is necessary but NOT sufficient — `CheckVersion` is called
AFTER `ParseHandshakePacket`, and we never reached it because parsing
failed earlier.

### The diagnostic UDP listener — captured 35+ handshake packets

Enhanced `unreal-stub/udp7777-listener.ps1` to dump full packet hex
(was 64-byte preview). Stopped the UE5.4 stub server, ran the
listener, launched SUPERVIVE with v13 hook, captured ~35 packets from
two sources (127.0.0.1 + 169.254.83.107 link-local).

Common structure (every packet):

```
Byte 0     : 0xBB         ← stable across ALL packets (magic)
Byte 1     : random        ← per-packet (maybe checksum or nonce)
Bytes 2-5  : DC 21 A6 A3   ← stable across ALL packets/sources
Byte 6     : random
Byte 7     : 0xFB          ← stable
Byte 8     : BC or A0      ← varies by source IP
Bytes 9-10 : 01 02         ← stable
Byte 11    : 0x80 / 0x00   ← alternates (handshake type flag)
Byte 12    : 0x80-0x89     ← increments per packet pair (sequence)
Bytes 13-16: F3 58 C0 6E   ← stable
Bytes 17-48: 32 × 0x00     ← cookie field (initial=zero)
Bytes 49+  : variable tail ← cookie response / signature
```

### Server-side fix #2: MagicHeader CVar — SOLVED with two iterations

UE5.4 `StatelessConnectHandlerComponent` reads
`CVarNetMagicHeader` at construction time and uses it as a fixed bit
prefix on every packet. SUPERVIVE's client uses `0xBB`. We configured
matching MagicHeader on the server.

**Iteration 1 — string `"10111011"`:**

Tried `[ConsoleVariables] net.MagicHeader=10111011` (binary string of
`0xBB`'s bits MSB-first) in `unreal-stub/Config/DefaultEngine.ini`.
Result: server's own diagnostic `Rejecting packet with invalid magic
header '000000BB' vs '000000DD' (8 bits)`. Mismatch! Server computed
`0xDD` from `"10111011"`.

**Bit-ordering math (verified by the server's error message):**

The TBitArray's `Add` puts the FIRST char of the string into bit 0
(LSB) of the resulting uint32. So:

- `"10111011"` → bits [0]=1, [1]=0, [2]=1, [3]=1, [4]=1, [5]=0,
  [6]=1, [7]=1 → uint32 `0b11011101` = `0xDD`
- To produce uint32 `0xBB` (binary `10111011` MSB-first) we need
  bits LSB-first matching: bit 0=1, bit 1=1, bit 2=0, bit 3=1,
  bit 4=1, bit 5=1, bit 6=0, bit 7=1 → string `"11011101"`

**Iteration 2 — string `"11011101"`:**

Server's MagicHeader uint32 now correctly computes to `0xBB`. The
"invalid magic header" error is GONE.

`-ExecCmds` is too late for this CVar — `StatelessConnectHandlerComponent`'s
constructor reads it during engine init. MUST go in
`[ConsoleVariables]` in `DefaultEngine.ini` so it's available
pre-construction. Also setting `net.VerifyMagicHeader=1` explicitly
(default may be 0).

### What's left: ParseHandshakePacket body format mismatch

After MagicHeader matches, server progresses one layer deeper and
hits `IncomingConnectionless: Error reading handshake packet` from
`StatelessConnectHandlerComponent::ParseHandshakePacket()` returning
false. The first check in `ParseHandshakePacket` is a packet-size
validation against `HANDSHAKE_PACKET_SIZE_BITS`,
`RESTART_HANDSHAKE_PACKET_SIZE_BITS`, `RESTART_RESPONSE_SIZE_BITS`,
`VERSION_UPGRADE_SIZE_BITS` (plus random padding variance). If the
client's packet sizes don't fall within these expected ranges, parse
fails before reading any handshake fields — no `CheckVersion` log
ever fires either.

The captured packet sizes are 56-64 bytes (9-byte variance). UE5.4
stock `BaseRandomDataLengthBytes` + `RandomDataLengthVarianceBytes`
implies a similar variance. But the packet BODY layout (after the
8-bit magic and the 7 bits of SessionID/ClientID/Handshake/Restart)
clearly differs from stock — note the stable `DC 21 A6 A3` at bytes
2-5 that varies neither per-packet nor per-source. That's NOT
stock UE5.4 SessionID/ClientID; that's a TheoryCraft custom field.

### Tooling delivered

- `unreal-stub/Source/Loki/Loki.cpp` — custom `FLokiModule` that
  binds FNetworkVersion overrides in `StartupModule()` /
  `Unbind()` in `ShutdownModule()`. Includes `LogLokiStub` log category
  for diagnostic visibility.
- `unreal-stub/Config/DefaultEngine.ini` — `[ConsoleVariables]`
  section with `net.MagicHeader=11011101` and `net.VerifyMagicHeader=1`.
- `unreal-stub/udp7777-listener.ps1` — now dumps full packet hex
  (was 64-byte preview).
- Captured packets in `unreal-stub/Saved/Logs/udp7777-rx.log`
  (35+ packets, structure analyzed above).

### Next session strategies

1. **Hook the CLIENT's `StatelessConnectHandlerComponent::Outgoing`**
   to capture pre-bit-pack handshake fields. We'd see
   `RemoteCurVersion`, `RemoteMinVersion`, `HandshakePacketType`,
   `RemoteNetworkVersion`, `RemoteSentHandshakePacketCount`, and the
   cookie — knowing the unencoded values lets us reverse the wire
   format.
2. **Search for TheoryCraft's custom `StatelessConnect`-derived class**
   in the SUPERVIVE shipping exe. They may have subclassed +
   overridden `IncomingConnectionless` / `Outgoing`. Find via string
   xrefs to `StatelessConnect`-related literals.
3. **Patch our SERVER's `ParseHandshakePacket`** to accept the
   observed packet sizes and parse the custom layout — requires
   recompiling UE5.4 engine source, big effort.
4. **Skip the StatelessConnect handshake entirely** — disable it on
   both sides. Client side requires hooking; server side via
   `bRequiresHandshake = false` on the handler.

### Commits this session

- (session 10 writeup commit follows)

## Session 11 (2026-06-30 — strategy #3 sanity-check confirmed handshake gate; strategy #1 confirmed stock UE5.4 with likely BaseRandomDataLengthBytes tweak)

Session 11 attacked blocker #1's INNER layer (parse-handshake-packet
failure) via two parallel angles: (3) a 10-minute server-side bypass
sanity check, and (1) static RE of TheoryCraft's StatelessConnect
implementation. The bypass produced a clean failure-mode change that
proves the server can accept the client's UDP traffic; the RE proves
TheoryCraft uses stock UE5.4 source and points at a single likely
constant tweak.

### Strategy #3: `-NoPacketHandler` bypass — server accepts, client times out

Added `-NoPacketHandler` to the stub server launch command. In non-shipping
UE5.4 builds (`UE_BUILD_SHIPPING == 0`), this flag has two effects:
1. `UNetDriver::InitConnectionlessHandler` (line 1931) skips creating
   the `ConnectionlessHandler` / `StatelessConnectComponent` entirely.
2. `UIpNetDriver::ProcessConnectionlessPacket` (line 1436) auto-marks
   incoming packets as `bPassedChallenge = true` instead of rejecting
   them when the stateless component is null.

Server log progression with the flag:

```
LogNet: Accepting connection without handshake, due to '-NoPacketHandler'.
LogNet: Server accepting post-challenge connection from: 169.254.83.107:57311
LogNet: IpConnection_1 setting maximum channels to: 32767
LogNet: SetClientLoginState: State changing from Invalid to LoggingIn
LogNet: SetExpectedClientLoginMsgType: Type same: [0]Hello
LogNet: AddClientConnection: Added client connection ...
```

The server allocates a proper `UNetConnection` for the client and is
parked in `LoggingIn` state waiting for `NMT_Hello`. Three independent
network interfaces — 127.0.0.1, 169.254.83.107, 10.5.0.2 — all reached
this state across the test (client tried multiple local IPs).

But the client side stays committed to UE5.4's StatelessConnect
protocol regardless. The client's PendingNetDriver sends handshake
packets, waits 20 seconds for a server challenge-ack reply, gets none
(because our server has no stateless component to reply with), times
out, and Sentry catches the ungraceful `NetworkFailure: ConnectionTimeout`
as a crash:

```
06:31:12 UEngine::Browse Started Browse: ""
06:31:12 PacketHandlerLog: Loaded PacketHandler component: ... (StatelessConnectHandlerComponent)
06:31:12 LogHandshake: Stateless Handshake: NetDriverDefinition 'GameNetDriver' CachedClientID: 0
06:31:32 LogNet: Warning: UNetConnection::Tick: Connection TIMED OUT ... Threshold: 20.00
06:31:35 LogSentrySdk: invoking on_crash hook
```

Conclusion: strategy #3 alone is insufficient — the server-side bypass
opens the gate but the client still expects a stateless challenge-ack
to unlock NMT_Hello. We'd need to *either* implement the stateless
reply on the server *or* bypass the client's StatelessConnect too. The
right path is the former because (a) hooking the packer-protected
client is high-friction and (b) UE5.4's server stateless handshake is
already implemented if we just configure it correctly.

### Strategy #1: RE the SUPERVIVE exe — TheoryCraft uses stock UE5.4

`usmapdump wstrings` for "StatelessConnect" returned 15 heap hits but
zero hits in the main module — meaning the class isn't named at
class-registration sites in code; it's only constructed at runtime in
the heap. `usmapdump strings` for the ANSI ASCII variant found ONE main-
module hit at mod-RVA `0x8160A61` — and `usmapdump peek` of the
surrounding `.rdata` revealed:

```
C:\TheoryCraft\build-staging\Engine\Source\Runtime\Engine\Private\PacketHandlers\StatelessConnectHandlerComponent.cpp
```

That's a `__FILE__` literal — TheoryCraft compiled UE5.4's
StatelessConnect source from THEIR build tree, not subclassed it.
Following the log-entry registration table downstream of the file
path string identified five log call sites with their `__LINE__`
values embedded as 32-bit integers:

| In-binary line | Stock UE5.4 line | Log message |
|---|---|---|
| 441 | 441 | "CVar net.MagicHeader is too long (%i), maximum size is 32 bits: %s" |
| 493 | 493 | "Tried to send handshake connect packet without a server connection." |
| 579 | 579 | "Tried to send handshake response packet without a server connection." |
| 878 | 878 | "Stateless Handshake: NetDriverDefinition '%s' CachedClientID: %u" |
| 1053 | 1053 | "Server is running an incompatible version of the game..." |

Every line number matches stock UE5.4 *exactly*. The build path is
TheoryCraft's, but the source contents at these checkpoints are
identical to Epic's. So they're using stock or near-stock UE5.4's
StatelessConnect, not a custom subclass.

### Why session 10's ParseHandshakePacket still failed

With confirmed stock source, the rejection at line 1430
(`IncomingConnectionless: Error reading handshake packet.`) means
`ParseHandshakePacket` returned `false`. The earliest failure in that
function is the size-variance check at line 1502-1515:

```cpp
const int32 MinBitsLeftExclHandshake = BitsLeft - (HANDSHAKE_PACKET_SIZE_BITS - 1);
const int32 MaxBitsLeftExclHandshake = BitsLeft - (VerRandomizedHandshakePacketSizeBits - 1);
...
const int32 MinRandomBits = (BaseRandomDataLengthBytes - RandomDataLengthVarianceBytes) * 8;
const int32 MaxRandomBits = BaseRandomDataLengthBytes * 8;
const bool bMaybeHandshakePacket = MaxBitsLeftExclHandshake >= MinRandomBits && MinBitsLeftExclHandshake <= MaxRandomBits;
```

Stock UE5.4 constants:
- `BaseRandomDataLengthBytes` = 16 → `MaxRandomBits` = 128
- `RandomDataLengthVarianceBytes` = 8 → `MinRandomBits` = 64
- `HANDSHAKE_PACKET_SIZE_BITS` = 307 (Latest version, includes NetCL)
- With MagicHeader(8) + SessionID(2) + ClientID(3) prefix = 13 bits before ParseHandshakePacket
- Expected total packet size: 307 + 13 + [64..128] + 1 termination bit = 385..449 bits = **48..57 bytes**

Captured packets in `udp7777-rx.log`: **56..64 bytes** (9-byte variance,
matching 9 = `RandomDataLengthVarianceBytes + 1` so the variance
constant is unchanged).

The packet size range is shifted UP by exactly 8 bytes from stock
expectations. The leading hypothesis: **TheoryCraft increased
`BaseRandomDataLengthBytes` from 16 to 24** (variance still 8). That
would produce random data of 16..24 bytes and total packet sizes of
56..64 bytes — exactly matching capture.

This is consistent with: TheoryCraft inheriting Epic's source, but
tweaking the random-padding base value (a one-line change in
`StatelessConnectHandlerComponent.cpp` line 312) without touching any
log lines.

### Captured packet's "stable bytes" reinterpretation

Session 10 noted stable bytes `DC 21 A6 A3` at packet positions 2-5
and `01 02` at positions 9-10. With confirmation that the protocol is
stock UE5.4 + likely BaseRandomDataLengthBytes shift:

- The MagicHeader is bit-packed at bits 0-7 (= byte 0 = `0xBB`).
- Bytes 1+ contain bit-packed fields including SessionID, ClientID,
  HandshakeBit, MinVersion, CurVersion, HandshakePacketType,
  SentHandshakePacketCount, LocalNetworkVersion (32 bits), and
  LocalNetworkFeatures (16 bits).
- The bit-level offset of `LocalNetworkVersion` (3716198887 = 0xDD80B1E7)
  in the wire format depends on the exact bit boundaries — needs full
  bit-by-bit decode to confirm position. The captured bytes 2-5
  `DC 21 A6 A3` are NOT the LocalNetworkVersion value (0xDD80B1E7), so
  the position needs more bit-level math.
- The "alternating 80/00" at position 11 and "increments 80-89" at
  position 12 in session 10's analysis match `SentHandshakePacketCount`
  bit-shifting through byte boundaries as it increments per packet.

### Tooling delivered

- (none — pure analysis session)

### Next session strategies

1. **Modify our UE5.4 engine's `StatelessConnectHandlerComponent.cpp`
   line 312** to set `BaseRandomDataLengthBytes = 24` (matching the
   TheoryCraft hypothesis), rebuild the engine module (UnrealEngine
   target), restart the stub server WITHOUT `-NoPacketHandler`. If the
   server's ParseHandshakePacket no longer rejects the client's
   packets, the stock handshake flow takes over and we should see
   `SendConnectChallenge`, then `SendChallengeAck`, then NMT_Hello.
   ~30 min build + test.

2. **Hook the running game** to confirm `BaseRandomDataLengthBytes`
   value before changing the engine. Disassemble `CapHandshakePacket`
   or `SendInitialPacket` (line 465 of stock UE5.4) and look for the
   immediate operand `0x10` (16) or `0x18` (24). Anchor: the file path
   string at mod-RVA `0x8160A10` references every UE_LOG site in this
   file; finding the LEA xref to it from .text gives us code addresses
   in the function range. ~60 min RE, useful if (1) fails to fix.

3. **Disable `net.VerifyNetSessionID` server-side** as a parallel
   probe — set `[ConsoleVariables] net.VerifyNetSessionID=0`. This
   only matters if the client's SessionID doesn't match the server's
   `CachedGlobalNetTravelCount` (= 0 fresh boot). Per the source
   logic, `bInitialConnect` already bypasses the SessionID check, so
   this likely doesn't change anything — but cheap to try.

4. If (1) fails, expand search to the captured packets' OTHER
   non-stock-expected bytes (positions 9-10 `01 02`, position 13-16
   `F3 58 C0 6E`) — these are bit-aligned with `LocalNetworkVersion`
   and `LocalNetworkFeatures`, which depend on the override mechanism
   we set up in session 10. Cross-check that the bit-decoded values
   match `3716198887` and the captured `EEngineNetworkRuntimeFeatures`
   value.

### Commits this session

- (session 11 writeup commit follows)

## Session 12 (2026-06-30 — BaseRandomDataLengthBytes hypothesis: source change correct, rebuild path blocked by Launcher install)

Session 12 attempted to test the session-11 hypothesis (TheoryCraft uses
`BaseRandomDataLengthBytes = 24` vs stock 16) by modifying the local UE5.4
engine source and rebuilding. The source modification was made, compiled
cleanly, and produced a valid `Module.Engine.50.cpp.obj` containing the
change. However, the final `link.exe` step for `UnrealEditor-Engine.dll`
could not complete because the user's UE5.4 install is a Launcher install
that ships precompiled `.dll`s in `Binaries/` but no `.lib` import
libraries in `Intermediate/` for engine modules — so the linker cannot
resolve dependencies on `UnrealEditor-Core.lib` etc.

### Sequence of events

1. **Source edit accepted** — Modified
   `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\PacketHandlers\StatelessConnectHandlerComponent.cpp`
   line 312 from `BaseRandomDataLengthBytes = 16` to `= 24`. Made a backup
   first (`.supervive-revival-bak`). Also cleared the read-only attribute
   the Launcher install sets on engine source files.

2. **UBT refused on first attempt** — `Build.bat LokiEditor Win64
   Development` returned "Target is up to date" because Launcher installs
   include `Engine/Build/InstalledBuild.txt` which makes UBT treat engine
   modules as immutable.

3. **Workaround: rename InstalledBuild.txt** — Renamed to
   `InstalledBuild.txt.supervive-revival-disabled`. UBT then recognized the
   install as a (pseudo) source build and kicked off 3548 actions.

4. **First rebuild attempt failed at static_assert** — After ~55 minutes
   and 2819/3548 actions complete, the build had errors at lines 1474 and
   1478 of StatelessConnectHandlerComponent.cpp:
   ```
   error C2607: static assertion failed
   ```
   With `BaseRandomDataLengthBytes = 24`:
   - `MinRandomBits = (24-8)*8 = 128`, `MaxRandomBits = 24*8 = 192`
   - `MinRestartHandshakePacketVariance = 82 + 128 = 210`, `Max = 274`
   - `OriginalHandshakePacketSizeBits = 227` falls INSIDE [210, 274]
   - The static_asserts are protective for the case
     `MinSupportedHandshakeVersion == EHandshakeVersion::Original`, which
     we don't use (default is `SessionClientId = 3`).

5. **Relaxed the failing asserts** — Wrapped the two failing
   `static_assert`s in `#if 0` with a comment explaining the rationale.
   The other 6 asserts in the block remain (they use
   `OriginalRestartHandshakePacketSizeBits = 2`, far below any variance
   range).

6. **Second rebuild succeeded at compile, failed at link** — `Build.bat`
   ran 9/737 actions in 73 seconds:
   ```
   [8/737] Compile [x64] Module.Engine.50.cpp     ✓
   [9/737] Link [x64] UnrealEditor-Engine.lib      ✓ (stub import lib only)
   ```
   But action 9 was just `lib.exe` producing the import library stub,
   NOT `link.exe` producing the actual DLL. The DLL link is a separate
   action that runs LATER in the build graph. UBT aborted after action 9
   because actions 1-7 had failed:
   ```
   MiMalloc.c(24): error C1083: 'static.c': No such file
   example_jobify.h(6): error C1083: 'oodle2base.h': No such file
   ConvexDecompTool.cpp(13): error C1083: 'btAlignedAllocator.h': No such file
   UnrealMathSSE.cpp(9): error C1083: 'sse_mathfun_extension.h': No such file
   AttributeInterpolator.cpp(4): error C1083: 'AHEasing/easing.h': No such file
   SlateSdfGenerator.cpp(13): error C1083: 'msdfgen.h': No such file
   RigVMMathLibrary.cpp(4): error C1083: 'AHEasing/easing.h': No such file
   ```
   These third-party source files aren't shipped with the Launcher install
   (only their precompiled .obj files are, which UBT now distrusts).

7. **Manual link.exe attempt failed** — Tried running `link.exe` directly
   with the UBT-generated `UnrealEditor-Engine.dll.rsp` (which has all
   compiler flags + library dependencies). Result:
   ```
   LINK : fatal error LNK1181: cannot open input file
       '..\Intermediate\Build\Win64\x64\UnrealEditor\Development\Core\UnrealEditor-Core.lib'
   ```
   The engine DLL link depends on ~30 other module .lib files
   (UnrealEditor-Core.lib, UnrealEditor-CoreUObject.lib, etc.). The
   Launcher install ships these as compiled `.dll`s in `Binaries/` but
   does NOT include the `.lib` import libraries in `Intermediate/`. The
   manual link cannot proceed.

8. **Engine install restored** — Restored
   `UnrealEditor-Engine.dll` from backup (link.exe had deleted it
   immediately before failing). Restored
   `StatelessConnectHandlerComponent.cpp` from backup (back to stock with
   `BaseRandomDataLengthBytes = 16` and all asserts intact). Renamed
   `InstalledBuild.txt.supervive-revival-disabled` back to
   `InstalledBuild.txt`. Engine install is verifiably intact and matches
   the original Launcher state.

### Why the rebuild path is dead-end for Launcher installs

UE5.4 Launcher installs are designed to be **read-only** for engine
modules. The shipping artifacts include:
- `Binaries/Win64/UnrealEditor-X.dll` — runtime DLLs
- `Source/.../X/` — public + private source headers and cpps (for
  IntelliSense and game-module dependency resolution)
- `Source/.../X/X.Build.cs` — build configuration

The shipping artifacts EXCLUDE:
- `.lib` import libraries for engine modules
- Many third-party source files referenced by engine cpps

This means:
- UBT can produce game-module .lib/.dll that LINK against engine .dll
  (via dynamic linkage at runtime).
- UBT CANNOT relink engine .dll itself (no .lib files to satisfy
  inter-module dependencies).
- Manual link.exe can't fill the gap (same missing .lib problem).

To recompile engine modules, the install must be a **source build** —
fetched from Epic's GitHub repository, with `Setup.bat` run to download
~100GB of third-party dependencies. That's hours of installation +
hours of full engine build.

### Next session's recommended path: Custom UE PacketHandlerComponent override

Rather than modifying engine source, write a custom UE module in the
`unreal-stub` project that:
1. Defines a `LokiStatelessConnect` HandlerComponent subclass of
   `StatelessConnectHandlerComponent`.
2. Overrides `IncomingConnectionless` and `ParseHandshakePacket` to
   handle TheoryCraft's wire format (larger random padding, anything
   else discovered).
3. Defines a `ULokiHandlerComponentFactory` that returns instances of
   our subclass instead of stock.
4. Registers via `DefaultEngine.ini`:
   ```ini
   [PacketHandlerComponents]
   ; Override engine's default StatelessConnect with our version
   ```
   OR via plugin module startup code that swaps the factory at runtime.

This lives entirely in `unreal-stub/Source/Loki/` and never touches the
engine install. UBT compiles it as part of `LokiEditor Win64 Development`,
producing `UnrealEditor-Loki.dll` (small DLL we can rebuild in seconds).

Estimated effort: 3-5 hours, depending on how thoroughly we need to
override (just constants vs. full behavior).

### What we still need to verify before plugin work

The `BaseRandomDataLengthBytes = 24` hypothesis is consistent with all
captured packet sizes but isn't yet PROVEN. Before doing the plugin
work, it would be valuable to disassemble the running SUPERVIVE client's
`CapHandshakePacket` or `SendInitialPacket` and confirm the inlined
constant value. The session-11 RE work identified the StatelessConnect
file path at mod-RVA `0x8160A10` but didn't find direct LEA xrefs from
.text. Possible approaches for the disasm:
- Use `usmapdump xrefstr` against alternative anchors (the FName
  "LogHandshake" string, log struct addresses).
- Use a debugger with PDBs (none ship with Launcher engine binaries).
- Use IDA/Ghidra to load both stock UnrealEditor-Engine.dll and
  SUPERVIVE-Win64-Shipping.exe, do symbol matching via FLIRT/diaphora.

### Tooling delivered

- `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\PacketHandlers\StatelessConnectHandlerComponent.cpp.supervive-revival-bak`
  — backup of stock engine source, preserved for future reference of
  what we attempted.
- `H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Engine.dll.supervive-revival-launcher-bak`
  — backup of stock engine DLL, in case future engine experiments break it.

### Commits this session

- (session 12 writeup commit follows)

## Session 13 (2026-06-30 — custom LokiStatelessConnect override mechanism works; BaseRandomDataLengthBytes=24 hypothesis FALSIFIED; TheoryCraft's packet format is structurally different from stock UE5.4)

Session 13 built a custom UE module-level override mechanism for
StatelessConnectHandlerComponent to bypass the Launcher-install rebuild
blocker from session 12. The mechanism works correctly. But the
hypothesis it was designed to test (`BaseRandomDataLengthBytes = 24`)
was falsified by the actual server behavior — TheoryCraft's packet
format diverges from stock UE5.4 in MORE than just trailing random
padding length.

### Mechanism built (working)

Created three new files in `unreal-stub/Source/Loki/`:

- **`LokiStatelessConnect.h/.cpp`** — subclass of
  `StatelessConnectHandlerComponent` that overrides
  `IncomingConnectionless(FIncomingPacketRef PacketRef)`. When incoming
  packet exceeds `StockMaxHandshakeBits = 449` (stock's max accepted
  handshake size in bits), truncate the trailing 64 bits (8 bytes) of
  random padding and delegate to parent's IncomingConnectionless. This
  was the test of the session-11 hypothesis: bigger random padding
  should be the only difference.

- **`LokiNetDriver.h/.cpp`** — subclass of `UIpNetDriver` (UCLASS,
  UObject) that overrides `InitConnectionlessHandler()` to construct
  `LokiStatelessConnect` directly instead of going through stock's
  `Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)`
  factory. Also overrides `LowLevelSend()` to pad outgoing
  connectionless packets (detected via
  `ConnectionlessHandler->GetRawSend() == true`) with +8 random bytes
  so the client's parser would accept our replies.

- **DefaultEngine.ini** updated to register the custom NetDriver:
  ```ini
  [/Script/Engine.GameEngine]
  +NetDriverDefinitions=(DefName="GameNetDriver",
    DriverClassName="/Script/Loki.LokiNetDriver",
    DriverClassNameFallback="/Script/OnlineSubsystemUtils.IpNetDriver")
  ```

- **Loki.Build.cs** updated with `PacketHandler`,
  `OnlineSubsystemUtils`, `Sockets` deps for the new code.

### Build path: Launcher install required generating UnrealEditor-Core.lib

The added dependencies forced Loki.dll to link against
`UnrealEditor-Core.lib`, which the Launcher install doesn't ship (only
the `.dll` is included). The build failed with `LNK1181: cannot open
input file UnrealEditor-Core.lib`. Worked around by generating the
import library from the existing DLL using:

```powershell
dumpbin /exports UnrealEditor-Core.dll | grep -oE 'symbol pattern' > exports.txt
echo "LIBRARY UnrealEditor-Core" > UnrealEditor-Core.def
echo "EXPORTS" >> UnrealEditor-Core.def
cat exports.txt >> UnrealEditor-Core.def
lib /def:UnrealEditor-Core.def /machine:x64 /out:UnrealEditor-Core.lib
```

Produced a 3MB import library with 6964 exports. After this, the build
completed in 1.4 seconds and produced `UnrealEditor-Loki.dll` (97 KB,
with `UnrealEditor-Loki.pdb` for debugging).

This `dumpbin + lib /def:` workaround is generally applicable to any
missing `.lib` in a Launcher install — Core was just the first hit.
Other engine modules' `.lib` files were already present in the install's
`Intermediate/Build/Win64/x64/UnrealEditor/Development/X/` directories
(see session 12 writeup for which ones).

### Smoke test: server loaded LokiNetDriver cleanly

Server boot log:
```
LogLokiStateless: Display: LokiStatelessConnect constructed — handshake size adapter active.
LogLokiNet: Display: LokiNetDriver: connectionless handler initialized with LokiStatelessConnect.
LogNet: Name:GameNetDriver Def:GameNetDriver LokiNetDriver_0 IpNetDriver listening on port 7777
```

Our custom NetDriver loaded, our subclass was constructed, UDP 7777
listening. The DefaultEngine.ini routing worked end-to-end. The
mechanism is sound — meaning ANY future custom HandlerComponent or
NetDriver work in this project can build on this foundation without
touching engine source.

### End-to-end test: hypothesis falsified

Client launched, browse_hook fired, packets arrived. Server log:
```
NotifyAcceptingConnection accepted from: 127.0.0.1:60644
LogLokiStateless: Verbose: Truncating handshake packet from 472 bits to 408 bits
NotifyAcceptingConnection accepted from: 127.0.0.1:60644
LogLokiStateless: Verbose: Truncating handshake packet from 480 bits to 416 bits
... (more accepts and truncations)
LogLokiStateless: Verbose: Truncating handshake packet from 464 bits to 400 bits
LogNetVersion: Checksum from delegate: 3716198887
LogHandshake: Verbose: SendRestartHandshakeRequest.
LogLokiNet: Verbose: LowLevelSend: padding handshake reply 216 bits -> 280 bits
```

Truncation fired on packets >449 bits (472, 480, 464). Truncated sizes
(408, 416, 400) fell within stock UE5.4's accepted size variance. So
`ParseHandshakePacket` SHOULD have succeeded. Instead, server reached
the `else if (bHasValidSessionID)` branch (line 1440 of stock UE5.4
StatelessConnectHandlerComponent.cpp) which fires when
`bHandshakePacket = 0`. The branch's purpose is to handle non-handshake
packets from clients that might have changed address — it sends a
`RestartHandshakeRequest` to ask the client to re-establish.

So stock UE5.4's bit-13 read (which expects `bHandshakePacket` after
MagicHeader+SessionID+ClientID) is reading **0** from TheoryCraft's
packets. That's not consistent with the BaseRandomDataLengthBytes=24
hypothesis — that hypothesis predicts stock UE5.4 layout from the
start, just with bigger trailing padding.

### What the captured byte layout actually shows

Re-examining session 10's captured packets with this result in mind:

```
Byte 0:     0xBB (stable, MagicHeader)
Byte 1:     RANDOM per-packet — bit 5 distributes ~50/50 across packets
Bytes 2-5:  DC 21 A6 A3 (stable across ALL packets/sources)
Byte 6:     random
Byte 7:     0xFB (stable)
Byte 8:     varies by source IP
Bytes 9-10: 01 02 (stable)
Byte 11:    0x80/0x00 alternating
Byte 12:    incrementing per packet pair (sequence)
Bytes 13-16: F3 58 C0 6E (stable)
Bytes 17-48: 32 × 0x00 (zero-filled)
Bytes 49+:  variable tail
```

Across 17 sampled packets, byte-1 bit-5 (the position stock UE5.4
would read as `bHandshakePacket` after the 8-bit MagicHeader, 2-bit
SessionID, 3-bit ClientID) is randomly 0 or 1. If TheoryCraft used
stock format, this bit would be CONSTANT (always 1 for handshake
packets, always 0 for non-handshake). The randomness proves the bit
isn't at position 13 in TheoryCraft's format.

Stable byte 1 random + bytes 2-5 stable + byte 6 random + byte 7 stable
pattern doesn't match anything in stock UE5.4's bit-packed handshake.
The structure looks like a **wrapping layer** atop the handshake:

- Byte 0 (8 bits): MagicHeader (correctly identified)
- Byte 1 (8 bits): per-packet random — looks like a nonce, sequence
  byte, or IV byte
- Bytes 2-5 (32 bits): stable application/session identifier
- Byte 6 (8 bits): random — maybe checksum or counter
- Byte 7 (8 bits): another stable protocol byte (0xFB)
- ... and so on

This is consistent with TheoryCraft having added a custom
`HandlerComponent` to their PacketHandler chain. Stock UE5.4 supports
this via `[PacketHandlerComponents]` in DefaultEngine.ini:
```ini
[PacketHandlerComponents]
EncryptionComponent=AESGCMHandlerComponent
+Components=SomeCustomTheoryHandler
```

Each HandlerComponent in the chain wraps/unwraps packets. The
`StatelessConnectHandlerComponent` is just ONE component in the chain;
others can prepend/append bytes around it.

### Outgoing reply problem (related)

Even ignoring incoming, our outgoing `SendRestartHandshakeRequest`
reply was a stock UE5.4 packet (with our +8 random padding bytes). The
client expects TheoryCraft's wrapping bytes at the front; ours had
none. So the client received a malformed packet and likely crashed
parsing it.

### What this means for session 14

The custom-override infrastructure is the right foundation but it
needs to be applied at the **PacketHandler chain level**, not just by
subclassing StatelessConnectHandlerComponent. We need to know:

1. **What HandlerComponent(s) TheoryCraft added to their chain.** Look
   for class names in the SUPERVIVE-Win64-Shipping.exe via
   `usmapdump wstrings`/`strings` for substrings like "Loki",
   "Theory", "Cipher", "Encryption", "Signature", "Handler".

2. **The wrapping wire format**: prepend bytes (presumably), then the
   stock UE5.4 packet, then maybe append bytes too. Once known, we
   write a matching HandlerComponent in our `Loki` module that:
   - Reads the wrapping bytes in `IncomingConnectionless` and strips
     them before delegating
   - Writes the wrapping bytes in `Outgoing` before delegating

3. Possibly hook the client's PacketHandler::Initialize to log which
   components it registers (would give us the exact factory string).

### Tooling delivered (session 13)

- `unreal-stub/Source/Loki/LokiStatelessConnect.h` + `.cpp` — subclass
  with `IncomingConnectionless` override. Truncation strategy is wrong
  for current hypothesis but the framework is correct for future
  per-bit format adaptation.

- `unreal-stub/Source/Loki/LokiNetDriver.h` + `.cpp` — UCLASS subclass
  of `UIpNetDriver` that overrides `InitConnectionlessHandler` and
  `LowLevelSend`. Cleanly registered via DefaultEngine.ini. The
  `LowLevelSend` override's bRawSend-based detection is correct
  approach — it just needs the right padding bytes.

- `H:\Unreal Engine\UE_5.4\Engine\Intermediate\Build\Win64\x64\UnrealEditor\Development\Core\UnrealEditor-Core.lib`
  — generated import library, enables future builds of Loki module
  against Core symbols. NOT a backup — created from Core.dll via
  `dumpbin /exports + lib /def:`. Persists across game updates as long
  as Core.dll's export set doesn't change.

- `unreal-stub/Source/Loki/Loki.Build.cs` updated with additional
  module deps for the above.

- `unreal-stub/Config/DefaultEngine.ini` updated to route GameNetDriver
  through LokiNetDriver.

### Commits this session

- (session 13 writeup commit follows)

## Session 14 (2026-06-30 — wrapper architecture IDENTIFIED + half the handshake works: server's stock parser succeeds, SendConnectChallenge fires; client rejects our wrapped reply)

Session 14 made the biggest qualitative jump of the chapter. Identified
TheoryCraft's wire format: an 8-byte WRAPPER prepended to every UE5.4
stateless handshake packet. Built matching wrap/unwrap logic in our
LokiNetDriver/LokiStatelessConnect subclasses. Server-side path now
works end-to-end: incoming packets are wrapper-stripped, stock UE5.4's
ParseHandshakePacket succeeds, SendConnectChallenge fires (the
breakthrough signal we've been chasing for 4 sessions), and our reply
is wrapper-prepended on outgoing. But the client REJECTS our reply
with "Packet failed PacketHandler processing" within 1s — the random
wrapper bytes 1 and 6 aren't actually random; they're likely a
CRC/checksum/hash the client validates.

### How the wrapper was identified

`usmapdump wstrings` for "LokiNet" in the running SUPERVIVE process
returned 6 hits. One hit at mod-RVA `0x84F2BFE` showed the UTF-16
string `LogLokiNet`, immediately followed in `.rdata` by these raw
bytes:

```
BB 53 DC 21 A6 A3 85 FB 82 9B F5 4A 34 33 21 93
```

Cross-referenced against session 10's captured packet structure:

```
Byte 0:     0xBB         ← matches constant byte 0
Byte 1:     random       ← (53 in constant — varies per packet)
Bytes 2-5:  DC 21 A6 A3  ← matches constant bytes 2-5 EXACTLY
Byte 6:     random       ← (85 in constant — varies per packet)
Byte 7:     0xFB         ← matches constant byte 7
Bytes 8+:   variable     ← THIS is where stock UE5.4 begins
```

Bit-decoding captured bytes 8-10 (`A4 01 02`) as STOCK UE5.4 handshake
header with EMPTY inner MagicHeader:

- byte 8 = 0xA4 → LSB-first bits 0,0,1,0,0,1,0,1
  - SessionID (bits 0-1) = 0 ✓
  - ClientID (bits 2-4) = 1 ✓
  - bHandshakePacket (bit 5) = **1** ✓ (the bit we were missing in session 13!)
  - bRestartHandshake (bit 6) = 0 ✓
  - MinVersion bit 0 (bit 7) = 1
- byte 9 = 0x01 → continues MinVersion = 3 (= `EHandshakeVersion::SessionClientId`)
- byte 10 = 0x02 → CurVersion = 4 (= `EHandshakeVersion::NetCLUpgradeMessage`)

These are EXACTLY stock UE5.4 defaults. Proves the inner packet is
stock UE5.4 with no inner MagicHeader, wrapped by an 8-byte outer
TheoryCraft layer. Architecture confirmed: client uses
LokiNetSocketSubsystem (found in same string search) — a custom UE
SocketSubsystem returning custom FSocket instances that wrap/unwrap
at the FSocket level, leaving stock UE5.4's PacketHandler chain
unchanged. (Consistent with the client log showing ONLY
StatelessConnectHandlerComponent in the PacketHandler chain — no
custom HandlerComponent for wrapping.)

### What was built (working)

`LokiStatelessConnect.h/.cpp` updated:
- Override `IncomingConnectionless` to validate the 6 stable signature
  bytes (BB at 0, DC 21 A6 A3 at 2-5, FB at 7) and strip the 8-byte
  wrapper from the front before delegating to stock
  `StatelessConnectHandlerComponent::IncomingConnectionless`.
- Logs `Stripping wrapper: NNN bits -> MMM bits (wrapper bytes: ...)`
  on every stripped packet, including the actual wrapper bytes.

`LokiNetDriver.h/.cpp` updated:
- Override `LowLevelSend` (already had this from session 13).
- For `ConnectionlessHandler->GetRawSend() == true` (handshake replies):
  prepend the 8-byte wrapper. Stable bytes 0, 2-5, 7 are filled with
  the signature; random bytes 1 and 6 are filled with `FMath::Rand()`.
- Forwards to `Super::LowLevelSend` with the wrapped buffer.

`DefaultEngine.ini` updated:
- `net.MagicHeader=` (empty) — stock UE5.4 parses immediately after our
  strip, no inner magic to read.
- `net.VerifyMagicHeader=0` — disabled (no header to verify).

Build path was already established in session 13 (`UnrealEditor-Core.lib`
generated via `dumpbin`+`lib /def:`). This session's incremental
rebuild took ~8 min (first build that touches engine .gen.cpp files)
and produced UnrealEditor-Loki.dll at 14:57:27.

### Smoke test + end-to-end test signals

Server log on launch:
```
LogConfig: Set CVar [[net.MagicHeader:]]
LogConfig: Set CVar [[net.VerifyMagicHeader:0]]
LogLokiStateless: Display: LokiStatelessConnect constructed — 8-byte wrapper adapter active.
LogLokiNet: Display: LokiNetDriver: connectionless handler initialized with LokiStatelessConnect.
LogNet: Name:GameNetDriver Def:GameNetDriver LokiNetDriver_0 IpNetDriver listening on port 7777
```

After client launched with browse_hook:
```
LogNet: NotifyAcceptingConnection accepted from: 127.0.0.1:52596
LogLokiStateless: Verbose: Stripping wrapper: 464 bits -> 400 bits (wrapper bytes: BB 8B DC 21 A6 A3 1A FB)
LogHandshake: SendConnectChallenge. Timestamp: 335.113976, Cookie: 177011039060136031127150111043116139043235003104040254101107
LogLokiNet: Verbose: LowLevelSend: wrapping handshake reply 385 bits -> 449 bits
LogNet: NotifyAcceptingConnection accepted from: 169.254.83.107:49969
LogLokiStateless: Verbose: Stripping wrapper: 456 bits -> 392 bits (wrapper bytes: BB 6B DC 21 A6 A3 B3 FB)
LogHandshake: SendConnectChallenge. Timestamp: 341.609449, Cookie: 060022191047236218120253015015013031025026194130031001117165
LogLokiNet: Verbose: LowLevelSend: wrapping handshake reply 433 bits -> 497 bits
```

- ✓ Two independent connections from different local IPs both reached
  this state
- ✓ Wrapper signature validated correctly (BB, DC 21 A6 A3, FB at the
  expected offsets across multiple packets)
- ✓ Stock UE5.4 ParseHandshakePacket SUCCEEDED — confirming the
  wrapper-strip + empty-magic theory
- ✓ `SendConnectChallenge` fired — the breakthrough signal we've been
  chasing for 4 sessions
- ✓ Reply built + wrapper-prepended + sent

### Client-side rejection

```
[client] LogNet: Warning: Packet failed PacketHandler processing.
[client] LogNet: Error: PendingConnectionFailure: Your connection to the host has been lost.
```

Within 1 second of receiving our wrapped Challenge reply (much faster
than a 20s timeout). So the client RECEIVED our packet but the
PacketHandler chain rejected it during processing.

`Packet failed PacketHandler processing` is from
`NetConnection.cpp:1899` — fires when `PacketHandler::Incoming`
returns Error. In stock UE5.4, this happens when any HandlerComponent
sets `Packet.SetError()` during processing.

### Likely cause of client-side rejection

The wrapper bytes 1 and 6 (which our server filled with `FMath::Rand()`)
are probably NOT random in the actual TheoryCraft protocol. Most
plausible options:

1. **byte 1 = CRC8 of wrapper bytes 2-7** — small checksum the client
   validates at FSocket level
2. **byte 6 = CRC8 of inner packet** — checksum of the inner payload
3. **bytes 1 + 6 = some other lightweight integrity check** — e.g., a
   16-bit hash split across the two positions

If the client's FSocket subclass validates these on receive and drops
malformed packets, our reply with random values fails validation, gets
dropped at FSocket layer (before reaching PacketHandler), and the
client's StatelessConnect times out... but actually the log shows
"PacketHandler processing" failure — so the wrapper IS being stripped
at FSocket layer (otherwise wouldn't reach PacketHandler), but then
PacketHandler rejects the INNER content.

So the alternative theory: the inner packet content we send doesn't
match what the client expects. Differences could be:
- Wrong handshake version in Challenge (stock UE5.4 uses negotiated
  version; maybe our server uses Latest)
- ClientID in Challenge doesn't echo correctly
- Cookie format different than TheoryCraft expects

Both possibilities need session-15 investigation.

### Next session strategies

1. **Add hex-dump logging of outgoing reply bytes** — modify
   `LokiNetDriver::LowLevelSend` to log the actual bytes we send (both
   wrapper and inner). Compare against what stock UE5.4 should
   produce.

2. **Capture the client's RESPONSE packet to our Challenge** — if the
   client did process our Challenge before failing, it might have sent
   a ChallengeResponse. The server log would show another incoming
   packet. If yes, we know the wrapper bytes are OK (just the inner
   content differs). If no, the wrapper bytes failed validation.

3. **Hook the CLIENT's FSocket.RecvFrom or PacketHandler.Incoming** to
   log the actual bytes the client's UE pipeline receives. Compare
   against what we sent. Any pre-PacketHandler transformation (e.g.,
   FSocket wrapper strip) would be visible here.

4. **Investigate CRC/checksum candidates** for wrapper bytes 1 and 6.
   Common: CRC-8, CRC-CCITT, simple XOR sum. Computable from the
   surrounding wrapper bytes or inner packet content. Test each by
   re-running with computed values and seeing if the rejection
   changes.

### Tooling delivered (session 14)

- `unreal-stub/Source/Loki/LokiStatelessConnect.h` + `.cpp` — refined
  to strip the 8-byte wrapper (FRONT, not trailing) with signature
  validation.
- `unreal-stub/Source/Loki/LokiNetDriver.h` + `.cpp` — refined to
  prepend the 8-byte wrapper on outgoing handshake replies.
- `unreal-stub/Config/DefaultEngine.ini` — `net.MagicHeader=` (empty),
  `net.VerifyMagicHeader=0`.

### Commits this session

- (session 14 writeup commit follows)

## Session 15 (2026-06-30 — wrapper bytes 1/6 analyzed and mirrored, but client still rejects; failure is elsewhere)

Session 15 tackled the session-14 cliff (client rejecting our wrapped
reply) from two angles: brute-force analysis of captured wrapper bytes
1/6 for a pattern, and a mirroring strategy that echoes incoming b1/b6
back in the reply. The mirroring works mechanically but doesn't resolve
the client's rejection — confirming that bytes 1 and 6 are NOT the
problem.

### Byte 1/6 pattern analysis (negative result)

Parsed all 172 captured packets from `unreal-stub/Saved/Logs/udp7777-rx.log`
(session 10 capture). Tested byte 1 and byte 6 against:

- **CRC-8** with 13 polynomials × multiple init values (0, 0x55, 0xAA,
  0xBB, 0xDC, 0xFB, 0xFF) × 12 byte ranges (wrapper subsets, inner
  packet, full packet, with/without target byte). Both forward and
  reflected polynomials.
- **XOR-sum** and **SUM-mod-256** over the same ranges.
- **FNV-1a hash** over the inner packet.
- **CRC-16 CCITT** split across bytes 1+6 (16-bit pair).

ZERO matches above the 25% threshold. Byte 1 has 153 distinct values
across 172 packets (≈89% unique); byte 6 has 126 distinct values
(≈73% unique). Within a single (src, byte8, byte12) group (typically
2 packets each), b1 and b6 are ALWAYS distinct — no determinism on
visible packet state. So bytes 1/6 are effectively random per packet
(or derived from per-packet random tail entropy we can't see).

### Mirroring strategy: works mechanically, doesn't fix rejection

Added per-instance state to `LokiStatelessConnect`:
- `LastIncomingByte1`, `LastIncomingByte6`, `bHasLastIncoming` —
  captured by `IncomingConnectionless` from every received packet.

Modified `LokiNetDriver::LowLevelSend`:
- For connectionless handshake replies, mirror the last-received b1/b6
  values into the outgoing wrapper (instead of `FMath::Rand`).

Server log confirms exact mirror:
```
LokiStateless: Stripping wrapper: 456 bits -> 392 bits (wrapper bytes: BB FB DC 21 A6 A3 C3 FB)
LogHandshake: SendConnectChallenge. Timestamp: 41.741932, Cookie: ...
LokiNet: LowLevelSend: wrapping handshake reply 417 bits -> 481 bits (wrapper bytes BB FB DC 21 A6 A3 C3 FB)
```

Mirror successful: outgoing wrapper `BB FB DC 21 A6 A3 C3 FB` matches
incoming wrapper exactly.

Client side (unchanged):
```
[client] LogNet: Warning: Packet failed PacketHandler processing.
[client] LogNet: Error: PendingConnectionFailure: Your connection to the host has been lost.
```

**Same rejection mode as session 14**. So bytes 1 and 6 are NOT what
the client validates.

### What the client log tells us

```
LogHandshake: Stateless Handshake: NetDriverDefinition 'GameNetDriver' CachedClientID: 7
LogNetVersion: Loki 1.0.0.0, NetCL: 0, EngineNetworkVersion: 34, GameNetworkVersion: 0 (Checksum: 3716198887)
```

- Client's `CachedClientID = 7` (bumped from 0 last session — every
  new connection per `GameNetDriver` definition increments it).
- Client's `NetworkChecksum = 3716198887` (matches our server's
  override).
- Client's PacketHandler chain has ONLY stock StatelessConnect
  (confirmed: no custom HandlerComponent — wrapping is at FSocket
  level as suspected).

### Where the rejection actually originates

`"Packet failed PacketHandler processing"` fires from
`NetConnection.cpp:1899` when `PacketHandler::Incoming` returns Error.
The handler chain has only StatelessConnect, so StatelessConnect's
`Incoming` must be setting `Packet.SetError()`.

Stock UE5.4 `StatelessConnectHandlerComponent::Incoming` (line 947+):
1. Reads MagicHeader (none, empty config)
2. Reads SessionID + ClientID + handshake bit
3. If handshake bit set, calls `ParseHandshakePacket`
4. If valid Challenge, calls `SendChallengeResponse`

Possible error paths inside this flow:
- Size variance check inside `ParseHandshakePacket` fails (returns
  false, sets `Packet.SetError()`)
- `CachedClientID` mismatch — but server echoes back the same ClientID
  client sent, so should match
- `CachedGlobalNetTravelCount` mismatch — server has GlobalNetTravelCount=0,
  matches client's initial value
- Cookie format / size mismatch
- Some validation we haven't traced

### Three remaining hypotheses for session 16

1. **Server-direction wrapper differs from client-direction.**
   Captured packets are all CLIENT→SERVER. Maybe SERVER→CLIENT packets
   have different signature bytes (e.g., byte 0 = 0xCC instead of
   0xBB, or different stable bytes). Our reply mirrors the CLIENT's
   format — wrong for server-direction. **Verification approach**:
   hook the CLIENT's FSocket.RecvFrom to log incoming wrapper bytes
   when our reply arrives. Compare to what we sent.

2. **Inner Challenge has a subtle content mismatch.** Stock UE5.4
   SendConnectChallenge builds the packet from current server state.
   Maybe a specific field (e.g., HandshakeVersion in Challenge,
   Timestamp encoding, Cookie size if TheoryCraft modified
   COOKIE_BYTE_SIZE) doesn't match what TheoryCraft expects.
   **Verification approach**: dump our outgoing INNER bytes (post-wrap-strip
   equivalent) and bit-decode against captured client→server Initial
   bytes. Look for structural differences.

3. **PacketHandler.Incoming termination-bit detection failing.** Stock
   UE5.4 PacketHandler::Incoming_Internal expects the last byte to
   have a termination bit (high bit set). If our wrapping changes the
   last-byte structure somehow, client gets garbage bit count.
   **Verification approach**: log the actual byte we send as final
   byte. Should have high bit set.

### Plan for session 16

- **Step 1**: Add hex dump of our outgoing INNER bytes (the actual
  Challenge content, pre-wrap) to `LokiNetDriver::LowLevelSend`.
  Cross-reference with bit-decoded captured client→server bytes.
  Identify what (if anything) we send that's structurally different.

- **Step 2**: If inner content looks OK, hook the CLIENT side to
  observe the rejection in real-time. Two options:
  - Cheaper: hook `PacketHandler::Incoming` entry in the CLIENT's
    UnrealEditor-Engine.dll equivalent (statically linked in the
    SUPERVIVE binary; can find via xref to "Packet failed PacketHandler
    processing" string at NetConnection.cpp:1899 location).
  - Heavier: build a DLL that hooks the CLIENT's FSocket.RecvFrom and
    logs the post-strip bytes. Compare to what our server sent.

- **Step 3**: If hypothesis 1 (server-direction wrapper) is the answer,
  test by manually setting wrapper bytes to different values (e.g.,
  0xCC at position 0 instead of 0xBB) and see if the client's
  rejection mode changes.

### Tooling delivered (session 15)

- `unreal-stub/Source/Loki/LokiStatelessConnect.h` + `.cpp` — added
  `LastIncomingByte1/6` + `bHasLastIncoming` state, captured in
  `IncomingConnectionless`.
- `unreal-stub/Source/Loki/LokiNetDriver.cpp` — `LowLevelSend` now
  mirrors incoming b1/b6 into outgoing wrapper. Also logs the full
  outgoing wrapper bytes for debugging.
- `scratchpad/analyze_packets.py` + `analyze_v2.py` + `analyze_v3.py`
  — Python tools for byte-pattern analysis. Reusable for future
  byte-formula investigations.

### Commits this session

- (session 15 writeup commit follows)

## Session 16 (2026-06-30 — outgoing inner bytes captured + bit-decoded; PERFECTLY stock UE5.4 Challenge format; rejection cause is above the inner-content layer)

Session 16 added hex-dump logging to LokiStatelessConnect (incoming
wrapper-strip side) and LokiNetDriver (outgoing wrap side), captured the
exact bytes of both directions during a real client-server exchange,
and bit-decoded them against stock UE5.4 protocol expectations. The
conclusion is decisive: our outgoing Challenge is a PERFECTLY formed
stock UE5.4 packet. The client's rejection has nothing to do with the
inner content — it must be at a layer above (wrapper direction
asymmetry, undocumented MAC, or LokiNet-FSocket validation).

### Captured packets

Server log after running stub + client with `-Hook`:

```
LokiStateless: Stripping wrapper: 504 bits -> 440 bits (wrapper bytes: BB 0B DC 21 A6 A3 4C FB)
LokiStateless: Stripping wrapper: full 63 bytes: BB 0B DC 21 A6 A3 4C FB BC 01 02 80 80 F3 58 C0 6E 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 18 00 48 60 BE 7A 29 9E 85 51 0C D3 5E FC 08 A1
LogHandshake: SendConnectChallenge. Timestamp: 38.151915, Cookie: 125217138189072171241138143138202028068102208254010167217056
LokiNet: LowLevelSend: wrapping handshake reply 433 bits -> 497 bits (wrapper bytes BB 0B DC 21 A6 A3 4C FB)
LokiNet: LowLevelSend: full 63 bytes: BB 0B DC 21 A6 A3 4C FB BC 01 82 80 80 F3 58 C0 6E 00 00 00 00 10 F5 71 13 43 40 7D D9 8A BD 48 AB F1 8A 8F 8A CA 1C 44 66 D0 FE 0A A7 D9 38 B4 03 BA DA D2 8E 35 9F 39 44 BF D0 3D 61 21 01
```

### Bit-decoded incoming Initial (client→server)

After stripping the 8-byte wrapper:

```
SessionID                 = 0
ClientID                  = 7
bHandshakePacket          = 1
bRestartHandshake         = 0
MinVersion                = 3  (SessionClientId)
CurVersion                = 4  (NetCLUpgradeMessage)
HandshakePacketType       = 0  (InitialPacket)
SentHandshakePacketCount  = 1
LocalNetworkVersion       = 3716198887       ← matches client log
LocalNetworkFeatures      = 0x0000
SecretIdPad               = 0
PacketSizeFiller (28 B)   = 00 00 00 00 ... (all zeros — correct for Initial)
random tail (16 bytes)    = 18 00 48 60 BE 7A 29 9E 85 51 0C D3 5E FC 08 A1
```

EXACT stock UE5.4 Initial format with TheoryCraft's expected defaults.

### Bit-decoded outgoing Challenge (server→client, our reply)

After stripping the 8-byte wrapper:

```
SessionID                 = 0
ClientID                  = 7                ← correctly echoed from incoming
bHandshakePacket          = 1
bRestartHandshake         = 0
MinVersion                = 3
CurVersion                = 4
HandshakePacketType       = 1  (Challenge)   ← correctly toggled from Initial
SentHandshakePacketCount  = 1                ← correctly echoed
LocalNetworkVersion       = 3716198887       ← matches our override
LocalNetworkFeatures      = 0x0000
ActiveSecret              = 0
Timestamp                 = 38.151915200054646  ← matches server log "Timestamp: 38.151915"
Cookie (20 bytes)         = 7D D9 8A BD 48 AB F1 8A 8F 8A CA 1C 44 66 D0 FE 0A A7 D9 38  ← matches server log
```

Byte-by-byte diff vs incoming shows ONLY these (all expected):
- Byte 10: 0x02 → 0x82 (HandshakePacketType Initial=0 → Challenge=1, bit 23 flip)
- Bytes 21-46: Initial's zeros → Challenge's Timestamp+Cookie
- Bytes 47-62: Different random padding (per-packet, expected)

**The Challenge packet our server sends is a textbook stock UE5.4 Challenge.**

### Architecturally, this packet should be accepted

Per stock UE5.4 source:
- `bHasValidClientID = (ClientID == CachedClientID)` → Client has CachedClientID=7
  (per client log), our reply has ClientID=7 → MATCH
- `bHasValidSessionID = (SessionID == CachedGlobalNetTravelCount)` → Client has
  CachedGlobalNetTravelCount=0 (fresh), our reply has SessionID=0 → MATCH
- `bIsChallengePacket = (HandshakePacketType == Challenge && Timestamp > 0.0)`
  → both true → would trigger SendChallengeResponse on client
- Cookie format: stock UE5.4 GenerateCookie → 20 bytes ✓

Yet the client rejects with `Packet failed PacketHandler processing`.

### Three remaining hypotheses

1. **Wrapper has DIRECTION-asymmetric stable bytes.** Captured packets
   are all CLIENT→SERVER. We've been MIRRORING the client's wrapper
   format in our SERVER→CLIENT replies. Maybe the wrapper signature
   bytes (0xBB at byte 0, DC 21 A6 A3 at bytes 2-5, 0xFB at byte 7)
   are CLIENT-ORIGIN markers. The SERVER's wrapper might need
   DIFFERENT stable bytes (e.g., 0xCC at byte 0, or different
   signature) to identify it as server-origin.

2. **Crypto/MAC layer below the wrapper.** The wrapper bytes 1 and 6
   (which we established are NOT a CRC of visible content) might be
   keyed-hash output of some hidden state. The client validates them.
   Our mirrored values from the client's outgoing don't match what
   the client expects for incoming-from-server.

3. **LokiNet-FSocket-level packet validation.** The custom FSocket
   subclass (which we couldn't find by name searching) implements
   wrap/unwrap. Its unwrap might check more than just the visible
   signature bytes — maybe inspects packet size, address-derived
   token, or per-connection state.

### How to discriminate

- For hypothesis #1: try setting outgoing wrapper byte 0 to different
  values (CC, AA, BB+server-flag-bit-set, etc.) and see if client
  rejection mode CHANGES. If client logs different errors, byte 0 IS
  validated.
- For hypothesis #2/#3: hook the client's UE code to log what its
  FSocket.RecvFrom returns vs what the PacketHandler.Incoming sees.
  Compare to identify if any layer strips/transforms before PacketHandler.

### Next session strategies

**Cheap experiment to start session 17 with:** vary the outgoing
wrapper byte 0 (try CC, then AA, then leave as BB). If any variation
causes the client to behave differently (longer connection time,
different log message, no rejection), we've found a validation point.

**If experimentation doesn't reveal:** build a CLIENT-side hook DLL
that intercepts `FBitReader::SetData` or the `PacketHandler::Incoming`
entry in the SUPERVIVE binary, dumps what it sees, and logs the
specific point of rejection. Uses existing `tools/inject` infrastructure
similar to browse_hook. ~3-5 hours work.

### Tooling delivered (session 16)

- `unreal-stub/Source/Loki/LokiNetDriver.cpp` — `LowLevelSend` now
  also dumps full outgoing packet hex.
- `unreal-stub/Source/Loki/LokiStatelessConnect.cpp` —
  `IncomingConnectionless` now also dumps full incoming packet hex.
- `scratchpad/decode_packets.py` — bit-decoder for stock UE5.4
  handshake packets (incoming Initial + outgoing Challenge variants).
  Reusable for future packet analysis.

### Commits this session

- (session 16 writeup commit follows)

## Session 17 (2026-06-30 → 2026-07-01 — STATELESS HANDSHAKE COMPLETES END-TO-END; new blocker at UNetConnection's own PacketHandler chain)

Massive session. Went from "client outright rejects our reply in 1s" to
"full stateless handshake completes, UNetConnection created, expecting
NMT_Hello". Discovered THREE distinct facts about TheoryCraft's LokiNet
architecture, each unblocking a previous blocker.

### Discovery 1: 16-byte constant encodes BOTH directions

Re-examined the `LogLokiNet` constant we found in session 14 (mod-RVA
`0x84F2C10` in SUPERVIVE-Win64-Shipping.exe):

```
BB 53 DC 21 A6 A3 85 FB | 82 9B F5 4A 34 33 21 93
└─ client→server ─────┘   └─ server→client ────┘
```

Sessions 14-16 mirrored bytes 0-7 in our server-direction replies →
client kept rejecting. Session 17 first attempt used bytes 8-15 as
server-direction signature. Client's rejection MODE changed
immediately:

- Sessions 14-16: `Packet failed PacketHandler processing` →
  `PendingConnectionFailure` within 1s (fatal outright rejection)
- Session 17: client stayed alive for full 30-second UE5.4 handshake
  timeout, sent Initial retries at 1Hz, then timed out with
  `ConnectionTimeout` (normal handshake failure, not fatal rejection)

Server-direction wrapper is a real thing. Bytes 0-7 of the constant
are the CLIENT→SERVER template; bytes 8-15 are the SERVER→CLIENT
template. Byte 0 = `0xBB` (client), `0x82` (server). Byte 7 = `0xFB`
(client), `0x93` (server). Bytes 2-5 stable signature per direction,
bytes 1 and 6 random per packet.

### Discovery 2: Fixed vs random for bytes 1/6 doesn't matter

Session 17 second attempt used the LITERAL constant bytes 1/6 values
(`0x9B` and `0x21`) instead of random. Client behavior UNCHANGED —
same 30-second timeout. So bytes 1/6 are truly per-packet random nonce
(as our 172-packet analysis in session 15 suggested).

### Discovery 3: The client accepts UNWRAPPED replies too

Session 17 third attempt DISABLED the outgoing wrap entirely
(`bDisableOutgoingWrap = true`) — server sends raw stock UE5.4
handshake packets, no wrapper at all. **The client accepted them AND
completed the handshake.** Server log:

```
LogHandshake: SendConnectChallenge. Timestamp: 34.076447, Cookie: ...
LogHandshake: SendChallengeAck. InCookie: 009129133243...
LogNet: Server accepting post-challenge connection from: 127.0.0.1:58828
LogNet: IpConnection_0 setting maximum channels to: 32767
PacketHandlerLog: Loaded PacketHandler component: Engine.EngineHandlerComponentFactory (StatelessConnectHandlerComponent)
LogNet: SetClientLoginState: State changing from Invalid to LoggingIn
LogNet: SetExpectedClientLoginMsgType: Type same: [0]Hello
LogNet: NotifyAcceptedConnection: [UNetConnection] RemoteAddr: 127.0.0.1:58828, IpConnection_0
LogNet: AddClientConnection: Added client connection
```

**Every checkpoint of the stock UE5.4 stateless handshake fires** —
Challenge sent → Response received → Ack sent → UNetConnection created
→ expecting `NMT_Hello`. This is the state we've been chasing since
session 8 of the chapter.

The architecture inference: TheoryCraft's LokiNetSocketSubsystem
`RecvFrom` conditionally strips wrapper (accepts unwrapped) but always
wraps `SendTo`. So the client can talk to either wrapped or unwrapped
servers.

### Discovery 4 (new blocker): UNetConnection has its OWN PacketHandler chain with stock StatelessConnect

After UNetConnection creation, next packet from client fails within
27ms:

```
LogHandshake: Incoming: Error reading handshake packet.
LogNet: Warning: Packet failed PacketHandler processing.
LogNet: UNetConnection::Close: [UNetConnection] ... Result=PacketHandlerIncomingError
LogNet: SetClientLoginState: State changing from LoggingIn to CleanedUp
```

Root cause: `UNetConnection::InitHandler` (NetConnection.cpp:687-712)
creates its OWN `PacketHandler` chain and hardcodes
`Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)`
— **the stock class, NOT our `LokiStatelessConnect`**. Our subclass
only handled connectionless packets via `LokiNetDriver`'s
`ConnectionlessHandler` (server-driver level). The
UNetConnection-level chain is separate.

Post-handshake, the client still wraps outgoing packets. Byte 8 of the
inner packet has `bHandshakePacket=0` (post-handshake game data), but
the WRAPPER byte 0 = `0xBB` reads as `bHandshakePacket=1` at the stock
StatelessConnect layer. Stock code sees "handshake" → calls
`ParseHandshakePacket` on garbage → `Incoming: Error reading handshake
packet` (line 1202) → connection killed.

Attempted a fix in-session by overriding `LokiStatelessConnect::Incoming`
too, but it doesn't fire because the UNetConnection instantiates stock
StatelessConnect, not our subclass.

### Client-side signal that we're close

Client log at 00:25:19.132 shows the client's own `LogHandshake:
Stateless Handshake: NetDriverDefinition 'GameNetDriver'
CachedClientID: 7` moments before the server-side handshake succeeds.
Client kept the connection alive for 9 seconds after handshake before
crashing at 00:19:36 (during `sendReply` → server-side connection
already closed).

### Session 18 plan

Need to make the UNetConnection's PacketHandler use our
LokiStatelessConnect subclass. Options in order of preference:

1. **Subclass UIpConnection + override InitHandler** — override the
   connection's PacketHandler chain init to add
   `LokiStatelessConnect` directly. Register the subclass as
   `NetConnectionClass` in `LokiNetDriver` so
   `Driver->InternalCreateChildConnection` spawns our subclass.
   Cleanest option.

2. **Subclass UIpConnection + override ReceivedRawPacket** — intercept
   incoming packets before the PacketHandler chain and strip the
   wrapper. Then delegate to `Super::ReceivedRawPacket`. Simpler if
   InitHandler isn't virtual.

3. **Swap the StatelessConnect component post-init** — after
   InitHandler runs with stock, swap
   `StatelessConnectComponent.Pin()` with a fresh
   `LokiStatelessConnect`. Fragile — much state would need copying.

### Tooling delivered (session 17)

- `unreal-stub/Source/Loki/LokiStatelessConnect.h` + `.cpp` — added
  `ServerToClientByte*` constants + `Incoming(FBitReader&)` override
  that also strips the wrapper. The Incoming override doesn't fire on
  UNetConnection-level packets yet (subclass isn't wired up there),
  but the logic is ready for session 18.

- `unreal-stub/Source/Loki/LokiNetDriver.cpp` — `LowLevelSend` now has
  `bDisableOutgoingWrap = true` constexpr, sending raw stock UE5.4
  handshake replies. Confirmed the client accepts them.

- `scratchpad/analyze_packets.py`, `analyze_v2.py`, `analyze_v3.py`,
  `decode_packets.py` — reusable analysis tools.

### Commits this session

- (session 17 writeup commit follows)

## Session 18 (2026-06-30 → 2026-07-01 — UNetConnection PACKET HANDLER WIRED; client reaches Welcomed with 3 channels)

Session 17's blocker was that `UNetConnection::InitHandler`
(UE5.4 NetConnection.cpp:687-712) hardcodes the stock
`StatelessConnectHandlerComponent` factory string, so our
`LokiStatelessConnect` never got installed at the per-connection
layer. Session 18 fixes this by subclassing `UIpConnection`,
overriding `InitHandler`, and pointing `NetConnectionClass` at the
subclass in the `ULokiNetDriver` constructor.

### The fix

Three touched files:

- `unreal-stub/Source/Loki/LokiIpConnection.h + .cpp` (new) — subclass
  of `UIpConnection`. Overrides `InitHandler` to replicate stock
  UE5.4 `UNetConnection::InitHandler` verbatim EXCEPT for one line:
  instead of calling
  `Handler->AddHandler(TEXT("Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)"), true)`,
  we construct `LokiStatelessConnect` directly and pass it to the
  overload `Handler->AddHandler(TSharedPtr<HandlerComponent>&, bool)`.
  All the other stock init plumbing (mode selection, `NotifyAddHandler`
  lambda binding `InitFaultRecovery`, `InitializeDelegates`,
  `NotifyAnalyticsProvider`, `Initialize`, cast to
  `StatelessConnectComponent`, `SetDriver`,
  `SetHandshakeFailureCallback` for `WrongVersion` upgrade,
  `InitializeComponents`, and `MaxPacketHandlerBits` write-back) is
  preserved bit-for-bit.

- `unreal-stub/Source/Loki/LokiNetDriver.h + .cpp` — added a
  `(const FObjectInitializer&)` constructor that sets
  `NetConnectionClass = ULokiIpConnection::StaticClass()` before
  `UNetDriver::InitConnectionClass()` runs. `InitConnectionClass`
  early-outs when `NetConnectionClass != NULL`, so our assignment
  wins over the config default (`IpConnection`).

Build succeeded (72s total, 8 actions).

### Result: HANDSHAKE + LOGIN + WELCOME all complete

Stub server log with `LogLokiIpConnection Verbose` added to `-LogCmds`
(new log category from the new file). See
[docs/session-18-stub-log-excerpt.txt](session-18-stub-log-excerpt.txt)
for the filtered sequence. Key lines:

```
LogHandshake: SendConnectChallenge. Cookie: 232103...
LogHandshake: SendChallengeAck. InCookie: 232103...
LogNet: Server accepting post-challenge connection from: 127.0.0.1:57753
LogNet: LokiIpConnection_0 setting maximum channels to: 32767       ← OUR SUBCLASS
LogLokiStateless: LokiStatelessConnect constructed — 8-byte wrapper adapter active.
LogLokiIpConnection: LokiIpConnection: per-connection PacketHandler initialized with LokiStatelessConnect (reserved bits: 7).
LogNet: SetClientLoginState: State changing from Invalid to LoggingIn
LogNet: NotifyAcceptedConnection: [UNetConnection] Name: LokiIpConnection_0
LogNet: AddClientConnection: Added client connection: LokiIpConnection_0
LogLokiStateless: [Incoming] Stripping wrapper: 299 bits -> 235 bits (wrapper bytes: BB 75 DC 21 A6 A3 DF FB)
LogNet: SetExpectedClientLoginMsgType: Type changing from [0]Hello to [5]Login   ← NMT_Hello received
LogLokiStateless: [Incoming] Stripping wrapper: 817 bits -> 753 bits (wrapper bytes: BB A4 DC 21 A6 A3 FA FB)
LogNet: SetClientLoginState: State changing from LoggingIn to Welcomed           ← NMT_Login/Welcome
LogLokiStateless: [Incoming] Stripping wrapper: 136 bits -> 72 bits
LogLokiStateless: [Incoming] Stripping wrapper: 301 bits -> 237 bits
LogNet: UChannel::CleanUp: ChIndex == 0.
LogNet: UNetConnection::Close: ... Channels: 3
LogNet: UNetConnection::PendingConnectionLost.
LogNet: SetClientLoginState: State changing from Welcomed to CleanedUp
```

Every predicted checkpoint from the session-18 plan fires:

- Server side loads OUR `LokiStatelessConnect` (not stock) in the
  UNetConnection's PacketHandler chain
- Our `Incoming(FBitReader&)` override fires on post-handshake packets
  and cleanly strips the 8-byte wrapper (`BB ?? DC 21 A6 A3 ?? FB`)
- Client's `NMT_Hello` is received (state Hello → Login)
- Client's `NMT_Login` is received, server sends `NMT_Welcome`, state
  moves LoggingIn → Welcomed
- 3 UE control channels open (Control + probably map + game state)
- Connection lives 113ms end-to-end from Initial to close (was 27ms
  in session 17)

### New blocker: post-Welcome client-side disconnect

After Welcomed state and 3 channels, the client sent one more bunch
(301 bits → 237 bits post-strip) then closed the connection cleanly
(`PendingConnectionLost` from client's side, `Channels: 3`,
`bPendingDestroy=0`). The disconnect is client-initiated. Most likely
cause: the client sent `NMT_Join` expecting a specific map/game
package to load, but our stub's `Entry` map is empty and doesn't
match the client's expected `LobbyV2` scaffold, so the client's
`UPendingNetGame::LoadMapCompleted` decided not to proceed.

This is NORMAL UE dev work now, not protocol reverse-engineering. The
stateless handshake is completely solved. From here forward this is a
standard "author a listen server that matches what your client's
control channel expects" problem. Session 19+ will:

1. Look at the client's UE log around the disconnect for the specific
   `NMT_*` message that failed or the map/package name it complained
   about.
2. Author minimal listen-server plumbing (GameMode, GameState, PC
   class) matching what the client expects to load.
3. Get to the point where the client reaches "menu populated" state
   with data replicated from our stub server.

### Tooling delivered (session 18)

- `unreal-stub/Source/Loki/LokiIpConnection.h + .cpp` — the new
  UIpConnection subclass with `InitHandler` override.
- `unreal-stub/Source/Loki/LokiNetDriver.h + .cpp` — constructor sets
  `NetConnectionClass` to route per-connection instantiation to
  `ULokiIpConnection`.
- `docs/session-18-stub-log-excerpt.txt` — filtered stub log showing
  the end-to-end handshake+login+welcome sequence.

### Chapter state (end of session 18)

- Handshake: **DONE** (session 17)
- Post-handshake packet-handler wiring: **DONE** (session 18)
- NMT_Hello / NMT_Login / NMT_Welcome control-channel messages:
  **DONE** (session 18 — reached Welcomed with 3 channels open)
- Post-Welcome map/GameMode acceptance: TODO (session 19)
- Replicating hero-roster / mission / store data to the client: TODO
  (session 20+)

### Commits this session

- (session 18 writeup commit follows)

## Session 19 (2026-07-01 — client reaches JOIN SUCCEEDED, PC spawns server-side; new blocker at client-side ActorChannel spawn)

Session 18 unblocked the UNetConnection-level PacketHandler wiring. Client
completed handshake through Welcomed with 3 channels, then cleanly closed the
control channel. Session 19 identified WHY (client's `MakeSureMapNameIsValid`
rejected our stub's `/Engine/Maps/Entry` map name because Entry is editor-only
content not in the cooked shipping build) and fixed it in two independent
layers.

### Fix 1: ULokiGameInstance::ModifyClientTravelLevelURL override

Added `unreal-stub/Source/Loki/LokiGameInstance.h + .cpp` — subclass of
UGameInstance that overrides `ModifyClientTravelLevelURL(FString&)`.
`UWorld::WelcomePlayer` calls this hook by reference right before sending
`NMT_Welcome` (World.cpp:6201-6204), giving us a clean seam to rewrite the
LevelName without patching engine source. Rewrite target:
`/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent` — the exact path the client
browsed to via browse_hook, guaranteed to exist in its cooked packages.

Registered via DefaultEngine.ini:
```
[/Script/EngineSettings.GameMapsSettings]
GameInstanceClass=/Script/Loki.LokiGameInstance
```

### Fix 2: FWorldDelegates::OnPostWorldInitialization — rename world package + object

Fix 1 alone got the client to send `NMT_Netspeed`, then still crashed at the
actor channel for the server-spawned PlayerController. Root cause: our stub's
world still LIVES at `/Engine/Maps/Entry.Entry`, so the server-spawned actor's
full path is `/Engine/Maps/Entry.Entry:PersistentLevel.PlayerController_0` —
which is what gets replicated in the NetGUID hierarchy. Client can't resolve
`/Engine/Maps/Entry.Entry` (editor-only, not cooked) → `SerializeNewActor`
fails at `Archetype == null` → `NMT_ActorChannelFailure(ChIndex=3)` back to
server → PC channel breaks → connection closes.

Fix: added `FWorldDelegates::OnPostWorldInitialization` hook to `Loki.cpp`
that renames the game world's OUTER PACKAGE AND WORLD OBJECT to the client's
expected path:
- Package: `/Engine/Maps/Entry` → `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent`
- World object: `Entry` → `LVL_LobbyV2_Persistent`

Uses `UPackage::Rename` and `UWorld::Rename` with
`REN_ForceNoResetLoaders | REN_DoNotDirty | REN_DontCreateRedirectors`. Fires
once at server startup after world init, before any client connects. Verified
in log:
```
LogLokiStub: Renaming game world package: /Engine/Maps/Entry -> /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent
LogLokiStub: Renaming world object: Entry -> LVL_LobbyV2_Persistent
LogWorld: Bringing World /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.LVL_LobbyV2_Persistent up for play
```

Server-spawned actor paths now look like:
```
PlayerController /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_0
```

### Result: end-to-end sequence through Join succeeded

Server log (`docs/session-19-stub-log-excerpt.txt`):
```
LogNet: Server accepting post-challenge connection from: 127.0.0.1:54720
LogNet: NotifyAcceptingChannel Control 0 server World /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.LVL_LobbyV2_Persistent: Accepted
LogNet: Login request: ?Name=9b9d2c887e2524f918e383a895f2f1c2 ...
LogLokiGameInstance: ModifyClientTravelLevelURL: /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent -> (same)
LogNet: SetClientLoginState: State changing from LoggingIn to Welcomed
LogNet: Join request: /Engine/Maps/Entry?Name=9b9d... ?SplitscreenCount=1
LogNet: Join succeeded: 9b9d2c887e2524f918e3                              ← NEW MILESTONE
LogNet: SetClientLoginState: State changing from Welcomed to ReceivedJoin ← NEW MILESTONE
LogNet: Server connection received: ActorChannelFailure 3
LogNet: Actor channel failed: PlayerController .../LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_0
LogNet: SetClientLoginState: State changing from ReceivedJoin to CleanedUp
```

Every checkpoint through NMT_Login → NMT_Welcome → NMT_Netspeed → NMT_Join →
GameMode.PostLogin → PlayerController spawn now fires. Server successfully
opens 8 channels for the connection. Then the client's `SerializeNewActor`
fails on channel 3 (the PC) and sends NMT_ActorChannelFailure back, causing
teardown.

### New blocker (session 20): client-side SerializeNewActor for PlayerController

`Server connection received: ActorChannelFailure` decodes to
`NMT_ActorChannelFailure(int32 ChannelIndex)` sent from
`UPackageMapClient::SerializeNewActor` at PackageMapClient.cpp:3151 when
`SerializeNewActor` returns null actor. The client-side failure paths from
PackageMapClient.cpp:611-758:
- `Unresolved Archetype GUID. Guid not registered`
- `SerializeNewActor: Failed to spawn actor for NetGUID` (SpawnActorAbsolute returned null)
- `SerializeNewActor: Actor level has invalid world (may be streamed out)`

The number `3` in `ActorChannelFailure 3` is the CHANNEL INDEX (not a reason
code) — channel 3 is the PC actor channel.

Most likely causes:
1. Server-spawned PC is stock `APlayerController` but client's LobbyV2 map
   loaded a specific `ALokiLobbyPlayerController` class via its cooked
   GameMode — class-GUID resolution mismatch.
2. PC's replicated subobjects (PlayerState, HUD, etc.) fail to resolve.
3. Client's LobbyV2 map's GameMode is stricter about PC classes.

### Session 20 plan

Investigate client-side actor spawn failure. Add `LogNetPackageMap Log` to
the client via `-LogCmds` (won't help — client is shipping and log verbosity
is compiled out). Better: attach a debugger or look at `Loki.log` for any
client-side actor spawn errors — the client does emit warnings.

Alternative: override the server's `GameMode.PlayerControllerClass` to match
what the client's LobbyV2 GameMode expects. Requires:
1. Discovering the client's LobbyV2 GameMode class name (usmapdump strings
   the exe for `ALokiLobbyGameMode` or similar)
2. Creating a stub PC subclass of the client's expected PC class in our Loki
   module
3. Registering it via `AGameModeBase::PlayerControllerClass` in a custom
   GameMode

Alternatively: keep server PC as stock APlayerController but investigate
whether the client's LobbyV2 map has a bunch of level-persistent actors that
need to exist server-side too (level actor replication).

### Tooling delivered (session 19)

- `unreal-stub/Source/Loki/LokiGameInstance.h + .cpp` — GameInstance subclass
  with `ModifyClientTravelLevelURL` override rewriting LevelName in NMT_Welcome.
- `unreal-stub/Source/Loki/Loki.cpp` — added `OnPostWorldInitialization` hook
  that renames the game world's package + object to
  `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.LVL_LobbyV2_Persistent`.
- `unreal-stub/Config/DefaultEngine.ini` — added
  `[/Script/EngineSettings.GameMapsSettings] GameInstanceClass=/Script/Loki.LokiGameInstance`.
- `docs/session-19-stub-log-excerpt.txt` — filtered server log showing
  world-rename + Join succeeded + ActorChannelFailure sequence.

### Chapter state (end of session 19)

- Handshake: **DONE** (session 17)
- Post-handshake packet-handler wiring: **DONE** (session 18)
- NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: **DONE** (session 18)
- Post-Welcome map validation: **DONE** (session 19, via ModifyClientTravelLevelURL)
- NMT_Join / GameMode.PostLogin / PC spawn (server side): **DONE** (session 19, via world/object rename)
- Client-side PC actor spawn: TODO (session 20 — class mismatch or subobject resolution)
- Replicating hero-roster / mission / store data to the client: TODO (session 21+)

### Commits this session

- (session 19 writeup commit follows)

## Session 20 (2026-07-01 — client PC ACTOR SPAWNS; new blocker at RPC signature mismatch)

Session 19's blocker was `ActorChannelFailure(3)` — client couldn't instantiate
the server-replicated PlayerController. Session 20 identified the root cause
from client-log `LogNetPackageMap` warnings AND fixed it in one line.

### Root cause: per-class NetworkChecksum mismatch

Client's Loki.log after session-19 test showed:
```
LogNetPackageMap: Warning: GetObjectFromNetGUID: Network checksum mismatch.
    FullNetGUIDPath: /Script/Engine.Default__PlayerController, 2497074788, 939521608
LogNetPackageMap: Warning: ... Default__HUD, 2302596731, 388723456
LogNetPackageMap: Warning: ... Default__DefaultPawn, 1041852434, 1673433460
LogNetPackageMap: Warning: ... Default__GameStateBase, 2773682451, 1156806299
LogNetPackageMap: Warning: ... GameModeBase, 2302596731, 388723456
LogNetPackageMap: Warning: ... SpectatorPawn, 1041852434, 1673433460
LogNetPackageMap: Warning: ... Default__PlayerState, 264646587, 96879716
LogNetPackageMap: Error: SerializeNewActor. Unresolved Archetype GUID. Path: Default__PlayerController
LogNet: Warning: Network Failure: GameNetDriver[NetChecksumMismatch]
```

Every stock replicated class had a checksum mismatch. SUPERVIVE ships modified
engine base classes (extra replicated properties on APlayerController,
APlayerState, AGameStateBase, AGameModeBase, AHUD, ADefaultPawn, ASpectatorPawn)
— so their schema fingerprints differ from stock UE5.4's.

### Fix: server sets NetworkChecksumMode=None

`UPackageMapClient::SerializeExportInternal` (PackageMapClient.cpp:883) omits
`bHasNetworkChecksum` from the ExportFlags when `NetworkChecksumMode == None`.
`UPackageMapClient::GetObjectFromNetGUID` (PackageMapClient.cpp:3633) skips the
checksum comparison when `CacheObjectPtr->NetworkChecksum == 0`. So if the
server doesn't send the checksum, the client doesn't check it.

Added `ULokiNetDriver::InitBase` override that calls
`GuidCache->SetNetworkChecksumMode(FNetGUIDCache::ENetworkChecksumMode::None)`
right after `Super::InitBase` creates the cache. Three lines total:

```cpp
if (GuidCache.IsValid()) {
    GuidCache->SetNetworkChecksumMode(FNetGUIDCache::ENetworkChecksumMode::None);
}
```

Attempted first via client-side `-ExecCmds="net.IgnoreNetworkChecksumMismatch 1"`
— the CVar didn't take effect (SUPERVIVE's shipping build likely ignores
`-ExecCmds` or the CVar is set too late). Server-side omission works.

### Result: PC actor spawns client-side; new blocker at RPC signature mismatch

Server log (`docs/session-20-stub-log-excerpt.txt`):
```
LogLokiNet: NetworkChecksumMode set to None (bypasses per-class schema fingerprint check on client).
...
LogNet: Join succeeded: 9b9d2c887e2524f918e3
LogNet: SetClientLoginState: Welcomed -> ReceivedJoin
[LokiStateless] Incoming: 136 bits -> 72 bits (a client bunch)
[LokiStateless] Incoming: 2958 bits -> 2894 bits (a 370-byte client RPC bunch)
LogNet: Error: ReceivedRPC: ReceivePropertiesForRPC - Mismatch read.
    Function: ServerVerifyViewTarget,
    Object: PlayerController .../LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_0
LogNet: Error: UActorChannel::ProcessBunch: Replicator.ReceivedBunch failed. Closing connection.
    RepObj: PlayerController, Channel: 3
LogNet: UNetConnection::Close: ... Result=ObjectReplicatorReceivedBunchFail
LogNet: SetClientLoginState: ReceivedJoin -> CleanedUp
```

Client got past the checksum stage, INSTANTIATED the PlayerController actor,
and called `ServerVerifyViewTarget` RPC on it. Server tried to deserialize the
RPC's arguments — mismatch. `ServerVerifyViewTarget` is a stock UE
APlayerController RPC, but SUPERVIVE's version has different parameters.

### New blocker (session 21): stock UE RPC signatures differ from SUPERVIVE's

Same underlying root cause as the checksum mismatch — SUPERVIVE modified
`APlayerController`. This time it's an RPC parameter list mismatch, and there's
no "ignore RPC signature" CVar because deserialization is a byte-stream parse
that has to structurally match.

### Session 21 plan

Options:
1. **Reverse-engineer SUPERVIVE's APlayerController modifications** and mirror
   the RPC signatures in a `ULokiStubPlayerController` subclass. Requires
   reading the exe for the modified `ServerVerifyViewTarget` signature (and
   probably other modified RPCs — likely dozens). Then register the subclass
   as the GameMode's `PlayerControllerClass`.
2. **Suppress RPC processing server-side** for RPCs we don't care about. E.g.,
   override `AGameModeBase::PlayerControllerClass` with a stub PC that has
   `ServerVerifyViewTarget` UFUNCTION that just returns immediately.
3. **Skip PC spawning entirely** — override `AGameModeBase::PostLogin` to not
   spawn a PC, only spawn game/replication-visible actors we author. Not
   compatible with normal UE flow but might work for our narrow menu-population
   goal.

Recommend Option 1 or 2. Start by `usmapdump wstrings` on the exe to find
`ServerVerifyViewTarget` and check what other modified RPCs there are:
```
tools\usmapdump\usmapdump.exe wstrings "G:\...\SUPERVIVE-Win64-Shipping.exe" | grep -iE "ServerVerify|ServerAcknowledge|ServerUpdateCamera|Server.*ViewTarget"
```

### Tooling delivered (session 20)

- `unreal-stub/Source/Loki/LokiNetDriver.cpp + .h` — added `InitBase` override
  that sets `GuidCache->NetworkChecksumMode = None` immediately after
  `Super::InitBase`.
- `docs/session-20-stub-log-excerpt.txt` — filtered server log showing
  Join succeeded → PC spawns client-side → RPC signature mismatch on
  ServerVerifyViewTarget.

### Chapter state (end of session 20)

- Handshake: DONE (session 17)
- Post-handshake packet-handler wiring: DONE (session 18)
- NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: DONE (session 18)
- Post-Welcome map validation: DONE (session 19, ModifyClientTravelLevelURL)
- NMT_Join / PostLogin / PC spawn server-side: DONE (session 19, world rename)
- Client-side PC actor spawn: DONE (session 20, NetworkChecksumMode=None)
- Server-side RPC deserialization for modified engine RPCs: TODO (session 21)
- Replicating hero-roster / mission / store data to client: TODO (session 22+)

### Commits this session

- (session 20 writeup commit follows)

## Session 21 (2026-07-01 — bReplicates=false PC approach FAILS; class-name resolution is a hard wall)

Session 20's blocker was `ReceivedRPC: Mismatch read` on `ServerVerifyViewTarget`
— stock UE APlayerController takes 0 args but SUPERVIVE's client-side version
sends ~2894 bits of arguments. Session 21 attempted a workaround: subclass
APlayerController with `bReplicates = false` so the client never receives a PC
and therefore never sends PC-level RPCs back.

### Attempt: LokiStubPlayerController with bReplicates=false

Added three files:
- `unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp` — subclass of
  APlayerController with `bReplicates = false`, `NetDormancy = DORM_DormantAll`.
- `unreal-stub/Source/Loki/LokiStubGameMode.h + .cpp` — AGameModeBase subclass
  that sets `PlayerControllerClass = ALokiStubPlayerController::StaticClass()`.
- `unreal-stub/Config/DefaultEngine.ini` — registered
  `[/Script/EngineSettings.GameMapsSettings] GlobalDefaultGameMode=/Script/Loki.LokiStubGameMode`.

### Result: NEW failure at ActorChannelFailure with different close reason

Server log:
```
LogLokiStubGM: LokiStubGameMode constructed with PlayerControllerClass=LokiStubPlayerController
LogLoad: Game class is 'LokiStubGameMode'
LogLokiStubPC: LokiStubPlayerController constructed (bReplicates=false, ...)
[connection sequence through Welcomed]
LogNet: Join request: /Engine/Maps/Entry?Name=9b9d... ?SplitscreenCount=1
LogNet: Join succeeded: 9b9d2c887e2524f918e3
LogNet: SetClientLoginState: Welcomed -> ReceivedJoin
LogNet: Server connection received: ActorChannelFailure 3
    ... Actor: LokiStubPlayerController .../PersistentLevel.LokiStubPlayerController_0 ...
    PC: LokiStubPlayerController_0, Owner: LokiStubPlayerController_0
LogNet: Warning: UControlChannel::ReceivedBunch: NetConnection::Close() ...
    failed to initialize the PlayerController channel. Closing connection.
LogNet: SendCloseReason: Result=ControlChannelPlayerChannelFail
LogNet: SetClientLoginState: ReceivedJoin -> CleanedUp
```

Root cause of the new failure: `AGameModeBase::PostLogin` calls `SpawnPlayActor`
which forcibly opens an ActorChannel for the PC EVEN IF `bReplicates=false`.
The channel-open bunch sends the actor's CLASS GUID as
`/Script/Loki.LokiStubPlayerController`. Client tries to resolve this — it's
not in the cooked SUPERVIVE package registry (only stock
`/Script/Engine.PlayerController` is). Client's `SerializeNewActor` returns
null → `NMT_ActorChannelFailure(3)` back to server → connection dies with
`Result=ControlChannelPlayerChannelFail` (different from session 20's
`Result=ObjectReplicatorReceivedBunchFail`).

### Dead-ends discovered

Two paths are now proven closed:
1. **Custom PC class name**: breaks client-side actor spawn because our class
   isn't in SUPERVIVE's cooked package registry.
2. **Stock APlayerController class**: succeeds through actor spawn but hits
   RPC signature mismatch when client's SUPERVIVE-modified APlayerController
   calls `ServerVerifyViewTarget` back with non-zero arg payload.

`bReplicates=false` doesn't help because UE's actor-channel setup for the PC
is not gated by bReplicates in the join flow — the channel opens
unconditionally, and the class GUID is always sent.

Attempted a class-rename trick (rename `/Script/Loki.LokiStubPlayerController`
to `/Script/Engine.PlayerController` at runtime — session-19-style) but
reverted after realizing it would collide with the existing loaded stock
`APlayerController` CDO in the same path. UE forbids two UClasses at the same
package path.

### New blocker (session 22): must match SUPERVIVE's RPC signature

Path forward: keep `PlayerControllerClass = APlayerController::StaticClass()`
(so class GUID resolves client-side) and add a UFUNCTION override that matches
the SUPERVIVE-modified `ServerVerifyViewTarget` signature. Requires:

1. RE the signature via `usmapdump wstrings` / `usmapdump nameid` on a LIVE
   running SUPERVIVE process (usmapdump attaches to a process, not a static
   exe — needs the game running for the packer to have unpacked strings).
2. Optionally: `usmapdump extract` to dump the full property schema — this
   may give us the exact FProperty layout of the modified
   `ServerVerifyViewTarget_Parms` struct.
3. Add matching UFUNCTION to `ALokiStubPlayerController` (which becomes a
   proper subclass of APlayerController that overrides the RPC).
4. Register `LokiStubPlayerController` as `PlayerControllerClass` in a
   custom GameMode — but ONLY if we can also make the client resolve it
   as APlayerController. Options:
   - Add UClassRedirect from `/Script/Engine.PlayerController` →
     `/Script/Loki.LokiStubPlayerController` at server-side.
   - Or: keep GameMode's PC class as stock APlayerController, and register
     our RPC override on the stock class via `UFUNCTION(Server, ...)` in a
     side-loaded UObject that hooks the class's function table.

### Tooling delivered (session 21)

- `unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp` — APlayerController
  subclass. Currently has bReplicates=false + NetDormancy=DormantAll. Both
  attributes preserved as documentation of what didn't work; session 22 will
  either flip them or introduce a matching RPC UFUNCTION.
- `unreal-stub/Source/Loki/LokiStubGameMode.h + .cpp` — AGameModeBase subclass
  registering LokiStubPlayerController.
- `unreal-stub/Config/DefaultEngine.ini` — GlobalDefaultGameMode registration.
- `docs/session-21-stub-log-excerpt.txt` — filtered stub log showing
  ControlChannelPlayerChannelFail failure mode.

### Chapter state (end of session 21)

- Handshake: DONE (session 17)
- Post-handshake packet-handler wiring: DONE (session 18)
- NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: DONE (session 18)
- Post-Welcome map validation: DONE (session 19)
- NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
- Client-side PC actor spawn (stock class): DONE (session 20)
- Server-side RPC deserialization for modified engine RPCs: TODO (session 22)
- Replicating hero-roster / mission / store data to client: TODO (session 23+)

### Commits this session

- (session 21 writeup commit follows)

## Session 22 (2026-07-01 — SUPERVIVE's engine modifications CONFIRMED via usmapdump extract; RPC signature RE deferred)

Session 22 attempted to RE SUPERVIVE's `ServerVerifyViewTarget` RPC signature.
Used `tools/usmapdump/usmapdump.exe extract` to dump the live SUPERVIVE
process's UClass schema. The tool writes to `schema.txt` (70,996 lines) and
also produces a fresh `mappings.usmap`.

### Key finding: TheoryCraft heavily modified engine base classes

The extracted `AActor` UClass has 103 FProperties — significantly more than
stock UE5.4's ~85. New TheoryCraft-added properties on `AActor`:

- `LokiReplicationStrategy` (StructProperty, UStruct:LokiReplicationStrategy)
  — a 5-field struct: `CustomReplicationStrategy` (enum), `bOwningPlayer`,
  `bDistanceBased`, `bVision`, `bTeamBased`. **This is a per-actor
  replication-control struct that runs on EVERY actor in the game.**
- `ServerState` (StructProperty, UStruct:PoolableActorServerState) — actor
  pooling infrastructure
- `bCopyTagsFromStaticMeshes`, `bAggregateTicks`, `StaticMeshTags` —
  tag/tick additions
- `bDebugTarget`, `bEnablePooling`, `bCanPrimeOnServer`, `bCanPrimeOnClient`,
  `bCanPrimeInArena`, `bCanPrimeInBattleRoyale`,
  `bAlwaysDestroyInsteadOfReturningToPool`, `MaxPoolSize`, `PoolPrimeSize`,
  `SimulatedTearOffIdleTimeInSeconds`, `InitiallyVisibleComponents`,
  `PoolManager` — actor pooling system
- `OnLokiEndPlay`, `OnPooledActorTornOff` — Loki-specific delegates

Full excerpt saved to
[docs/session-22-schema-actor-loki-mods.txt](session-22-schema-actor-loki-mods.txt).

### But: PlayerController properties look STOCK vanilla

The extracted `APlayerController` has 56 FProperties — all match stock UE5.4
names. No obvious SUPERVIVE additions at the base PlayerController level.

That means the `ServerVerifyViewTarget` RPC mismatch isn't from added
FProperties on PlayerController; it must be from either:
1. Added parameters on the `ServerVerifyViewTarget` UFUNCTION itself, OR
2. Engine-level RPC-envelope modification (e.g., every RPC bunch has extra
   TheoryCraft metadata prepended/appended)

### Why we couldn't extract the exact signature

`usmapdump extract` only dumps FProperty registrations (member variables),
NOT UFunction registrations. Nothing in the schema.txt shows RPC parameter
lists.

Also tried `usmapdump wstrings` for the RPC name — got 8 hits including one
that showed `"ServerVerifyViewTarget()"` with EMPTY parens (which SUGGESTS
a zero-arg signature, matching stock — but this is a debug string not a
real reflection dump, so unreliable).

`usmapdump xrefstr` on the RPC name string returned 0 hits — the string is
referenced indirectly (via a name-pool index or dynamic construction, not
via a rip-rel LEA).

`usmapdump nameid` confirmed just one entry: `ServerVerifyViewTarget` at
NamePool id 0xA3F7.

### Session 23 plan

Two viable paths:

**Path A: Live bunch decoding**
Add hex-dump logging in the stub's `UActorChannel::ReceivedBunch` path (or
even simpler: add a `LogNet` Verbose CVar so UE's own bunch parser logs each
byte). Then compute what bits the client sent between `Function name/hash`
end and bunch end. Cross-reference with UE's BunchFormat spec to identify
parameter types. Slow but definitive.

**Path B: Proper class dumper**
Use a stronger UE reflection dumper (SDKGen-style: walk the entire
GUObjectArray and enumerate all UFunction objects with their Children FProperty
list). Would need to write custom code (usmapdump doesn't currently do this)
OR use an external tool like Dumper-7 (community UE dumper for shipping games).

Path A is faster to iterate but manual. Path B is more general-purpose.
Recommend starting with Path A on the ONE known-failing RPC.

Also worth investigating: whether there's a client-side CVar that would
LOG each RPC's expected arg count client-side (e.g., `net.LogRPCs=1`).
Might reveal the args from the CLIENT side directly.

### Task list from this session

Created 5 tasks: launch (completed), extract schema (completed), add matching
UFUNCTION (deferred — need signature), solve class-name resolution (deferred),
end-to-end test (deferred).

### Tooling artifacts (session 22)

- `docs/session-22-schema-actor-loki-mods.txt` — filtered schema showing
  SUPERVIVE's AActor modifications and the LokiReplicationStrategy struct.
- (Existing) `schema.txt` was refreshed by usmapdump — 4.28 MB, 70,996 lines,
  full class + struct + enum schema of the live game. Not committed
  (too large) but present in repo root.
- (Existing) `tools/extractor/mappings.usmap` — refreshed usmap file for
  future .pak content extraction.

### Chapter state (end of session 22)

- Handshake: DONE (session 17)
- Post-handshake packet-handler wiring: DONE (session 18)
- NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: DONE (session 18)
- Post-Welcome map validation: DONE (session 19)
- NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
- Client-side PC actor spawn (stock class): DONE (session 20)
- Server-side RPC deserialization for modified engine RPCs: TODO (session 23 — needs Path A or B RE approach)
- Replicating hero-roster / mission / store data to client: TODO (session 24+)

### Commits this session

- (session 22 writeup commit follows)

## Session 23 (2026-07-01 — RPC bunch BYTES captured; FString parameter confirmed)

Session 22's plan Path A: log the actual bunch bytes and decode the RPC
parameter structure empirically. Session 23 executed that.

### What was added

1. `LogNetTraffic VeryVerbose` + `LogRep VeryVerbose` on the stub's -LogCmds.
   UE's built-in bunch tracer now logs per-packet Send/Receive details
   including bunch-level info: `Reliable Bunch, Channel %i Sequence %i:
   Size %.1f+%.1f` (header/payload sizes).

2. Full inner-packet hex dump in
   `unreal-stub/Source/Loki/LokiStatelessConnect.cpp` `Incoming(FBitReader&)`
   override — dumps the full post-wrapper-strip byte sequence for any
   packet larger than 128 bits. This gives us the raw RPC bytes.

3. Modified `LokiStubGameMode` to use STOCK `APlayerController` (instead of
   session-21's LokiStubPlayerController) so the client can spawn the PC
   and actually fire the ServerVerifyViewTarget RPC. (Session-24 will swap
   back to a Loki subclass with the matching UFUNCTION.)

### Result: RPC bunch bytes captured, FString parameter confirmed

Server log for the failing bunch (Channel 3, Sequence 549, size 5.8+292.4):

The 362-byte inner packet post-wrapper-strip contains a valid UE-format
FString at byte offset 145:
```
0091: 2F 00 00 00        // int32 LE count = 47 (chars + null)
0095: 2F 47 61 6D 65 2F  // "/Game/"
      4C 6F 6B 69 2F     // "Loki/"
      4D 61 70 73 2F     // "Maps/"
      4C 6F 62 62 79 56 32 2F  // "LobbyV2/"
      4C 56 4C 5F 4C 6F 62 62 79 56 32 5F 42 61 74 74 6C 65 50 61 73 73  // "LVL_LobbyV2_BattlePass"
      00                 // null terminator
```

That's the ONLY ASCII string in the packet. Full byte dump saved to
[docs/session-23-rpc-bunch-bytes.txt](session-23-rpc-bunch-bytes.txt).

**Hypothesis**: SUPERVIVE's `ServerVerifyViewTarget` takes at least one
`FString` parameter, likely the current lobby-mode map name (client tells
server "I'm on LobbyV2_BattlePass now"). The remaining ~245 bytes of the
payload contain additional structured data (bit-packed, hard to identify
without more analysis) — likely more parameters.

Interpretation: SUPERVIVE repurposed `ServerVerifyViewTarget` from its
stock "verify current view target actor" semantics into a lobby-mode
handshake RPC. Makes sense — TheoryCraft removed most of stock UE's
gameplay-style RPCs in favor of their custom lobby+matchmaking pipeline.

### The bunch payload structure

The 292.4-byte payload has three visually distinct sections:
- Bytes 0-90: Structured binary (repeated patterns like `AC AD EC 85`,
  `AC BE CA C0`, `AC BC D2 F0` — variable-length quantities or
  bit-packed enum/int fields)
- Bytes 91-137: `2F 00 00 00` + `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass\0`
  (FString #1)
- Bytes 138-292: More structured binary, no ASCII strings

The other structured sections look like they could be:
- Compressed/packed integer arrays
- Enum lookups (repeated similar bytes suggest tokenized values)
- Possibly OTHER FStrings serialized with UE's Huffman-style compression
  (`FString::SerializeAsANSICharArray`) — but stock UE doesn't use
  Huffman for FString.

### New blocker (session 24)

Still need to identify the EXACT parameter list of
`ServerVerifyViewTarget`. Session 24 approach:

1. Enable `LogRepTraffic Verbose` on the stub (this session forgot; only
   had `LogRep VeryVerbose`). LogRepTraffic prints "Received RPC: %s" and
   should log the sub-reader's NumPayloadBits value explicitly — that
   tells us the exact bit count of the RPC's arg struct.

2. Write a bit-level packet parser (Python or Rust). Read the packet header
   (FNetPacketNotify), skip to bunch on channel 3, read bunch header
   (bReliable, bOpen, ChIndex encoded, ChSequence, NumBits), then parse
   the field header + SerializeIntPacked NumPayloadBits + payload bits.

3. Once we know NumPayloadBits, try trial signatures:
   - Try `FString` — see if it consumes all bits.
   - If not, try `FString + something` — iterate.
   - Common candidates: FString ClientMapName, FVector2D/FVector Location,
     FQuat Rotation, uint32 timestamp/hash, bytes Payload.

4. Add matching UFUNCTION to `ALokiStubPlayerController`, flip
   `PlayerControllerClass` back to Loki subclass, re-run. Repeat for any
   additional modified RPCs SUPERVIVE calls after this one.

### Task list from session 23

Created 3 new tasks (all completed): enable LogNetTraffic Verbose, extract
RPC bunch bytes, decode format vs UE spec. Session 24 will need fresh
tasks for the bit-level parsing.

### Tooling artifacts (session 23)

- `docs/session-23-rpc-bunch-bytes.txt` — 15-line capture of the RPC
  bunch bytes + observations.
- `scratchpad/decode_rpc_bunch.py` — Python decoder that identifies ASCII
  runs, FString-shaped patterns, and dumps the packet header. Not
  committed (session-local scratch).
- Modified `LokiStatelessConnect.cpp` (`Incoming` now dumps full inner
  hex for >128-bit packets).
- Modified `LokiStubGameMode.cpp` (PlayerControllerClass swapped to stock
  APlayerController for RE mode).

### Chapter state (end of session 23)

- Handshake: DONE (session 17)
- Post-handshake packet-handler wiring: DONE (session 18)
- Control-channel messages (Hello / Login / Welcome): DONE (session 18)
- Post-Welcome map validation: DONE (session 19)
- NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
- Client-side PC actor spawn: DONE (session 20)
- SUPERVIVE engine modifications confirmed: DONE (session 22)
- RPC bunch bytes captured: DONE (session 23)
- Exact RPC parameter list identified: TODO (session 24 — bit-level parse)
- Add matching UFUNCTION + solve class-name resolution: TODO (session 24-25)
- Replicating hero-roster / mission / store data to client: TODO (session 26+)

### Commits this session

- (session 23 writeup commit follows)

## Session 24 (2026-07-01 — bit-level packet parser: packet header WORKS, bunch header stuck; pivot recommended)

Session 24 extended `scratchpad/decode_rpc_bunch.py` (also saved to
`docs/session-24-packet-parser.py`) to attempt bit-level parsing of the
session-23 captured packet.

### What works

- **StatelessConnect prefix**: The captured bytes are AFTER our
  LokiStatelessConnect wrapper strip but BEFORE `StatelessConnectHandlerComponent::Incoming`
  runs. The stock impl reads:
  ```
  SessionID (2 bits) + ClientID (3 bits) + bHandshakePacket (1 bit) = 6 bits
  ```
  Verified from `H:\...\PacketHandlers\StatelessConnectHandlerComponent.h:533,536`
  (SessionIDSizeBits=2, ClientIDSizeBits=3). Skipping 6 bits at the start
  of the packet gets us aligned with UE's own view.

- **FNetPacketNotify header**: 32-bit PackedHeader (Seq14 + AckedSeq14 +
  HistoryWordCount-1_4) + `HistoryWordCount * 32` bits of history data.
  Parser decodes:
    Seq=1577, AckedSeq=354, HistoryWordCount=1
  Which matches the stub log's
    `LogNetTraffic: Verbose: FNetPacketNotify::ReadHeader - Seq 1577, AckedSeq 354 HistorySizeInWords 1`
  exactly. ✓

- **PacketInfo section**: `bHasPacketInfoPayload=1` (1 bit) followed by
  `JitterClockTime` (10 bits, per
  `H:\...\NetConnection.h:72 NumBitsForJitterClockTimeInHeader = 10`).
  Parser decodes JitterClockTime=439 with reader at bit 81.

### Where it hits a wall

Bunch header parsing at bit 81 reads:
  - Bit 81 (bControl/bIsOpenOrClose): 1
  - Bit 82 (bOpen): 0
  - Bit 83 (bClose): 0

But bIsOpenOrClose=1 implies at least one of bOpen/bClose must be 1
(the write side ORs them). This bunch is the Channel-3 RPC bunch that
UE's own trace showed as `Reliable Bunch, Channel 3 Sequence 549:
Size 5.8+292.4` — so it should have bReliable=1, bOpen=0, bClose=0.
That means bIsOpenOrClose should be 0, not 1.

Either the parser has a subtle off-by-one (unlikely — packet header
decoded correctly), OR there's an additional bit/prefix between the
JitterClock section and the first bunch that we're not accounting for.

Candidates for the missing bit(s):
- Some engine version has a `bHasSecurityData` or similar bit.
- Possibly SUPERVIVE's wire-format has an extra byte/bit beyond the
  8-byte outer wrapper — we handle the outer wrapper but may need to
  strip more.

### Pivot recommendation for session 25

Rather than continue bit-level RE, add SERVER-SIDE instrumentation to
capture the RPC's sub-reader bytes at the point of `ReceivePropertiesForRPC`:

1. Subclass FObjectReplicator (or hook the connection's FieldCache path)
   to log the exact sub-reader payload of `ServerVerifyViewTarget`.
   Since sub-reader bit-count == NumPayloadBits, we know EXACTLY what
   the client sent as arguments (byte-aligned within the sub-buffer).

2. Alternative: modify our stub PC's `CallRemoteFunction`-side handler
   to intercept the incoming RPC bytes.

3. Alternative: add `LogNet.RepLayoutTrace` or similar CVars that force
   UE to log per-property bit consumption in ReceivePropertiesForRPC.

Once we have the byte-aligned param struct, decoding it manually is
straightforward.

### What's confirmed

- The RPC bunch payload contains a properly-encoded UE FString
  `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass` (int32 count=47 +
  46 chars + null).
- Bunch payload is ~292 bytes total — likely multiple additional
  parameters beyond just the FString.
- Client's `ServerVerifyViewTarget` has been repurposed by SUPERVIVE
  (from stock UE's 0-arg "verify view target actor" to a lobby-mode
  handshake carrying a map name + more).

### Tooling artifacts (session 24)

- `docs/session-24-packet-parser.py` — 309-line Python parser
  (partial). Decodes StatelessConnect prefix, FNetPacketNotify header,
  JitterClock; leaves bunch header parsing as an exercise (or session
  25 pivots away from this approach).

### Chapter state (end of session 24)

- Handshake, packet handler wiring, control messages, map validation,
  Join, PC spawn, checksum bypass: ALL DONE (sessions 17-20)
- SUPERVIVE engine mods confirmed: DONE (session 22)
- RPC bunch bytes captured: DONE (session 23)
- FString parameter identified: DONE (session 23)
- Bit-level packet header parsing: DONE (session 24, `docs/session-24-packet-parser.py`)
- Full RPC parameter list identified: TODO (session 25 — pivot to
  server-side sub-reader instrumentation)
- Add matching UFUNCTION + solve class-name: TODO (session 25-26)
- Menu-data replication: TODO (session 27+)

### Commits this session

- (session 24 writeup commit follows)

## Session 25 (2026-07-01 — SERVER-SIDE RPC BYTE CAPTURE + FIELD-HEADER DECODED)

Session 24's pivot recommendation: hook server-side to capture RPC sub-reader
bytes directly. Session 25 executed that and successfully decoded the RPC
field header, isolating the exact 2298-bit RPC arg struct.

### Fix delivered: LokiActorChannel subclass

Added `unreal-stub/Source/Loki/LokiActorChannel.h + .cpp` — subclass of
`UActorChannel` overriding `ReceivedBunch(FInBunch& Bunch)`. Uses
`FBitReaderMark` to non-destructively extract the bunch's raw bit stream
into a byte buffer, hex-dumps it with ChIndex/ChSequence/NumBits/bReliable
metadata, then Mark.Pop's the reader back so Super sees a fresh bunch.

Registered via `unreal-stub/Config/DefaultEngine.ini`
`[/Script/OnlineSubsystemUtils.IpNetDriver] ChannelDefinitions` — replaces
stock `ActorChannel` class with `/Script/Loki.LokiActorChannel`.

Verified: the Channel-3 bunch containing ServerVerifyViewTarget now logs:
```
LogLokiActorChannel: ReceivedBunch: ChIndex=3 ChSeq=176 bReliable=1
    bOpen=0 bClose=0 NumBits=2339 StartPos=0 remaining=2339 bits
LogLokiActorChannel: ReceivedBunch: bytes (293) 8E 90 78 EB 45 16 00 8C 0B ...
```

Full 293-byte dump saved to `docs/session-25-bunch-capture.txt`.

### Bit-level decoding of the bunch (offline)

Wrote `docs/session-25-bunch-decoder.py` (212 lines) that parses the
captured bytes:

```
Total bunch bits: 2339

Content block header (bits 0-1, 2 bits):
  bOutHasRepLayout = 0 (no property replication in this bunch)
  bIsActor         = 1 (this bunch is for the actor, not sub-object)

Outer SerializeIntPacked NumPayloadBits (bits 2-17, 16 bits):
  NumPayloadBits = 2321 (FObjectReplicator payload size)

Field header (bits 18-40, 23 bits) — walks the RPC dispatch loop:
  RepIndex (SerializeInt(MaxIndex+1), assuming MaxIndex=100) = 94
  Inner NumPayloadBits (SerializeIntPacked)                  = 2298

RPC arg struct (bits 41-2338, 2298 bits = 287.25 bytes)
```

The 2298-bit RPC arg struct is what SUPERVIVE's client marshalled and
what our stock `APlayerController::ServerVerifyViewTarget` (0 args) failed
to consume — hence `Reader.GetBitsLeft() != 0 → Mismatch read`.

### RPC arg struct: FString + more

The FString `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass` appears
BYTE-ALIGNED in the raw bunch bytes at offset 128 with proper UE
serialization (int32 count=47 followed by 46 chars + null). That's 47*8
= 376 bits for chars + 32 bits for count = 408 bits total for that
FString alone.

Remaining 2298 - 408 = 1890 bits (~236 bytes) of additional parameters
before/after the FString.

### Session 26 plan

Now that we know the exact bit budget (2298 bits) and confirmed at least
one FString parameter, we can iterate:

1. Add a `UFUNCTION(reliable, server, WithValidation) ServerVerifyViewTarget(FString)`
   to LokiStubPlayerController. Log the leftover bits from
   `Reader.GetBitsLeft()` after Super::ProcessBunch — this tells us how
   many bits remain unconsumed.
2. If ~1890 bits remain after FString: add more params until it drops to 0.
   Candidates: FVector (96 bits), FRotator_NetQuantize (24 bits), FQuat_NetQuantize
   (64 bits), TArray<FStructOrStringOrBlob>, etc.
3. Try common anti-cheat "verify view target" args:
   - `FString ViewTargetName` (or `FName`)
   - `FVector_NetQuantize CameraLocation`
   - `FRotator CameraRotation`
   - `float ClientTime`
   - `int32 VerifyCounter`
   - `TArray<uint8> SignatureBlob` (large!)
   
4. Or the SUPERVIVE-specific "modified for lobby mode" signature that
   carries a matchmaking-mode name (LobbyV2_BattlePass = one of the
   game modes).

Also — solve the class-name resolution problem (still open from session
21). Now that we have a matching UFUNCTION, we need our class to receive
the RPC. Options:
- Continue using stock APlayerController (session 23 config) — but our
  override methods need to be on the actual dispatched class. Adding
  UFUNCTIONs to stock APlayerController isn't directly possible.
- Use `ALokiStubPlayerController` (session 21) with a runtime class-name
  rename to `/Script/Engine.PlayerController` (careful CDO handling).
- Register UFUNCTION on the stock class via UClass function-table
  manipulation at Loki module init.

### Tooling artifacts (session 25)

- `unreal-stub/Source/Loki/LokiActorChannel.h + .cpp` (NEW).
- `unreal-stub/Config/DefaultEngine.ini` (`ChannelDefinitions` override).
- `docs/session-25-bunch-capture.txt` — 18-line log excerpt + decode
  summary.
- `docs/session-25-bunch-decoder.py` — 212-line Python bit-level decoder.

### Chapter state (end of session 25)

- Handshake, packet handler wiring, control messages, map validation,
  Join, PC spawn, checksum bypass: ALL DONE (sessions 17-20)
- SUPERVIVE engine mods confirmed: DONE (session 22)
- RPC bunch bytes captured: DONE (session 23)
- Bit-level packet header parsing: DONE (session 24)
- Server-side per-bunch instrumentation: DONE (session 25)
- Bunch content-block header + field header decoded: DONE (session 25)
- RPC arg struct isolated (2298 bits, contains at least FString): DONE (session 25)
- Full RPC parameter list decoded: TODO (session 26 — trial signatures)
- Add matching UFUNCTION + class-name resolution: TODO (session 26-27)
- Menu-data replication: TODO (session 28+)

### Commits this session

- (session 25 writeup commit follows)

## Session 26 (2026-07-01 — UHT rejects UFUNCTION override with different params; runtime function-table injection required)

Session 26 attempted the direct approach from session 25's plan: add a
`UFUNCTION(reliable, server, WithValidation) ServerVerifyViewTarget(const FString& ClientMapName)`
override to `ALokiStubPlayerController`, hoping UE would use the subclass's
version instead of stock's 0-arg version.

### Finding: UHT enforces UFUNCTION parameter parity across override

UnrealHeaderTool rejected the build with:
```
LokiStubPlayerController.h(42): Error: Override of UFUNCTION
'ServerVerifyViewTarget' in parent 'APlayerController' cannot have a
UFUNCTION() declaration above it; it will use the same parameters as the
original declaration.
```

This is a hard UE contract: subclass UFUNCTION overrides MUST match the
parent's signature exactly. Adding new parameters via subclass override is
not permitted through the UHT / UPROPERTY reflection system.

### Session 27 plan — runtime UClass function-table injection

To register a UFUNCTION with a different signature under the name
`ServerVerifyViewTarget`, we need to bypass UHT and construct the UFunction
at runtime:

1. In `FLokiModule::StartupModule` (or a delegate), find
   `APlayerController::StaticClass()`.
2. Construct a new `UFunction` object with our target signature
   (FString + more params as needed).
3. Set its FName to `ServerVerifyViewTarget`.
4. Insert into APlayerController's FuncMap, replacing the existing entry.
5. Ensure the class's ClassNetCache is rebuilt so RepLayout picks up
   the new signature.

Complex but doable. UE's plugin/mod ecosystem has done similar tricks
(e.g., Blueprint-injected UFunctions).

Alternative (simpler): use the `AddNativeFunction` mechanism if it
supports overriding existing entries.

Also: session 26 confirmed we can keep the LokiActorChannel bunch-dump
capability alongside these attempts — it's non-destructive and preserves
UE's normal error path.

### Files changed in session 26

- `unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp` — attempted
  UFUNCTION override, reverted after UHT rejection. Preserved documentation
  comment explaining the constraint.
- `unreal-stub/Source/Loki/LokiStubGameMode.cpp` — reverted to stock
  APlayerController class after finding.

### Chapter state (end of session 26)

- Everything through PC spawn: DONE (sessions 17-20)
- SUPERVIVE engine mods confirmed: DONE (session 22)
- RPC bunch bytes captured + decoded: DONE (sessions 23-25)
- Server-side per-bunch instrumentation: DONE (session 25)
- Bunch content-block header + field header decoded: DONE (session 25)
- RPC arg struct isolated (2298 bits, FString + ~236 more bytes): DONE (session 25)
- UFUNCTION subclass override strategy: DEAD-END (session 26, UHT enforced)
- Runtime UClass function-table injection: TODO (session 27)
- Full RPC parameter list: TODO (session 27)
- Menu-data replication: TODO (session 28+)

### Commits this session

- (session 26 writeup commit follows)

## Session 27 (2026-07-01 — UFUNCTION runtime injection WORKS; class-name issue BYPASSED; iterate param order next)

Session 26 established that UHT rejects subclass UFUNCTION override with
different params. Session 27 implemented the runtime function-table
injection alternative — and IT WORKS.

### Implementation

Added `FLokiModule::InjectServerVerifyViewTargetFStringParam()` in
`unreal-stub/Source/Loki/Loki.cpp`. Registered via
`FCoreDelegates::OnPostEngineInit` so it runs after UE has fully loaded
class metadata but before any client connects.

The function:
1. Gets `APlayerController::StaticClass()`
2. Finds the existing `ServerVerifyViewTarget` UFunction (stock: 0 args)
3. Constructs a new `FStrProperty` with `CPF_Parm | CPF_ConstParm |
   CPF_ReferenceParm` flags, owned by the UFunction
4. Appends it to `Func->ChildProperties` linked list
5. Calls `Func->StaticLink(true)` to recompute `NumParms`, `ParmsSize`,
   `PropertyLink`, `ReturnValueOffset`
6. Calls `PCClass->ClearFunctionMapsCaches()` to invalidate cached
   FClassNetCache

Verified in log:
```
LogLokiStub: InjectServerVerifyViewTarget: found UFunction on APlayerController
    (NumParms=0, ParmsSize=0, FunctionFlags=0x80220CC2)
LogLokiStub: InjectServerVerifyViewTarget: added FStrProperty ClientMapName.
    New NumParms=1, ParmsSize=16
```

### Result: error mode changed — UE picked up the new signature

Before injection (sessions 20-25): `LogNet: Error: ReceivedRPC:
ReceivePropertiesForRPC - Mismatch read` (Reader.GetBitsLeft() != 0
after successful deserialization of 0 params).

After injection (session 27): `LogRep: Error: ReceivedRPC:
ReceivePropertiesForRPC - Reader.IsError() == true` (deserialization
overflowed).

This confirms UE's RepLayout picked up our injected FStrProperty and
tried to deserialize the payload as an FString. The overflow happens
because FString serialize reads a 32-bit int32 count from bit 0 of the
RPC payload — but session 25's analysis showed the payload's FIRST
991 bits are OTHER params, and the actual FString starts at bit 991.
So reading garbage bits as the count leads to reading more chars than
available.

### KEY architectural wins from session 27

1. **UFunction runtime injection works**. We can modify stock
   APlayerController's signature at runtime without touching engine
   source and without UHT rejection.

2. **Class-name resolution problem BYPASSED**. Session 21's dead-end
   (custom PC class name unresolvable client-side) is dodged entirely.
   Server spawns stock APlayerController — client resolves it just
   fine — but our injected UFunction is what UE dispatches to.

3. **Session 28's job is much simpler**: just iterate the parameter
   ordering. Try FVector + FRotator + FString (matches "verify view
   target with camera location, rotation, and current-view-target-name"
   semantics), etc.

### Session 28 plan

1. Update `InjectServerVerifyViewTargetFStringParam` to be a more general
   `InjectServerVerifyViewTargetSignature` that adds multiple params in
   order.
2. Trial common anti-cheat "verify view target" signatures:
   - `void ServerVerifyViewTarget(FVector, FRotator, FString)` — 96 + 96
     + FString = ~200 bits + FString ≠ 991 + FString
   - `void ServerVerifyViewTarget(TArray<uint8> AntiCheatBlob, FString)`
     — variable + FString
   - Try incremental adds via test-fail-observe loop.
3. When the FString consumes correctly (no Reader.IsError), we've
   correctly positioned it. Then check the tail — likely more params
   after.
4. When ALL bits consumed exactly (no Mismatch, no IsError), we're done.

### Tooling artifacts (session 27)

- `unreal-stub/Source/Loki/Loki.cpp` (extended with UFunction injector
  runtime hook)
- `docs/session-27-injection-test.txt` (17-line log excerpt showing
  before/after error-mode change)

### Chapter state (end of session 27)

- Everything through PC spawn: DONE (sessions 17-20)
- SUPERVIVE engine mods confirmed: DONE (session 22)
- RPC bunch bytes captured + decoded: DONE (sessions 23-25)
- Server-side per-bunch instrumentation: DONE (session 25)
- Bunch content-block header + field header decoded: DONE (session 25)
- RPC arg struct isolated (2298 bits): DONE (session 25)
- UHT-rejection of subclass override: CONFIRMED (session 26)
- Runtime UFunction injection technique: WORKING (session 27)
- Class-name resolution problem: BYPASSED (session 27)
- Full RPC parameter list identified: TODO (session 28 — iterate
  param orders)
- Menu-data replication: TODO (session 29+)

### Commits this session

- (session 27 writeup commit follows)

## Session 28 (2026-07-01 — generalized injector + first multi-param trial; iteration continues)

Session 27 established that runtime UFunction injection works. Session 28
generalized the injector infrastructure and made the first multi-property
trial.

### Delivered: generalized injector helpers

Extended `unreal-stub/Source/Loki/Loki.cpp` with reusable helpers:
- `AppendStringParam(Func, Name)` — appends FStrProperty
- `AppendStructParam(Func, Name, StructPath)` — appends FStructProperty
  looking up UScriptStruct by path (e.g., `/Script/CoreUObject.Vector`)
- `AppendVectorParam(Func, Name)` — FVector shortcut
- `AppendRotatorParam(Func, Name)` — FRotator shortcut
- `AppendToChildProperties(Func, Prop)` — tail-append to
  Func->ChildProperties linked list

### First multi-param trial: (FVector, FRotator, FString)

Rationale: common anti-cheat "verify view target" signature pattern —
(camera location, camera rotation, current-target name). Bit budget:
96 (FVector) + 96 (FRotator) + 32 (FString count) + N*8 (chars) = variable.

Injection log confirms it worked:
```
LogLokiStub: InjectServerVerifyViewTarget: found UFunction on
    APlayerController (NumParms=0, ParmsSize=0, FunctionFlags=0x80220CC2)
LogLokiStub: InjectServerVerifyViewTarget: added FVector+FRotator+FString
    params. New NumParms=3, ParmsSize=64
```

Test outcome: STILL `Reader.IsError() == true` (same overflow error mode
as session 27). Confirms FVector at bit 0 doesn't match the actual first
param of SUPERVIVE's RPC.

### Byte-level analysis

Analyzed the raw RPC payload's first 32 bits at bit 0:
- Value = 0x05C6000B = 96862219 as int32 LE
- As float32: ~1.86e-35 (denormalized, essentially zero)

Neither interpretation matches a plausible FVector X component or FString
count. First param must be a **fixed-size struct with specific bit
alignment** OR a **NetSerialize custom struct** whose bit-consumption
pattern isn't a simple UPROPERTY read.

### Why 991 bits before FString is unusual

Session-25 analysis: FString `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass`
starts at RPC-payload bit 991 (= bunch bit 1032, byte-aligned in raw
bunch). Preceding params sum to 991 bits. But:

- 991 mod 8 = 7 → not a multiple of byte
- 991 doesn't decompose cleanly into simple UPROPERTY combos:
  - FVector (96) + FRotator (96) = 192, remaining 799 doesn't fit FString+int32
  - N * FVector = 991: N = 10.32 (no)
  - FString(N=115) + FString(N=M) = 991: various N,M don't align
  - TArray<uint8> (32 + N*8) = 991: N = 119.875 (no)
- Suggests SUPERVIVE's first param is a **custom USTRUCT with NetSerialize
  override** (like FVector_NetQuantize but variable-length) OR contains
  bit-level packed fields (bools, enums).

### Session 29 plan

1. Add more property helpers: FByteProperty, FIntProperty, FFloatProperty,
   FBoolProperty, FArrayProperty<uint8>, more UScriptStruct paths for
   FVector_NetQuantize / FQuat / FRotator_NetQuantize.
2. Try trial signatures more systematically:
   - `(TArray<uint8>, FString)` — TArray absorbs variable prefix
   - `(FVector_NetQuantize100, FVector_NetQuantize100, FString)` — variable
     bit encoding for vectors
   - `(FQuat, FString)` — quaternion for rotation
   - `(FString First, FString ClientMapName)` — maybe two FStrings
   - `(FUniqueNetIdRepl, FString)` — player identity + map
3. Consider that the RPC arg struct may include a large USTRUCT with
   custom NetSerialize. In that case, we'd need to find or construct
   a matching USTRUCT.
4. Explore: SUPERVIVE's `usmapdump extract` schema showed several Loki-
   specific structs like `LokiReplicationStrategy`. Could one of these be
   the RPC's first param?

### Tooling artifacts (session 28)

- `unreal-stub/Source/Loki/Loki.cpp` (generalized injector)
- `docs/session-28-injection-trial.txt` (21-line log excerpt + summary)

### Chapter state (end of session 28)

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded: DONE
- Runtime UFunction injection working with multiple property types: DONE
- Trial 1 (FString): Reader.IsError (session 27)
- Trial 2 (FVector, FRotator, FString): Reader.IsError (session 28)
- Correct RPC signature: TODO (session 29 — iterate more)
- Menu-data replication: TODO (session 30+)

### Commits this session

- (session 28 writeup commit follows)

## Session 29 (2026-07-01 — analytical rule-out + FVector_NetQuantize trial; iteration continues)

Session 29 added analytical rigor and expanded injector helpers.

### Injector helper expansion

Added `AppendIntParam`, `AppendFloatParam`, `AppendByteParam` to
`unreal-stub/Source/Loki/Loki.cpp`. Uses `AppendStructParam` with path
lookup for FVector_NetQuantize100:
```cpp
AppendStructParam(Func, TEXT("CamLocation"),
                  TEXT("/Script/Engine.Vector_NetQuantize100"));
```

### Analytical: rule out scalar first-param types

Analyzed the first 96-128 bits of the RPC payload against common UE
struct layouts:

- **FVector as 3 floats**: X=1.86e-35, Y=-1.32e+23, Z=-1.68e+27. IMPOSSIBLE
  for real coordinates.
- **FRotator as 3 floats**: same nonsense values. IMPOSSIBLE.
- **FQuat as 4 floats**: norm = 1.68e+27, should be near 1.0. IMPOSSIBLE.
- **Bit 0 of payload = 1**: consistent with either
  - `FVector_NetQuantize100` non-zero-vector flag
  - `NetGUID` valid-reference flag (for FObjectProperty)

**Conclusion**: first param must be a **variable-bit-encoded type** (custom
NetSerialize struct or NetGUID via FObjectProperty). Plain UPROPERTY scalars
are ruled out.

### Session 29 trial: (FVector_NetQuantize100, int32, FString)

Modeled on stock UE `ServerUpdateCamera(FVector_NetQuantize CamLoc,
int32 CamPitchAndYaw)` — SUPERVIVE may have merged that payload into
ServerVerifyViewTarget.

Injection succeeded (NumParms 0 → 3, ParmsSize 0 → 48).

Test outcome: still `Reader.IsError() == true`. FVector_NetQuantize100
either doesn't match SUPERVIVE's first param type, or the total bit count
of the combination doesn't equal 2298.

### Session 30 plan

Given exhaustive scalar/simple-struct rule-outs, session 30 should:

1. **Add FObjectProperty helper** — construct with a UClass* target
   (e.g., `AActor::StaticClass()`). Try `(AActor* NewViewTarget, FString)`.
   Actor pointers on wire are NetGUIDs (variable bits).

2. **Explore FUniqueNetIdRepl** — SUPERVIVE has player-identity
   verification; this struct has custom NetSerialize.

3. **Try SUPERVIVE-specific Loki structs** — `LokiReplicationStrategy`,
   `PoolableActorServerState`, and other Loki-named structs from
   `docs/session-22-schema-actor-loki-mods.txt`.

4. **Alternative**: write a Python bit-decoder that tries a MATRIX of
   possible signatures against the captured bytes. For each combination,
   check if all 2298 bits are exactly consumed AND if the intermediate
   values are "reasonable" (float values in [-1e5, 1e5], counts in
   [0, 1000], etc.). This narrows the search space analytically.

5. **Attach debugger** — the ultimate escape hatch. Load LokiEditor
   under a debugger, set a breakpoint at
   `FRepLayout::ReceivePropertiesForRPC`, step through with our
   FStrProperty signature, watch where FString read starts. Repeat with
   Loki-specific structs.

### Tooling artifacts (session 29)

- `unreal-stub/Source/Loki/Loki.cpp` (int/float/byte helpers added)
- `docs/session-29-trials.txt` (20-line trial log + summary)

### Chapter state (end of session 29)

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded (2298 bits): DONE
- Runtime UFunction injection working (multiple types): DONE
- Plain scalar first-param types RULED OUT: DONE (session 29)
- Correct RPC signature: TODO (session 30 — variable-bit types)
- Menu-data replication: TODO (session 31+)

### Commits this session

- (session 29 writeup commit follows)

## Session 30 (2026-07-01 — AActor* trial reveals PRECISE ENGINE-SIDE BIT-CONSUMPTION diagnostic)

Session 29 established that plain scalar types can't be the first RPC
param. Session 30 tried `(AActor* NewViewTarget, FString ClientMapName)`
— stock UE `ClientSetViewTarget` pattern that SUPERVIVE may mirror. The
test still failed with `Reader.IsError()`, but the engine emitted a
DIAGNOSTIC log line that unlocks precise iteration.

### Delivered

- `AppendObjectParam(Func, Name, UClass* PropertyClass)` — FObjectProperty
  helper for injecting Actor / UObject pointer params. NetGUID
  serialization uses `PackageMap->SerializeObject` (variable bits).
- Trial signature: `(AActor* NewViewTarget, FString ClientMapName)`.
  Injection succeeded (NumParms 0 → 2, ParmsSize 0 → 24).

### KEY breakthrough: engine-side bit-consumption diagnostic

Server log during RPC deserialization emitted:
```
Ensure condition failed: false [File:Serialization/BitReader.cpp] [Line: 276]
FBitReader::SetOverflowed() called! (ReadLen: 2952, Remaining: 2248, Max: 2298)
```

Decoded:
- `Max: 2298` = sub-reader's total capacity — **matches session-25 decode
  exactly**. This is independent engine-side confirmation of our bunch
  bit budget.
- `Remaining: 2248` = bits left when overflow fired.
- **AActor* NetGUID consumed exactly 50 bits** (2298 − 2248 = 50).
- Then FString read at bit 50 attempted to consume 2952 more bits (the
  count read at bit 50 was ~369, way too many chars for the remaining
  2216 bits).

### Why this is game-changing

Every trial now gives us TWO independent measurements from UE itself:
1. How many bits the current param sequence consumed.
2. The specific position where overflow happened.

We no longer need to guess signatures blindly. We can:
- Add a candidate first param → see how many bits it consumes.
- If close to 991 (target position of FString), we're on the right track.
- If overflow happens BEFORE bit 991, our param is too large; try smaller.
- If overflow happens AFTER FString read starts (garbage bits), our param
  is too small; try larger.

Session 30's trial (AActor*, FString) consumed 50 bits for Actor pointer.
We need 991 total before FString. So we need to add ~941 more bits of
intermediate param(s).

### Session 31 plan

1. Iterate: try `(AActor*, X, FString)` where X consumes ~941 bits.
   Candidates for X:
   - `FRepMovement` (contains FVector + FRotator + bools, custom NetSerialize,
     variable ~150-300 bits)
   - Multiple sub-params: `(int32, float, int32, float, ...)` totaling 941 bits
   - Another `AActor*` or two (more NetGUIDs)
   - `TArray<uint8>` with a specific length
2. Watch the engine's `SetOverflowed` diagnostic each iteration.
3. When bit consumption before FString reaches exactly 991, we've found
   the correct signature.

### Tooling artifacts (session 30)

- `unreal-stub/Source/Loki/Loki.cpp` (FObjectProperty helper added)
- `docs/session-30-actor-trial.txt` (23-line log excerpt + summary)

### Chapter state (end of session 30)

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded (2298 bits): DONE
- Runtime UFunction injection with FObjectProperty support: DONE
- ENGINE-SIDE BIT-COUNT DIAGNOSTIC discovered: DONE (session 30 — huge)
- AActor* NetGUID first-param consumes 50 bits: MEASURED (session 30)
- Middle-param signature (~941 bits): TODO (session 31 — iterate with
  engine feedback)
- Menu-data replication: TODO (session 32+)

### Commits this session

- (session 30 writeup commit follows)







