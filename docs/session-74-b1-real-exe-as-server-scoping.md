# S74 — B1 "real exe as the dedicated server" — read-only feasibility / go-no-go

Scoping pass (no game launch) for the approach: **run a second instance of the real
`SUPERVIVE-Win64-Shipping.exe` as the tutorial SERVER on 127.0.0.1:7777**, so it runs SUPERVIVE's
OWN round/drop-in/hero machinery (native C++ + Angelscript + BP content), and the S62 menu flow
delivers the client to it. Motivation: neither the force-open route (client-as-authority stalls at
`EGP_BeginInit`) nor the DS-stub route (content-less stock-UE stub can't run the real round; S74
found the hero/gamemode chain also crosses an Angelscript layer) can RECONSTRUCT the round logic —
but the real exe already CONTAINS it. Don't replicate the server; run the real one.

## Why this is architecturally sound (what the disk shows)

- **The server code is IN the shipping client exe.** schema.txt (the game's own reflection) contains
  the full server cluster: `LokiServerPlatformInstance`, `ServerAuthManager`, `ServerCoreGameManager`,
  `ServerEndOfGameManager`, `AgonesManager`, `NexonRegistry`, `LokiServerAnalyticsManager`,
  `LokiServerAuthConfig`, `ELokiServerDebugMode`(26). UE ships client+server in one binary; S73's "no
  DS binary" = no separate build TARGET, NOT that the server code is absent. `bLoadWidgetsOnDedicated
  Server=False` in DefaultEngine.ini is a DS-aware setting = a DS code path exists.
- **`ULokiServerPlatformInstance` is created by `ULokiGameInstance`.** schema.txt:
  `LokiGameInstance : UGameInstance (13 props)` holds `LokiClientPlatformInstance`(59 props),
  `LokiServerPlatformInstance`(5 props), `LokiCommonPlatformInstance`(0). The GameInstance creates the
  SERVER platform instance only when the process runs as a server — that's exactly why force-open
  (client mode) logged "failed to get ULokiServerPlatformInstance": the client never instantiates it.
- **`ULokiServerPlatformInstance`'s 5 members = the DS's external dependency surface:**
  `AuthManager: ServerAuthManager` (DS-side AccelByte login/session),
  `CoreGameManager: ServerCoreGameManager` (server match orchestration — the round logic we couldn't reconstruct),
  `EndOfGameManager: ServerEndOfGameManager`,
  `AgonesManager: AgonesManager` (**Agones** — the open-source K8s game-server SDK; sidecar-based),
  `NexonRegistry: NexonRegistry` (publisher registry).
- **Force-open already PROVED the server gamemode code executes in this exe** (it ran
  BP_LokiGameMode_Tutorial to EGP_BeginInit). So the round machinery is present and runnable; it just
  never gets its ServerPlatformInstance in client mode.
- **★ Net-cache identity = the DS-stub route's biggest cost vanishes.** Two instances of the SAME
  binary have byte-identical FClassNetCache/FClassNetCacheMgr → ZERO class-net-cache divergence. The
  ~15 sessions the stub route spent on schema-injection / mirror alignment / RPC-sig reconstruction
  are simply not needed here. The real exe also uses its real `LokiReplicationGraph`
  (ReplicationDriverClassName=/Script/Loki.LokiReplicationGraph) natively.
- **Client delivery is already solved (S62):** the menu flow fires a real UE NetConnection to
  MatchInfo.ConnectionDetails.address=127.0.0.1:7777 (handshake EngineNetVer 34, GameNetVer 0). Point
  it at the real-exe server instead of the stub.

## The dependency surface to satisfy (to make ULokiServerPlatformInstance init + the round run)

1. **[MAKE-OR-BREAK] The process must actually run as a listening server.** UNKNOWN + the one hard gate.
   The only shipped binary is `SUPERVIVE-Win64-Shipping.exe` (a `-Shipping`, `-WindowsClient`-pak
   flavour). If it were a strict `TargetType.Client` build with `WITH_SERVER_CODE=0`, server code would
   be stripped — but the server classes ARE in the reflection, which contradicts a full strip (→ likely
   a `Game` target in Shipping, or Client with server code retained). Force-open's `?listen` "failed to
   Listen" is the one concrete negative, but that was a LISTEN server inside an already-client process
   (socket already bound / partial path); a clean DEDICATED `-server` launch is the untested, cleaner
   variant. THIS is the first thing to test and it gates everything else.
2. **Agones sidecar.** AgonesManager expects an Agones SDK sidecar (standard: gRPC :9357 / HTTP :9358,
   surface = Ready/Health/Allocate/Shutdown/GameServer/WatchGameServer/SetLabel). Off-the-shelf option:
   run the OFFICIAL `agones sdk-server --local` (Agones ships a local SDK server for exactly the
   "run a DS outside a cluster" case) → possibly zero RE. Fallback: fake the small documented surface in
   Go (ags already does HTTP faking). Low–medium, mostly NOT reverse-engineering.
3. **AccelByte server-side auth/session.** ServerAuthManager does DS-side AccelByte login (client-
   credentials grant) + session claim/registration. Extend ags with the server-side AccelByte endpoints
   (in-domain — we already fake the client side against dev.theorycraft.accelbyte.io / projectloki
   hosts-redirects). Medium.
4. **NexonRegistry.** Publisher registry; likely a light call — redirect to ags. Low.
5. **Match assignment / map+mode.** How the DS learns "host LVL_Tutorial with BP_LokiGameMode_Tutorial
   for these players." On real infra: Agones allocation + AccelByte session carries it. Locally: pass
   map+mode on the DS command line and/or in the faked allocation/session payload. Medium.

## Risk-ranked

- **R1 (make-or-break, cheap to test):** does the client-target Shipping exe stand up a listening
  server at all? One launch answers it. If server code is stripped/hard-disabled → B1 is DEAD.
- **R2 (bounded, partly off-the-shelf):** Agones + AccelByte-server bootstrap so ULokiServerPlatform
  Instance initializes. Agones has an official local server; AccelByte-server is ags-style faking.
- **R3 (unknown):** the packer/anti-tamper (`preloader.dll`) behaviour when the exe is launched in a
  server role / as a 2nd instance (it hooks NtCreateThreadEx; may object to headless/`-server`).
- **R4 (bounded):** the exact match/session shape the DS's ServerCoreGameManager expects before it
  starts the round + drop-in.

## GO / NO-GO

**Conditional GO** — B1 is the only route that leverages the game's OWN correct implementation of the
round/Angelscript/hero (everything the reconstruction routes can't rebuild), AND it deletes the
net-divergence problem via binary-identical net-caches. But its viability rests entirely on R1, which
is a single, cheap, empirical launch test that MUST be run first (needs elevation + Steam, so it's an
execution-session step, not scopeable from disk).

### Phase 0 (the gate — do FIRST, ~1 session, needs live launch)
Launch the shipping exe in a dedicated-server role and see if it stands up a listener:
```
SUPERVIVE-Win64-Shipping.exe \
  /Game/Loki/Maps/Tutorial/LVL_Tutorial?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C \
  -server -port=7777 -log -nosteam    (also try -NetDriverOverrides / without -nosteam; and a listen variant)
```
Watch its log for: "IpNetDriver listening" (or the LokiReplicationGraph/IpNetDriver bind), and whether
`ULokiGameInstance` constructs `ULokiServerPlatformInstance` (expect it to then error on Agones/auth —
that's FINE and expected; it means server mode engaged). 
- GO signal: the process runs as a server (binds a listener) and/or logs ServerPlatformInstance
  creation / an Agones/AccelByte-server error (= it got INTO server bootstrap). → proceed to Phase 1.
- NO-GO signal: server code refuses to run (no listener, immediate exit, "server code not available",
  or it silently behaves as a client). → B1 dead; fall back to B2 (force-open EGP_BeginInit) or bank.

### Phase 1 (if Phase 0 = GO): satisfy the ServerPlatformInstance bootstrap
- Stand up Agones local SDK server (or fake :9357/:9358) so AgonesManager gets Ready/Allocated.
- Add AccelByte server-side auth/session + Nexon endpoints to ags (redirect via existing hosts entries).
- Get `ULokiServerPlatformInstance` fully constructed (all 5 managers) → the DS should advance the round
  past EGP_BeginInit natively (the exact thing both prior routes couldn't do).

### Phase 2: wire the match + connect the client
- Feed the DS the tutorial map+mode + a session the client's S62 flow matches; connect the client
  (already lands on 7777). Because net-caches are identical, the handshake/replication should "just work."
- Expect the REAL round → drop-in → real hero spawn+possess = PLAYABLE (the payoff).

## Bottom line
B1 converts "reconstruct SUPERVIVE's proprietary server (native + Angelscript, no source) — impossible"
into "boot SUPERVIVE's own binary as a server against faked Agones + AccelByte-server — bounded, mostly
in-domain HTTP/SDK faking, with an off-the-shelf Agones local option." The whole bet hinges on the R1
launch test. Recommend running Phase 0 as the next hands-on (elevated + Steam) step before any build work.

## Ground-truth references (this scoping)
- ULokiGameInstance / platform instances: schema.txt L25145-25158.
- ULokiServerPlatformInstance 5 members: schema.txt L27781-27786.
- AccelByte backend URLs + IpNetDriver/LokiReplicationGraph + bLoadWidgetsOnDedicatedServer:
  tools/extractor/out/DefaultEngine.ini (L368-374 net driver; L449 DS widgets; L459+ AccelByte envs).
- Only SUPERVIVE-Win64-Shipping.exe ships (no *Server*.exe / no .target): Loki/Binaries/Win64/.
- Force-open EGP_BeginInit / "failed to get ULokiServerPlatformInstance": [[supervive-tutorial-launch-status]] S63-S68.
- Angelscript layer under the hero/gamemode: docs/session-74-overlay-spike-angelscript.txt.
