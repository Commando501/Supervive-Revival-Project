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

---

## ★ PHASE 0 RESULT (2026-07-12, RAN LIVE) — naive `-server` is a NO-GO; `IsRunningDedicatedServer()` is gated off.

Launched the real exe directly (elevated shell, Steam up, 7777 free — S73 stack had already exited):
`SUPERVIVE-Win64-Shipping.exe /Game/Loki/Maps/Tutorial/LVL_Tutorial?game=.../BP_LokiGameMode_Tutorial_C
-server -port=7777 -log -unattended -nosplash`. (Log defaulted to `Binaries\Win64\Loki.log` — the
`-abslog` path had spaces and `Start-Process` doesn't quote array elements; the *rest* of the cmdline,
including `-server`, parsed correctly per `LogInit: Command Line:`.)

**It ran as a CLIENT, ignoring `-server`:**
- `LogLokiGameInstance: Warning: initializing game instance for **client**`
- Initialized **D3D12 RHI** + **CEF browser** (a real dedicated server uses the NULL RHI — proof it is
  NOT in dedicated mode; `-server` on a dedicated-capable build would skip D3D12).
- **Ignored the positional `LVL_Tutorial?game=...` URL** and did the normal startup
  `UEngine::Browse "/Game/Loki/Maps/LVL_Login?Name=Player"` → client login flow (libcurl connects to the
  dead `accounts.projectloki` / `client-config` hosts — ags/redirect weren't up, irrelevant to the verdict).
- NO `IpNetDriver`/`InitListen`/`listening`, NO `LokiServerPlatformInstance` construction — no server path
  ever engaged. (The **Agones PROJECT plugin DID mount** — server *code* is present, just never entered.)

**Root cause (fundamental UE, not a fluke):** `IsRunningDedicatedServer()` /
`FPlatformProperties::IsServerOnly()` is a COMPILE-TIME property of the build TARGET. A cooked shipping
Client/Game monolithic build is game-only → `IsRunningDedicatedServer()` returns FALSE regardless of the
`-server` switch. Dedicated mode requires the separate `<Game>Server-Win64-Shipping.exe` (Server target),
which **does not ship** (S73). So the `-server` switch cannot turn this binary into a dedicated server.

**Also closes the listen-server sub-variant at startup:** the client startup force-browses `LVL_Login`
and ignores a positional `?listen` URL; and the force-open route already tried runtime `open …?listen`
(S64) → "failed to Listen". So neither dedicated nor listen engages from this binary the easy way.

### Refined verdict + remaining lever
- **Naive B1 (2nd exe as a dedicated server via `-server`): DEAD** — confirmed, fundamental gating.
- **B1′ (the only remaining B1 form): patch the mode gate at runtime** — shim
  `IsRunningDedicatedServer()` / `FPlatformProperties::IsServerOnly()` (and/or the LokiGameInstance
  client/server branch that logs "initializing game instance for client") to force the DEDICATED path,
  the same class of native patch the force-open route used. VIABILITY signal: server classes
  (LokiServerPlatformInstance/ServerAuthManager/…) are in the reflection AND the Agones *project plugin*
  mounts → server code appears COMPILED IN (likely a Game target, WITH_SERVER_CODE=1), so forcing the
  flag *might* light up the dedicated path. RISK: hostile packer (static RE dead; the ~3–5 min integrity
  check kills persistent .text patches — must be transient/self-restoring), the flag is read VERY early
  (before/at engine init — must patch pre-init, harder than the mid-run vtable patches force-open did),
  and if it's actually a strict Client target the server paths may be only partially linked. Uncertain,
  deep, multi-session.
- Fallbacks unchanged: **B2** (force-open past EGP_BeginInit — stalled S66–S68) or **bank** S70/S73.

Recommendation: this is a decision point. Naive B1 is closed; B1′ is a genuine but deep/uncertain
native-patch effort (turn the client into a dedicated server by flipping the compile-time-ish mode gate).
Worth it only if committing to that RE; otherwise bank S70/S73.

---

## ★ B1′ SCOPING (2026-07-12, read-only, from STOCK UE 5.4 SOURCE) — B1′ is ALSO a NO-GO. The mode gate is a compile-time constant, not a runtime flag.

Read the authoritative, packer-independent source (H:\Unreal Engine\UE_5.4):

`Core/Public/Misc/CoreMisc.h` — `IsRunningDedicatedServer()` is `FORCEINLINE`:
```cpp
if (FPlatformProperties::IsServerOnly()) return true;     // compile-time
if (FPlatformProperties::IsGameOnly())   return false;    // compile-time
#if UE_EDITOR  ...-server parse...  #else  return false;  #endif   // shipping non-editor: HARD false
```
`Core/Public/Windows/WindowsPlatformProperties.h` — `FWindowsPlatformProperties<HAS_EDITOR_DATA,
IS_DEDICATED_SERVER, IS_CLIENT_ONLY>`, all `static FORCEINLINE` returning compile-time literals:
`IsServerOnly() => IS_DEDICATED_SERVER`, `IsGameOnly() => UE_GAME`, `IsClientOnly() => IS_CLIENT_ONLY`.

For this shipping build (WindowsClient paks → Client target: `IS_DEDICATED_SERVER=false`, `UE_GAME=1`):
`IsRunningDedicatedServer()` = `false ? … : (true ? false : …)` = **compile-time `false`**, and being
`FORCEINLINE` it is FOLDED into a literal `false` at EVERY call site (hundreds, scattered, packer-protected).

**⇒ There is no runtime flag to patch.** "Force dedicated mode" is not flipping one boolean; it's rewriting
every folded branch across the binary — not feasible. SUPERVIVE's `LogLokiGameInstance: initializing game
instance for client` IS that folded branch resolving to the client side (evaluated at GameInstance init).

### Does the LISTEN-server sub-path survive? No — already empirically closed.
Listen server (world NetMode `NM_ListenServer`) is runtime and does NOT need `IsRunningDedicatedServer()`.
But: (1) force-open's runtime `open …?listen` already **"failed to Listen"** (S64); and (2) DECISIVE —
force-open DID run the real `BP_LokiGameMode_Tutorial` as authority in the client process (S63-S65) and
STILL logged **"failed to get ULokiServerPlatformInstance"**, proving `ULokiServerPlatformInstance` creation
is gated on the compile-time-`false` dedicated check, NOT on world authority/net-mode. So even a working
listen server would not create the server platform instance → same EGP_BeginInit round-start wall.

### Verdict: the entire "real exe as the server" family (B1 + B1′) is CLOSED, on fundamental UE grounds.
Dedicated-server is a compile-time BUILD-TARGET property. Only the CLIENT target shipped; the mode is baked
to `false` and folded, so no patch turns the client binary into a server, and the listen-server alternative
neither binds nor creates the ServerPlatformInstance (force-open proved both). A playable tutorial needs
SUPERVIVE's **Server-target binary** (or source), which we do not have. All four routes now converge on the
same conclusion. **The reasonable-effort AND current-artifacts ceiling is the S70/S73 spectator milestone.**
IF the Server-target `…Server-Win64-Shipping.exe` is ever obtained, the entire S70-S73 net stack + the S62
client-delivery flow become immediately useful (that binary + faked Agones/AccelByte-server = B1 as intended).

## Ground-truth references (this scoping)
- ULokiGameInstance / platform instances: schema.txt L25145-25158.
- ULokiServerPlatformInstance 5 members: schema.txt L27781-27786.
- AccelByte backend URLs + IpNetDriver/LokiReplicationGraph + bLoadWidgetsOnDedicatedServer:
  tools/extractor/out/DefaultEngine.ini (L368-374 net driver; L449 DS widgets; L459+ AccelByte envs).
- Only SUPERVIVE-Win64-Shipping.exe ships (no *Server*.exe / no .target): Loki/Binaries/Win64/.
- Force-open EGP_BeginInit / "failed to get ULokiServerPlatformInstance": [[supervive-tutorial-launch-status]] S63-S68.
- Angelscript layer under the hero/gamemode: docs/session-74-overlay-spike-angelscript.txt.
