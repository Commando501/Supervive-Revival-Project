# FK-5 probe — the latency / region subsystem, reverse-engineered end to end

Date: 2026-07-27. **Offline only.** No game launched, no injection, `server/` NOT modified.
Companion to `docs/fk5-backend-gap-and-regions-negative.md` (same session, backend-gap angle).
That doc reached the same headline from `schema.txt`; this one reaches it from **the game's own
`Binds.Cache` bind table plus x86 disassembly**, which upgrades several of its `[SI]` claims to
`[M]` and adds the ping mechanism, the cadence, the guard order, and a hard gate nobody had seen.

Tags: **[M]** measured (read from an artifact or decoded from instructions) ·
**[SI]** strong inference (every link measured, the joint is reasoned) · **[H]** hypothesis.

Sources: `dumps/merged.dump.exe` (file-offset == RVA, ImageBase `0x7FF6AF000000`) via
`tools/strxref/strxref.py` + `tools/re/offline_disasm.py` + `tools/re/offline_xref.py`;
`tools/asdump/out/binds_{types,members}.csv` (parsed from the shipped `Loki/Script/Binds.Cache`);
`schema.txt`; `tools/extractor/out/catalog/wbp/*.json`.

---

## 0. Headline

**There is no QoS subsystem in the client's matchmaking path.** The region-latency machinery is
100% Theorycraft's own `Services/CoreGame/LatencyManager.cpp` driving **UE's stock ICMP module's
UDP echo**, and it is fed by exactly one route — `GET /core-game/regions`.

**The "we served `PingHost: 127.0.0.1` and the client never pinged" negative is a nesting bug in
our own payload, and it is now explained at instruction level.** `PingHost` is a field of
`FRegionRoute`, which lives inside `FRegionHost.Routes` — a `TMap<FString,FRegionRoute>` we have
never sent. The client parsed our body successfully into **one region with an empty `Routes` map**,
and the measurer-creation loop iterates `Routes`. Zero routes ⇒ zero `ULatencyMeasurer`s ⇒ zero
pings ⇒ zero `POST /latencies` ⇒ the `??? — ms` row and the `ST_ServerLocations['']` lookup.

Everything downstream of that — "is a QoS responder needed?", "is `/latencies` a blocker?" — was
being asked about a pipeline that had never been started.

---

## 1. The data model — **[M]**, from the game's own bind table

`tools/asdump/out/binds_members.csv` is parsed from `Loki/Script/Binds.Cache`, the file the shipping
client itself uses to bind native types to Angelscript. It carries **real C++ declarations**, so it
settles every container type that `schema.txt` renders wrong (FK-22's index shift).

```cpp
// /Script/Loki.*   — verbatim from Binds.Cache
struct FRegionHostList { TArray<FRegionHost> Regions; FString ETag; };          // 32 B
struct FRegionHost     { FString Name; FString Addr; int Port; bool CanExclude;
                         TMap<FString, FRegionRoute> Routes; };                 // 0x78 B
struct FRegionRoute    { bool Enabled; bool IsAccelerator; FString Host; int Port;
                         FString PingHost; int PingPort; bool RequiresToken; }; // 0x38 B
struct FConnectionDetails : FCoreGameServerInfo
                       { FString ConnectionSecret; TMap<FString, FRegionRoute> Routes; };
struct FMemberServerLatency { FString Host; FString Region; FString Route; float AvgLatency; };
struct FMemberLatencies     { TArray<FMemberServerLatency> Latencies; };
struct FExcludedRegions     { TArray<FString> Regions; };
// FPartyMember property #16 : TArray<FMemberServerLatency> Latencies;
// FParty      property #10 : TArray<FString>              ExcludedRegions;

class UCoreGameManager {  TArray<FRegionHost> GetRegions();
                          bool GetRegion(const FString&, FRegionHost& Out) const;
                          bool GetRegionRoute(const FString& Region, const FString& Route, ...); };
class ULatencyMeasurer { const FString& GetHost/GetRegion/GetRoute() const; float GetLatency() const;
                         FOnLatencyUpdated OnLatencyUpdated; };
class ULatencyManager  { bool AllMeasurersReported() const;
                         ULatencyMeasurer GetFastestRegionMeasurer() const;
                         static ULatencyManager GetLatencyManager(UObject WorldContext);
                         bool GetLatencyMeasurer(const FString& Region, const FString& Route, ...);
                         TArray<ULatencyMeasurer> GetLatencyMeasurers(const FString& Region = "",
                                                                      bool bSortAscending = true) const;
                         bool GetRegionRoutePreference(const FString& Region, FString& Route) const;
                         bool SetRegionRoutePreferences(const TMap<FString,FString>&); };
```

> ★ **This closes the "inner-type trap" without a launch.** The companion doc had to mark
> `RegionHostList.Regions`'s element type `[SI]` and propose "one launch settles it". `Binds.Cache`
> states it: `TArray<FRegionHost> Regions`. Same for `MemberLatencies.Latencies`,
> `PartyMember.Latencies`, `FRegionHost.Routes`, `FConnectionDetails.Routes` and
> `FParty.ExcludedRegions` — all of which `schema.txt` renders as `ArrayProperty<StrProperty>`.
> **General lesson: `binds_members.csv` is a better type oracle than `mappings.usmap` for anything
> exposed to script — and it has been on disk since the asdump work.**

**Independent confirmation from the disassembly [M]:** the measurer loop at `fn 0x57DDCA0` advances
its region cursor with `add rbx, 0x78` (`0x57DE1A0`) — `sizeof(FRegionHost)` = 16+16+4+1+pad+0x50
(TMap) = **0x78** — and indexes route elements with `lea r13,[rax+rax*4]; shl r13,4` = stride
**0x50** = `TPair<FString,FRegionRoute>` (16 + 0x38 + TSet link) rounded to 80. Both match exactly.

---

## 2. The pipeline, hop by hop

```
GET /core-game/regions                                   fn 0x57B56B0 (2582 B)  [M]
  |   Bearer auth + If-None-Match; response -> FRegionHostList
  v
UCoreGameManager.ValidRegions  @ CoreGameManager + 0x6F0 (Data) / +0x6F8 (Num)  [M]
  |   broadcasts a delegate at CoreGameManager + 0x98
  v
ULatencyManager::<OnRegionsUpdated>                      fn 0x57DDCA0 (2410 B)  [M]
  |   reads this->[+0x68], then [that+0x6F0]/[+0x6F8] as an FRegionHost array   [M]
  |   ([+0x68] is the object whose delegate at its +0x98 this handler is bound
  |    to, and whose +0x6F0 holds ValidRegions -> it is the CoreGameManager [SI];
  |    [+0x70] is set from the next bind's target -> ClientConfigManager    [SI])
  |   for each FRegionHost R:
  |       if (R.CanExclude == 0) continue;                <-- HARD GATE, 0x57DE016   [M]
  |       for each (RouteName, FRegionRoute Rt) in R.Routes:
  |           if (measurer for hash(R.Name ^ RouteName) exists) continue;
  |           CreateMeasurer(this, &R.Name, &RouteName, &Rt.PingHost, Rt.PingPort);
  v
ULatencyManager::CreateMeasurer                          fn 0x57BECF0 (862 B)   [M]
  |   LogLatencyManager: Display: "Creating new latency measurer for %s %s"  (Region, Route)
  |   NewObject<ULatencyMeasurer>;
  |     M->Host  = Rt.PingHost   (+0x40)      M->Region = R.Name  (+0x50)
  |     M->Route = RouteName     (+0x60)      M->Port   = Rt.PingPort (+0x70)
  |   SetTimer(M->PingHostHandle @ +0x88, rate = 29.75 + Rand()/32768, bLooping = true)   [M]
  v
ULatencyMeasurer::PingHost                               fn 0x57CB950 (688 B)   [M]
  |   bUpdatingLatency (+0x74) = 1
  |   Address = Format("{0}:{1}", Host, Port)    // literal at 0x08B24050
  |   <ICMP module UDP echo>(Address, Timeout = 5.0f, Callback = fn 0x57DAAF0)
  |                                        ^ float at 0x76D5AC0 = 5.0            [M]
  v
result callback                                          fn 0x57DAAF0 / 0x57DAB63 [M]
  |   on failure: LogLatencyManager: Warning:
  |               "Could not ping target host: %s:%d. Result: %d"
  |   Latencies (TArray<float> @ +0x78) .Add(sample);  ++Received (+0x90)
  |   when Received == 5:  bUpdatingLatency = 0; Received = 0;
  |                        bHasReceivedPings (+0x98) = 1;  average the 5 samples;
  |                        broadcast OnLatencyUpdated -> ULatencyManager::OnLatencyUpdated
  |                                                      (bound at fn 0x57DDCA0 + 0x3A9)
  v
UPartyManager  <"OnAllPingsReceived">  (bound in fn 0x584ED20 + 0x39B)          [M]
  v
UPartyManager::SetLatencies  — PartyManager.cpp ~285-380 — POST .../latencies   [M]
```

### 2.1 `ULatencyMeasurer` live offsets (for a future shim) — **[M]**

Derived from `fn 0x57BECF0` stores + `fn 0x57DAB63` reads; the property list in `schema.txt:21984`
maps onto it exactly, which also fixes this build's `UObject` size at **0x30** and its
`FMulticastInlineDelegate` at 16 bytes.

| offset | field |
|---|---|
| `+0x30` | `OnLatencyUpdated` (multicast, 16 B) |
| `+0x40` | `Host` (FString) — **from `FRegionRoute.PingHost`** |
| `+0x50` | `Region` (FString) — from `FRegionHost.Name` |
| `+0x60` | `Route` (FString) — the `Routes` map key |
| `+0x70` | `Port` (int32) — **from `FRegionRoute.PingPort`** |
| `+0x74` | `bUpdatingLatency` |
| `+0x78` | `Latencies` — **`TArray<float>`**, not `TArray<FTimerHandle>` (usmap is wrong) |
| `+0x88` | `PingHostHandle` (FTimerHandle) |
| `+0x90` | `Received` (int32, counts to 5) |
| `+0x94` | `PreviousLatency` (float) |
| `+0x98` | `bHasReceivedPings` |

---

## 3. Why `/core-game/regions` produced silence — four independent measurements

What `interactive.go:718` serves today:

```json
{"Regions":[{"RegionName":"na","RouteName":"na","DisplayName":"Local",
             "Host":"127.0.0.1","PingHost":"127.0.0.1","Address":"127.0.0.1",
             "Port":443,"Enabled":true}]}
```

Against `FRegionHost{Name, Addr, Port, CanExclude, Routes}` **only `Port` matches**. Result:

| cause | evidence | tag |
|---|---|---|
| **(a) `Routes` is absent** ⇒ the inner `for (Route : R.Routes)` never iterates | `fn 0x57DDCA0` walks `Routes`' `TBitArray` allocation flags at region `+0x48/+0x50` | **[M]** |
| **(b) `PingHost`/`PingPort` are at the wrong nesting level** ⇒ even a route would have no host | `fn 0x57BECF0` seeds `Host`/`Port` from args 4/5, which `0x57DE020` loads as `[route+0x30]` (`PingHost`) and `[route+0x40]` (`PingPort`) | **[M]** |
| **(c) `CanExclude` defaults to `false`** ⇒ the whole region is skipped *before* the route loop | `cmp byte ptr [rbx-0x24], 0 ; je skip` at `0x57DE016`, with `rbx` = region+0x48 advancing by 0x78 | **[M]** |
| **(d) `Name` is `""`** ⇒ the widget looked up an empty display key | live `Loki.log:2151` `ST_ServerLocations` lookup with key `''` | **[M]** |

**Any one of (a)/(c) alone is sufficient.** The remedy must fix all four.

### 3.1 The corroborating silence is stronger than the companion doc allowed

`docs/fk5-backend-gap-and-regions-negative.md` §2.1 hedged: *"the measurer-creation line may be
`Verbose` and suppressed in Shipping."* **It is not.** Decoding the `FStaticLogRecord` structs
(`{const TCHAR* Format; const ANSICHAR* File; int32 Line; ELogVerbosity Verbosity; void* Dynamic}`)
straight out of `.rdata`:

```
LatencyManager.cpp:315  Display  "Creating new latency measurer for %s %s"
LatencyManager.cpp:346  Warning  "Could not ping target host: %s:%d. Result: %d"
LatencyManager.cpp:236  Warning  "Invalid minRouteLatencyDifference value: %s"
```

`Display` and `Warning` both print at default shipping verbosity. **⇒ zero `LogLatencyManager`
lines across 12 logs is direct evidence that no measurer has ever been created — not merely
suppressed logging.** **[M]**

### 3.2 The instruction-level confirmation nobody has had

`ULatencyMeasurer::PingHost` (`fn 0x57CB950`) calls into the ICMP module at **`0x1F8CFC0`**.
That address, and every byte for pages around it, reads **all-zero in `merged.dump.exe`** — an
undecrypted page. Demand-decrypt only zeroes pages that have never *executed*.

> **⇒ The UDP-echo implementation has never run in any captured state of this client.** Not "it ran
> and timed out" — it was never entered. **[M]**

The same test on `UPartyManager::TryJoinQueue` (impl `0x5875E90`, resolved via
`strxref native TryJoinQueue`) also reads all-zero: **the client has never called `TryJoinQueue`
either** — consistent with the diagnostic queue trim (`queueIDs` = tutorialNew/training/practice/bots)
leaving no real queue to click. **[M]**

---

## 4. `POST .../latencies` — exact preconditions, with source line numbers

All nine guards live in `Loki/Source/Loki/Services/Party/PartyManager.cpp`. Line numbers and
verbosities decoded from the `FStaticLogRecord`s at `.rdata 0x08B4B1F8-0x08B4B690`: **[M]**

| line | verbosity | message | meaning |
|---:|---|---|---|
| 294 | **Verbose** | `skipping set latencies, no valid party` | no `FParty` object at all |
| 300 | **Verbose** | `skipping set latencies, party state: %s` | `Party.State` not in the allowed set |
| 315 | Warning | `skipping set latencies, player not in party` | self not found in `Party.Members` |
| 322 | **Verbose** | `skipping set latencies, no changes` | no measurer produced a new value |
| 339 | Log | `setting changed latency,  Host: %s, Region: %s, Route: %s, current: %f, prior: %f, chg: %f` | per-route, delta path |
| 347 | Log | `setting new latency, Host: %s, Region: %s, Route: %s, current: %f` | per-route, first-value path |
| 362 | **Verbose** | `skipping set latencies, no changes over set threshold` | Σ delta < `minLatencyDifference` |
| 369 | Log | `Member latencies set` | POST success — `fn 0x585D1E0` (69 B) |
| 376 | Error | `Failed to set latencies, status: %d, connected: %hhd, msg: %s - %s` | POST failure — `fn 0x585D230` (144 B) |

Control flow: **guards 294/300/315 → build the payload (339/347) → threshold guard 362 → POST.**
The payload is `FMemberLatencies{ TArray<FMemberServerLatency> }`, one element per measurer —
`Host`/`Region`/`Route`/`AvgLatency` are literally the four `%s %s %s %f` of lines 339/347 and the
four fields of `FMemberServerLatency`. **[M]**

`Party.State` values: `EPartyState::{Default=0, Matchmaking=1, CustomGame=2, Unknown=3}`
(`schema.txt:65623`). Which subset line 300 admits is **not** resolvable offline — that whole
function is on a dark page. **[SI]**: `Default` and `Matchmaking` are the plausible pass set;
`buildSoloParty` currently serves no `State` at all.

> ⚠ **Experiment-design consequence — this is the part that would waste a session.**
> **Four of the five skip reasons are `Verbose`.** In the default shipping configuration they do
> **not** print, so a run that stalls at guard 294/300/322/362 looks *identical to a run where
> nothing happened at all*. The launcher already passes `-ini:` overrides
> (`configs/launch-redirect.ps1:299-310`), and FK-11 established that `[Core.Log]` is live in this
> build, so add:
> ```
> -ini:Engine:[Core.Log]:LogPartyManager=Verbose
> -ini:Engine:[Core.Log]:LogLatencyManager=Verbose
> ```
> (or `-LogCmds="LogPartyManager Verbose, LogLatencyManager Verbose"`).
> The *positive* signals (`Creating new latency measurer` = Display, `Could not ping target host`
> = Warning, `Member latencies set` = Log) print without it — so the verbosity bump buys the
> **negative** diagnosis, which is exactly what an A/B needs.

---

## 5. The ping mechanism — what is actually compiled in, and what answers it

### 5.1 It is a **UDP echo**, not ICMP, and not AccelByte QoS — **[M]/[SI]**

* `ULatencyMeasurer::PingHost` formats the target as **`{0}:{1}`** — host **and port** (`0x08B24050`).
  UE's own `FNetPing` diagnostics say *"`EPingType::ICMP` should not specify a port number"*
  (`0x081501D0`), and its UDP counterpart takes `PingAddress, PingPort` (`0x08150290`). A port ⇒
  UDP. **[SI]**, on measured strings.
* The ICMP-module TU (`.rdata 0x079C6B70-0x079C6F00`) holds, in order:
  `>>>>This string is 32 bytes<<<<` (UE's stock ICMP echo payload), `LogIcmp`, `Icmp`, `LogPing`,
  `StackSize`, `Ping`, the `Icmp Ping <url>` console-command help, `IcmpModule.cpp`,
  `Ping success/failure`, `127.0.0.1`, **`UDPPing`**, **`LokiPing`**, `Error converting Ip Address`,
  `IcmpWindows.cpp`. `Ping` and `UDPPing` are the two worker-thread names UE creates for
  `FIcmp::IcmpEcho` and `FUDPPing::UDPEcho`. **Both paths are compiled in.** **[M]**
* **`LokiPing` (`0x079C6E80`) is a Theorycraft insertion into a stock Epic TU.** Raw bytes:
  `4c 6f 6b 69 50 69 6e 67 00 …` — **8 ANSI characters, NUL-terminated, 16-byte padded**, sitting
  between the wide thread name `UDPPing` and `IcmpWindows.cpp`'s own
  `FStaticLogRecord` (`Error converting Ip Address: 0x%08x`, line 60, Warning). Its neighbours are
  Epic's; it is not — and **ANSI** is the tell: UE passes socket descriptions as `FString`
  (UTF-16), so an 8-byte ANSI literal in a ping TU reads as a **packet magic/payload**. **[SI]**
  ⇒ *do not assume the stock UE packet format.*
* The module's ICMP *registration* code is decrypted (`fn 0x1F8B2B0`, `fn 0x1F8B2F8` — the
  `Icmp Ping` console command), so the module is genuinely linked and initialised; only the *echo
  implementation* (`0x1F8CFC0`) is dark. **[M]**

**Cadence, measured from the image:** first ping at `29.75 + Rand()/32768` seconds after the
measurer is created (`29.75f` @ `0x8B4A180`, `1/32768f` @ `0x81518B8`), **looping** (`SetTimer` with
`bLooping=1` at `0x57BEF72`); timeout **5.0 s** per ping (`0x76D5AC0`); **5 samples** per completed
measurement (`cmp eax, 5` @ `0x57DABA8`), then averaged. So a working responder yields a first
`OnLatencyUpdated` roughly **30 s** after the regions payload lands, and a `POST /latencies`
shortly after. A *broken* responder yields a `Could not ping target host: …` Warning every ~30 s.

> ⚠ **We cannot read the packet format offline** — the page is undecrypted. Design the responder to
> **echo the datagram back verbatim and hexdump it**. A verbatim echo satisfies both stock UE UDP
> ping and any `LokiPing`-flavoured variant, and the hexdump *tells us the format for free* on the
> first packet. This is the single highest-information-per-effort artifact in the whole area.

### 5.2 `FNetPing` / `ServerSetPingAddress` — real, server-driven, and a **different subsystem**

* `FNetPing` is UE stock (`Engine/Private/Net/NetPing.cpp`), gated by `net.NetPingEnabled` /
  `net.NetPingTypes` / `net.NetPingUDPPort`. **Every one of those cvar strings has refs=0** in the
  decrypted 52% — no decrypted code registers or reads them. **[M]** (not proof of absence).
* The server→client push exists and is located: `fn 0x3F745E0` (1025 B) builds the URL options
  **`ClientNetPingICMPAddress=%i=%s`** and **`ClientNetPingUDPAddress=%i=%s`**, called from
  `fn 0x3F64BC0`. That is UE appending ping addresses to the **NetConnection join URL** — i.e. a
  live-match feature our own DS stub *could* drive. **[M]**
* **But it is not this pipeline.** `FNetPing` measures the in-match connection for HUD ping /
  net analytics. Region selection for matchmaking runs entirely through `ULatencyManager` →
  `FRegionRoute.PingHost:PingPort` → `FPartyMember.Latencies`. The two never meet: no decrypted
  code path connects `FNetPing` to `ULatencyManager`, and `ULatencyMeasurer` has its own socket
  path. **[SI]**
* Verdict: `ServerSetPingAddress` is a **real future capability for the DS route** (in-match ping
  display against our stub) and **irrelevant to BATTLE/PRACTICE**. Chasing it now is a detour.

### 5.3 AccelByte QoS — where the FK-5 belief came from

The AccelByte SDK's QoS types are present (`FAccelByteModelsQosRegionLatency{Region, Latency}`,
`FAccelByteModelsQosRegionLatencies{TArray<...> Data}`, `QosLatencyPollIntervalSecs`,
`QosServerLatencyPollIntervalSecs`) — they are *linked SDK surface*, and
`FAccelByteModelsV2MatchmakingCreateTicketRequest.Latencies` is a `TMap<FString,int>` on a
matchmaking ticket the client never creates. **None of it is wired to `ULatencyManager`, and
`QosManagerServerUrl=` is empty in all 12 environments.** The QoS belief was pattern-matching an
SDK's presence onto a game that reimplemented the feature. **[SI]**

---

## 6. `ClientConfiguration` is **not** the region source — the FK-5 register's other lever, closed

`ULatencyManager::OnClientConfigUpdated` = **`fn 0x57DC9CD`** (1377 B), and it touches exactly
four literals, in order: **[M]**

```
+0x1DC  'coregamerouting'                              (ANSI)
+0x20B  'minLatencyDifference'                         (ANSI)
+0x2E2  'minRouteLatencyDifference'                    (ANSI)
+0x3AB  'Invalid minRouteLatencyDifference value: %s'  (LatencyManager.cpp:236, Warning)
```

`FClientConfiguration` has 12 properties (`ClientVersions, ServiceHostnames, FeatureToggles,
PlaytestEnabled, PlaytestWindows, InventoryFreeVersion, StatusMessages, VendorConfigs,
CohortConfigs, BannerConfigs, ETag, LastUpdated`) — **no region, host, route or latency container.**

> **Answer to the register's "the region list may ride `ClientConfiguration`": no.** Client config
> contributes two float *thresholds* under the `coregamerouting` key — the hysteresis that guard
> 362 (`no changes over set threshold`) applies. The region/route table travels on
> `/core-game/regions` and nowhere else. Recording otherwise would be FK-5's mirror image.

---

## 7. Can measurement be bypassed by simply **serving** the values? — honest verdict

**Mechanically: yes, we can serve them. Usefully: no, it buys nothing today.** Three separate
consumers, and the served value reaches none of the ones that matter:

1. **The UI does not read the party document.** The extracted widgets are decisive:
   `WBP_UI_RegionLatency` calls `GetLatencyManager` → `GetLatencyMeasurer` → **`GetLatency()`**, and
   `WBP_UI_RegionSelect_Entry` calls `GetLatencyMeasurers` → `GetLatency` → `Get_Color_for_Latency`.
   Both read the **local `ULatencyMeasurer`**. `FPartyMember.Latencies` is *not* bound to any
   widget — a grep for `MemberServerLatency|AvgLatency` across every extracted `catalog/wbp/*.json`
   returns **zero files**, while `GetLatencyManager`/`GetLatencyMeasurer(s)`/`GetLatency` appear in
   eight. **⇒ Serving latencies will NOT clear the `??? — ms` row.** Only a real measurer will.
   **[M]** (`tools/extractor/out/catalog/wbp/WBP_UI_RegionLatency.json`,
   `WBP_UI_RegionSelect_Entry.json`)

2. **The matchmaker that consumes member latencies is us.** `FPartyMember.Latencies` exists so a
   real matchmaker can pick a server region. Our backend hard-codes the match address
   (`buildTutorialMatchInfo`, `127.0.0.1:7777`). Serving them is a no-op on our own decision.
   **[M]**

3. **Any client-side "pings are done" gate is unaffected by served values.** `UPartyManager`
   subscribes to an **`OnAllPingsReceived`** event and `ULatencyManager` exposes
   **`AllMeasurersReported()`**; both are local-measurer state that no HTTP payload can set.
   Whether a queue-join path actually consults them is **unresolved offline** — `TryJoinQueue`'s
   implementation page is undecrypted. **[M]** that the subscription and the predicate exist;
   **unknown** whether they gate. Note `GetFastestRegionMeasurer`'s implementation (`0x57AE540`) has
   exactly **one** caller in decrypted code — its own exec thunk — i.e. its consumers are
   Blueprint/UI, not native C++. **[M]**, with the 48%-dark caveat.

**Therefore:** serve `FPartyMember.Latencies` only as *cheap insurance* against an unseen native
read (it costs four fields and cannot break parsing — unknown keys are ignored, and the type is now
known exactly, so it cannot mistype). **Do not treat it as a substitute for fixing
`/core-game/regions`.** The fix and the fake are not interchangeable: only the fix produces
measurers, and measurers are what the UI and any `AllMeasurersReported` gate actually read.

---

## 8. The Angelscript layer — **zero involvement** **[M]**

A case-insensitive search for `latenc|region|ping|LatencyManager|LatencyMeasurer` across all
**78 decompiled modules** (`tools/asdump/out/modules/**`, 110 classes / 1,463 functions) returns
**no matches**. The only hits anywhere under `out/` are in the three `binds_*.csv` files, which are
the native bind table, not script. The latency/region subsystem is entirely native C++ — no script
hook exists to intercept, and no script gate can be blocking it.

---

## 9. Proposed backend changes — **NOT APPLIED** (`server/` untouched)

### D1 — `handleCoreGameRegions`: emit a real `FRegionHostList` ★ the whole probe reduces to this

`server/internal/interactive/interactive.go:718-732`. Keep the existing comment block; append the
2026-07-27 findings. Shape (types now **[M]** from `Binds.Cache`, not guessed):

```go
route := map[string]any{
    "Enabled":       true,
    "IsAccelerator": false,
    "Host":          "127.0.0.1",   // FRegionRoute.Host  — game-server address for this route
    "Port":          7777,          // FRegionRoute.Port  — the DS stub
    "PingHost":      "127.0.0.1",   // FRegionRoute.PingHost -> ULatencyMeasurer.Host
    "PingPort":      7778,          // FRegionRoute.PingPort -> ULatencyMeasurer.Port  (UDP echo)
    "RequiresToken": false,
}
region := map[string]any{
    "Name":       "na",             // FRegionHost.Name  -> measurer.Region, ST_ServerLocations key
    "Addr":       "127.0.0.1",
    "Port":       7777,
    "CanExclude": true,             // ★ REQUIRED: false skips the region before the route loop
    "Routes":     map[string]any{"default": route},   // ★ TMap<FString,FRegionRoute>
}
writeJSON(w, map[string]any{"Regions": []any{region}, "ETag": "revival-regions-v1"})
```

Risks / notes:
* `PingPort` **must not** be 7777 if the DS stub owns that UDP port — UE's netdriver would eat the
  echo. 7778 keeps them disjoint.
* `ETag`: `fn 0x57B56B0` sends `If-None-Match` **[M]**; the current handler omits `ETag` (so the
  header is empty) and the payload demonstrably parses 7×/session. Adding a *stable* ETag is the
  small risk that the client short-circuits a re-parse. **Ship the fix with `ETag` omitted first**;
  add it only if repeat-parsing turns out to be needed.
* `"Name"` is also the `ST_ServerLocations` string-table key. `"na"` may still miss the table (the
  packed entry set is unknown) — that would show as a *different* warning with a *non-empty* key,
  which is itself the confirmation that the name landed.

### D2 — register `POST .../latencies` (both candidate paths) with a logging echo handler

`/latencies` is one of the party sub-routes in the `.rdata` table at `0x08B4C1B8-0x08B4C4D0`
(neighbours: `/setExcludedRegions`, `/referral`, `/leave`, `/joinQueue`). Its call site is on a dark
page, so the base is unresolved. Register **both** `POST /party/parties/{id}/latencies` and
`POST /party/players/{id}/latencies`; the loser never fires and `docs/capture.log` names the winner.
Body: `{"Latencies":[{"Host","Region","Route","AvgLatency"}]}`. The success callback is 69 bytes and
logs one field-less line ⇒ it reads nothing from the response **[SI]** — echo the party document,
as `startSoloMode` does. **Store the values onto the party member and bump `partyVersion()`**
(the S85 monotonic-`FParty.Version` gate).

### D3 — serve `FPartyMember.Latencies` (cheap insurance only — see §7)

`buildSoloParty`: `"Latencies": [{"Host":"127.0.0.1","Region":"na","Route":"default","AvgLatency":3.0}]`.
Type now exact, so it cannot mistype. **Will not** clear the `??? — ms` display.

### D4 — a UDP echo responder + hexdump (new, ~40 lines, own goroutine)

Bind `127.0.0.1:7778/udp`; on each datagram: log `len` + hexdump + source, then **write the bytes
back verbatim** to the sender. Verbatim echo satisfies stock UE UDP ping and any `LokiPing` variant;
the hexdump recovers the packet format we cannot read offline (§5.1). Gate it behind a flag so it
never fights the DS stub for a port.

### D5 — restore the queue list (already-known prerequisite, restated because it is upstream)

`queueIDs` is trimmed to `tutorialNew, training, practice, bots` as an S60 diagnostic, and
`TryJoinQueue`'s implementation page is **provably never-executed [M]**. Nothing about latency can
be tested through BATTLE/PRACTICE until a real queue id is advertised behind a served account level.

---

## 10. The decisive experiment — one launch, four bits

**Preconditions:** apply **D1** (+ D2, D4 if cheap), and add
`-ini:Engine:[Core.Log]:LogLatencyManager=Verbose` and `-ini:Engine:[Core.Log]:LogPartyManager=Verbose`.
Steam running first. Sit at the main menu **≥ 90 s** (the first ping is ~30 s after the regions
payload; a full 5-sample average needs up to ~2.5 min).

Read `Loki.log` + `docs/capture.log` for, in order:

| # | Signal | Reads |
|---|---|---|
| 1 | `LogLatencyManager: Display: Creating new latency measurer for na default` | **The regions negative is fully closed.** The shape bug was the whole story. |
| 1′ | *no* such line, **and** a `LogJson`/`LogLokiPlatformQuery` error naming `Regions` | the element type or a field name is wrong — the client names it, exactly as it did for `Queues` |
| 1″ | *no* such line, **no** parse error | still a semantic miss: check `CanExclude`, then `Routes` key casing |
| 2 | `LogLatencyManager: Warning: Could not ping target host: 127.0.0.1:7778. Result: N` | measurer alive; **the responder is the only missing piece** — and `Result: N` names the UE failure enum |
| 3 | D4's hexdump prints a datagram | **the packet format, recovered.** Highest-value artifact here. |
| 4 | `LogPartyManager: Log: setting new latency, Host: … Region: na Route: default` then either `Member latencies set` or a `Verbose` skip naming its guard | the `/latencies` preconditions, resolved by name — including which `Party.State` values guard 300 admits |

**What this settles about FK-5:** if bits 1 and 2 fire, the "QoS UDP ping responder" belief is
*half* right in mechanism (a UDP responder is genuinely needed) and *wholly* wrong in attribution
(it is UE's ICMP-module UDP echo against **our own** `PingHost:PingPort`, ~40 lines of Go, not an
AccelByte QoS service). If bit 1 does not fire, the blocker was never latency at all and the fix
list moves to §9 D5.

---

## 11. Address reference

| what | address |
|---|---|
| `UCoreGameService::<GetRegions>` — `GET /core-game/regions`, `Bearer`, `If-None-Match` | `fn 0x57B56B0` (2582 B) |
| `ULatencyManager::<OnRegionsUpdated>` — region/route loop, `CanExclude` gate @ `+0x376` | `fn 0x57DDCA0` (2410 B) |
| `ULatencyManager::CreateMeasurer` — `Creating new latency measurer for %s %s` | `fn 0x57BECF0` (862 B) |
| `ULatencyManager::OnClientConfigUpdated` — `coregamerouting` thresholds | `fn 0x57DC9CD` (1377 B) |
| `ULatencyManager::GetFastestRegionMeasurer` (impl) | `fn 0x57AE540` (560 B) |
| `ULatencyMeasurer::PingHost` — `{0}:{1}`, timeout 5.0 | `fn 0x57CB950` (688 B) |
| ping-result callback / failure log | `fn 0x57DAAF0`, cold block `fn 0x57DAB63` (363 B) |
| ICMP-module UDP echo entry (**undecrypted**) | `0x1F8CFC0` |
| ICMP module registration / `Icmp Ping` console cmd | `fn 0x1F8B2B0` (72 B), `fn 0x1F8B2F8` (363 B) |
| manager construction + `ULatencyManager` binds (`[LM+0x68]=CoreGameManager`, `[LM+0x70]=ClientConfigManager`) | `fn 0x57BA080` (3914 B) @ `+0x441`.. |
| `UPartyManager` construction + `OnAllPingsReceived` bind | `fn 0x584ED20` (3474 B) @ `+0x39B` |
| `POST /latencies` success / failure callbacks | `fn 0x585D1E0` (69 B) / `fn 0x585D230` (144 B) |
| `UPartyManager::TryJoinQueue` (impl, **undecrypted**) | `0x5875E90` |
| `FNetPing` client ping-address URL options | `fn 0x3F745E0` (1025 B), caller `fn 0x3F64BC0` |
| `FStaticLogRecord`s for the `set latencies` guards | `.rdata 0x08B4B1F8 … 0x08B4B690` |
| `LatencyManager.cpp` string cluster | `.rdata 0x08B43230 … 0x08B43480` |
| ICMP-module string cluster (incl. `UDPPing`, **`LokiPing`**) | `.rdata 0x079C6B70 … 0x079C6F00` |
| party route table (`/latencies`, `/setExcludedRegions`, `/joinQueue`, …) | `.rdata 0x08B4C1B8 … 0x08B4C4D0` |
