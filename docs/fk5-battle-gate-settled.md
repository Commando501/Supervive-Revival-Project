# FK-5 SETTLED — "The BATTLE/PRACTICE blocker is an AccelByte QoS UDP ping responder"

**S105 · 2026-07-27 · offline only (no launch, no injection, `server/` unmodified)**

Supersedes the FK-5 entry in `docs/ignorance-map-s101.md` and the two carrying lines in
`docs/coverage-audit-s101.md` (`:149`, `:572`). Consolidates and *corrects* four parallel
investigations (`docs/fk5-latency-subsystem-re.md`, `docs/fk5-battle-practice-gate-s105.md`,
`docs/fk5-backend-gap-and-regions-negative.md`, `docs/fk5-live-probe-plan.md`) plus two
adversarial reviews.

**Evidence tags used throughout.** `[M]` = measured this session, by me, from a primary source
named inline. `[M*]` = measured by a sibling investigation and independently re-measured by me.
`[SI]` = strong inference, with the measured parts and the inferred joint separated. `[U]` = unknown.
There is no fourth tag: if it is not tagged, it is not a claim.

---

## 0. One-paragraph answer

**FK-5's named blocker does not survive.** There is no AccelByte QoS anything on the BATTLE or
PRACTICE path — the subsystem the belief named is linked but unwired, and the machinery that *is*
populated is Theorycraft's own `ULatencyManager` driving a UDP echo. **But this document does not
hand you a replacement culprit, because the honest state is "not QoS, and the gate past the tile is
unknown."** What *is* new and decisive: the entire chain from tile-render to the native
`UPartyManager::TryJoinQueue` is now mapped from the client's own bytecode and bind table, and
**the experiment that settles FK-5 costs zero backend change** — the `bots` queue is already served,
is not a "special" (solo-mode) queue, and therefore routes FIND MATCH into the real matchmaking path
today. Separately, the `/core-game/regions` negative that FK-5 flagged as a spent lever is
**explained** — the payload never had a ping target to begin with, for two independently sufficient
reasons — which retracts it as evidence but does *not* put latency on the BATTLE path.

---

## 1. Verdict on FK-5

### 1.1 What the belief claimed

> `coverage-audit-s101.md:149` and `:572` — *"BATTLE/PRACTICE need an AccelByte QoS UDP ping
> responder"*, carried as **"the named upstream blocker."**

### 1.2 What its evidence actually supported

An inference from an absence: *"no `qos` key in ServiceHostnames; client fetches zero QoS
endpoints."* Its own source (`memory/supervive-tutorial-launch-status.md:65-68`) hedged
*"AccelByte QoS … **OR** the ICMP module"*; the audit dropped the OR and promoted the disjunction
to a named blocker.

That evidence supports exactly one proposition: **the client does not fetch AccelByte QoS
endpoints.** It supports nothing about what blocks BATTLE.

### 1.3 What is now established

| # | Statement | Tag |
|---|---|---|
| 1 | AccelByte QoS is **not on this path at all.** `QosManagerServerUrl=` is empty in all 12 environment sections of `tools/extractor/out/DefaultEngine.ini`; AccelByte `QosManager` has one call-site string against 77–117 latency strings. | `[M*]` |
| 2 | The populated machinery is Theorycraft's `ULatencyManager` / `ULatencyMeasurer`, calling into **UE's own ICMP module** with a host **and a port** — i.e. `FIcmp::UDPEcho`, not ICMP, not QoS. | `[M]` §2 |
| 3 | **No `ULatencyMeasurer` has ever been created**, in any session on disk. `Creating new latency measurer for %s %s` is `LatencyManager.cpp:315`, **verbosity `Display`** — it prints at default shipping verbosity — and it appears **0 times in all 14 Loki logs**. | `[M]` §2.6 |
| 4 | The UDP-echo implementation `0x1F8CFC0` is a **100 % zero page** in `dumps/merged.dump.exe`. The packer demand-decrypts `.text` per page on execution ⇒ that code has never run in any *dumped* state. | `[M]` §2.5 |
| 5 | `UPartyManager::TryJoinQueue`'s implementation page `0x5875000` is likewise **100 % zero**. The real matchmaking path has never executed in any *dumped* state. | `[M]` §3.5 |
| 6 | Therefore **no captured session ever got far enough for the client to want a QoS endpoint.** The belief was an inference from an absence, about a code path that has never run. | `[M]` |

**FK-5 is a false-known. Confidence: HIGH.** It is false in *attribution* (wrong vendor, wrong
subsystem) and false in *ordering* (it was never observed to be first, because nothing downstream of
the tile has ever been observed at all).

### 1.4 What I am explicitly NOT claiming

- **Not** that latency is irrelevant downstream. `TryJoinQueue`'s preconditions sit on a page that
  has never been decrypted. `[U]`
- **Not** that the `/core-game/regions` payload is "the real gate." It is a real, measured defect of
  the **latency-display** pipeline. Nothing measured places it on the BATTLE path. Substituting it
  would be FK-5's own error in mirror image.
- **Not** that a UDP echo responder will never be needed. The mechanism is measured; the *need* is
  conditional on a measurer existing, which has never happened.

### 1.5 One grain of truth, correctly scoped

`Could not ping target host: %s:%d. Result: %d` carries a **port**, and `FRegionRoute` carries both
`PingHost` and `PingPort` `[M]`. So *if* the pipeline is ever revived, the client will send UDP to a
host **we advertise**, and answering it is ~40 lines of Go — **not** an AccelByte QoS service. FK-5
was half right about a *mechanism* and wholly wrong about *whose* mechanism and *when* it matters.

---

## 2. The latency / region subsystem, hop by hop (MEASURED)

Every hop below is tagged. Where a hop is inferred, the measured parts and the inferred joint are
separated.

### 2.0 Type model — from the game's own shipped bind table, not the usmap

`tools/asdump/out/binds_members.csv`, parsed from the shipped `Loki/Script/Binds.Cache`. Verbatim
declarations `[M]`:

```
FRegionHostList  : TArray<FRegionHost> Regions ;  FString ETag
FRegionHost      : FString Name ; FString Addr ; int Port ; bool CanExclude ;
                   TMap<FString, FRegionRoute> Routes
FRegionRoute     : bool Enabled ; bool IsAccelerator ; FString Host ; int Port ;
                   FString PingHost ; int PingPort ; bool RequiresToken
FMemberServerLatency : FString Host ; FString Region ; FString Route ; float32 AvgLatency
FMemberLatencies     : TArray<FMemberServerLatency> Latencies
FPartyMember.Latencies (prop 16) : TArray<FMemberServerLatency>
FConnectionDetails   : … ; TMap<FString, FRegionRoute> Routes          ← also carries routes
UCoreGameManager::GetRegions() -> TArray<FRegionHost>
```

> **Methodological upgrade worth banking.** `binds_members.csv` (5,582 classes / 15,327 methods) is a
> *better type oracle than `mappings.usmap`* for anything script-exposed — it declares container
> element types explicitly, where the usmap has been wrong repeatedly (`QueueInfo.Queues`,
> `LatencyMeasurer.Latencies`, `AccelByteModelsQosRegionLatencies.Data`). It has been on disk since
> the asdump work. **Type any new endpoint from it first.** `[M]`

### 2.1 Supply — `GET /core-game/regions` → `UCoreGameManager.ValidRegions`

`fn 0x57B56B0` (2582 B, `.pdata` exact) is the only referencer of the route literal; it also touches
`Bearer `, `Authorization` and **`If-None-Match`**. `[M*]` `RegionHostList` carries an `ETag` we do
not serve. Note `If-None-Match` appears **0 times** in `docs/capture.log` `[M]`, so HTTP-level
caching is not currently a hazard; the *in-body* `ETag` mechanism is separate and unresolved. `[U]`

### 2.2 The measurer-creation loop — `fn 0x57DDCA0` (2410 B, `.pdata` exact)

Its only string is `&ULatencyManager::OnLatencyUpdated` `[M]` — it is inside `ULatencyManager` and
binds each new measurer's update delegate.

**I decoded the gate byte-for-byte from `dumps/merged.dump.exe` (file-offset == RVA):** `[M]`

```
0x57DE011  48 8b 5c 24 70        mov  rbx, [rsp+0x70]        ; region cursor
0x57DE016  80 7b dc 00           cmp  byte ptr [rbx-0x24], 0 ; = region+0x24 = CanExclude
0x57DE01A  0f 84 29 01 00 00     je   0x57DE149              ; SKIP — past the factory
0x57DE020  41 8b 45 40           mov  eax, [r13+0x40]        ; route+0x30 = PingPort
0x57DE024  4d 8d 4d 30           lea  r9,  [r13+0x30]        ; route+0x20 = PingHost
0x57DE028  4d 8b c5              mov  r8,  r13
0x57DE02B  89 44 24 20           mov  [rsp+0x20], eax
0x57DE035  e8 b6 0c fe ff        call 0x57BECF0              ; measurer factory  (verified target)
...
0x57DE190  48 83 c3 78           add  rbx, 0x78              ; region stride
0x57DE199  48 8d 43 b8           lea  rax, [rbx-0x48]        ; ⇒ rbx = region_base + 0x48
0x57DE19D  48 3b 45 10           cmp  rax, [rbp+0x10]
0x57DE1A1  0f 85 b9 fb ff ff     jne  <loop top>
```

**Triangulated three ways.** `lea rax,[rbx-0x48]` pins `rbx = region+0x48`, so `[rbx-0x24]` is
`region+0x24`. UE declaration-order packing of `FRegionHost` gives `Name@0x00 (0x10)`,
`Addr@0x10 (0x10)`, `Port@0x20 (4)`, **`CanExclude@0x24 (1)`**, pad, `Routes@0x28 (0x50 TMap)` ⇒
**size 0x78**, exactly the measured stride. The `r13` cursor is a TMap pair base
(`FString 0x10` + `FRegionRoute 0x38` + link `8` = `0x50`), so `r13+0x30`/`+0x40` are
`route+0x20 = PingHost` and `route+0x30 = PingPort`. `[M]`

> **⚠ `CanExclude: false` skips the region before the route loop body runs.** Two of the four sibling
> investigations proposed a corrected regions payload carrying `"CanExclude": false`. That payload
> would have produced **zero measurers and no parse error** — visually identical to today's failure,
> and an uninterpretable null. See §6.3.

### 2.3 Measurer construction — `fn 0x57BECF0` (862 B, `.pdata` exact)

Emits `Creating new latency measurer for %s %s` via `.rdata` slot `0x08B433F0` `[M]`. Field map,
from stores here and reads in the result callback, matched one-to-one against `schema.txt:21984`
property order `[M*]`:

| off | field | note |
|---|---|---|
| +0x40 | `Host`   | ← `FRegionRoute.PingHost` |
| +0x50 | `Region` | ← `FRegionHost.Name` |
| +0x60 | `Route`  | ← the `Routes` **map key** |
| +0x70 | `Port`   | ← `FRegionRoute.PingPort` |
| +0x74 | `bUpdatingLatency` | |
| +0x78 | `Latencies` | `TArray<float>` — **corrects the usmap**, which renders `TArray<FTimerHandle>` |
| +0x88 | `PingHostHandle` | |
| +0x90 | `Received` | |
| +0x94 | `PreviousLatency` | |
| +0x98 | `bHasReceivedPings` | |

Timer: `29.75f + (Rand()&0x7FFF) × 1/32768`, `bLooping = 1`. `[M*]`

### 2.4 The ping — `ULatencyMeasurer::PingHost`, `fn 0x57CB950`

Formats the target with the literal `{0}:{1}` from `Host` and `Port`, loads `xmm1 = 5.0` (timeout),
and calls `0x1F8CFC0` in UE's ICMP module. `[M*]` UE's own `FNetPing` text says
*"EPingType::ICMP should not specify a port number"* — the presence of a port is what identifies
this as `FIcmp::UDPEcho`. `[M*]` The result callback averages after 5 samples. `[M*]`

### 2.5 The ping implementation has never executed — page-level, not log-level

Page-zero census I ran myself over `dumps/merged.dump.exe` `[M]`:

| function | page | non-zero bytes | reading |
|---|---|---|---|
| **UDP echo impl `0x1F8CFC0`** | `0x01F8C000` | **0 / 4096** | never executed |
| **`TryJoinQueue` impl `0x5875E90`** | `0x05875000` | **0 / 4096** | never executed |
| measurer loop `0x57DDCA0` | `0x057DD000` | 3782 / 4096 | page ran |
| measurer factory `0x57BECF0` | `0x057BE000` | 3690 / 4096 | page ran |
| `PingHost 0x57CB950` | `0x057CB000` | 3803 / 4096 | page ran |
| `OnClientConfigUpdated 0x57DC9CD` | `0x057DC000` | 3898 / 4096 | page ran |
| regions fetch `0x57B56B0` | `0x057B5000` | 3926 / 4096 | page ran |
| `TryStartSoloMode 0x587A980` | `0x0587A000` | 3836 / 4096 | page ran |
| `joinQueue` req builder `0x584C520` | `0x0584C000` | 3979 / 4096 | page ran |
| `IsSpecialQueue 0x5854F5F` | `0x05854000` | 3830 / 4096 | page ran |
| latency success cb `0x585D1E0` | `0x0585D000` | 3791 / 4096 | page ran |

> **⚠ Two corrections to how this instrument was used by the sibling docs.**
> **(a) The inference is one-directional.** A zero page proves *never executed*. A decrypted page
> proves only that *something on that 4 KB page* ran — **not** that the named function ran. Sibling
> claims of the form "the ICMP module is proven initialised because its page is decrypted" are
> **over-claimed** and are not reproduced here.
> **(b) "Provably never executed" → "never executed in any DUMPED state."** All dump states are menu
> states. Nobody has clicked BATTLE while dumping. The measurement is real; the universal quantifier
> is not.

### 2.6 Log verbosities — decoded, with the decoder validated against ground truth

I decoded the `FStaticLogRecord` structs (`{const TCHAR* Format; const ANSICHAR* File; int32 Line;
ELogVerbosity Verbosity; void* Dynamic}`, `ImageBase 0x7FF6AF000000`) straight out of `.rdata` `[M]`:

| line | file:line | verbosity | prints by default? |
|---|---|---|---|
| `Creating new latency measurer for %s %s` | `LatencyManager.cpp:315` | **Display** | **yes** |
| `Could not ping target host: %s:%d. Result: %d` | `LatencyManager.cpp:346` | **Warning** | **yes** |
| `skipping set latencies, no valid party` | `PartyManager.cpp:294` | Verbose | no |
| `skipping set latencies, party state: %s` | `PartyManager.cpp:300` | Verbose | no |
| `skipping set latencies, player not in party` | `PartyManager.cpp:315` | **Warning** | **yes** |
| `skipping set latencies, no changes` | `PartyManager.cpp:322` | Verbose | no |
| `setting changed latency, Host/Region/Route/current/prior/chg` | `PartyManager.cpp:339` | **Log** | **yes** |
| `setting new latency, Host: %s, Region: %s, Route: %s, current: %f` | `PartyManager.cpp:347` | **Log** | **yes** |
| `skipping set latencies, no changes over set threshold` | `PartyManager.cpp:362` | Verbose | no |
| `Member latencies set` | `PartyManager.cpp:369` | **Log** | **yes** |
| `Failed to set latencies, status: %d, connected: %hhd, msg: %s - %s` | `PartyManager.cpp:376` | **Error** | **yes** |
| `Client version not valid, leaving matchmaking` | `PartyManager.cpp:387` | **Warning** | **yes** |
| `skipping set referral code, player not in party` *(null control)* | `PartyManager.cpp:453` | **Warning** | **yes** |

**Decoder validated end-to-end** `[M]`: the last row decodes to `PartyManager.cpp:453 Warning`, and
that line is observed verbatim in the live log as
`[2026.07.26-20.20.04:769][ 20]LogPartyManager: Warning: skipping set referral code, player not in party`
(`Loki.log:1718`). Category, file and verbosity all match. Every verbosity above is therefore a
measured fact from a *calibrated* instrument.

> **★ C6 — a correction every sibling probe design needs.** In UE, `FOutputDeviceHelper::FormatLogLine`
> omits the verbosity token when `Verbosity == ELogVerbosity::Log`. I confirmed this empirically:
> `AuthManager.cpp:1177` (`Attempting to login with Steam`) and `AuthManager.cpp:71`
> (`Authentication success`) both decode as **`Log`** and both appear in `Loki.log` as
> `LogLokiAuthManager: <text>` with **no token**. `[M]`
> ⇒ **`grep "LogPartyManager: Log:"` finds nothing even on complete success.** The correct pattern is
> `grep "LogPartyManager:"`. Two of the four sibling plans specify the broken pattern.

> **C7 — the Verbose bump is not guaranteed to work.** `Verbose:` lines *do* appear in this build
> (13, all `LogSentrySdk`) `[M]`, so Verbose is not compile-stripped globally. But
> `LogPartyManager`'s **compile-time** verbosity is unmeasured `[U]` — if it was declared below
> `Verbose`, `-LogCmds`/`[Core.Log]` cannot revive those four lines. **Any step that depends on the
> bump needs its own positive control** (see §7, Step 5).

### 2.7 The three untried levers named by FK-5 — adjudicated

| lever | verdict | evidence |
|---|---|---|
| `POST /latencies` | **Not a QoS responder.** It is a **party member-state write**, gated on party membership, party state and a change threshold. Element = `FMemberServerLatency{Host,Region,Route,AvgLatency}` — matching the `:339`/`:347` argument lists field-for-field. Zero hits is fully explained by "no measurers ⇒ no values ⇒ nothing to POST." | `[M]` §2.0 + §2.6 |
| `OnClientConfigUpdated` | **Falsified as a region-supply route.** `fn 0x57DC9CD` (1377 B, `.pdata` exact) touches exactly four literals in order: `coregamerouting`, `minLatencyDifference`, `minRouteLatencyDifference`, `Invalid minRouteLatencyDifference value: %s`. `FClientConfiguration` has 12 properties, none a region/host container. It carries **two float thresholds** — the hysteresis behind the `:362` guard — not hosts. | `[M*]` |
| `FNetPing` / `ServerSetPingAddress` | **Different subsystem, genuinely server-driven, and irrelevant here.** `fn 0x3F745E0` builds NetConnection URL options `ClientNetPingICMPAddress=%i=%s` / `ClientNetPingUDPAddress=%i=%s` — the server pushes ping addresses to the client **on join**, i.e. in-match. No decrypted path connects it to `ULatencyManager`. Bank it for the DS route. | `[M*]` MEASURED parts; `[SI]` the joint |

**⚠ Do not enable the `coregamerouting` toggle.** `fn 0x58B9D30` (3116 B) — the match-travel path —
resolves the connect address from the **route table** when the toggle is on, and can demand a routing
token (`routing token required but LokiSocketSubsystem not found`). `[M*]` Enabling it before
`/core-game/regions` carries a valid `Routes` map with `RequiresToken:false` risks **the one thing
that currently works**. All four sibling docs either proposed or flagged this; the flag wins.

### 2.8 Measurement cannot be bypassed by serving values

Every latency-consuming widget reads the **local** `ULatencyMeasurer`, not the party document:
`WBP_UI_RegionLatency.json` → `GetLatencyManager` → `GetLatencyMeasurer` → `GetLatency`;
`WBP_UI_RegionSelect_Entry.json` → `GetLatencyMeasurers` → `GetLatency`. A grep for
`MemberServerLatency|AvgLatency` across every extracted `catalog/wbp/*.json` returns **zero files**,
while `GetLatencyManager`/`GetLatencyMeasurer(s)`/`GetLatency` appear in **eight**. `[M*]`

`ULatencyManager` also exposes `AllMeasurersReported()` and `GetFastestRegionMeasurer()` — both
**local measurer state that no HTTP payload can set.** `[M]` (bind table, §2.0)

⇒ Serving `FPartyMember.Latencies` will **not** clear the `??? — ms` row and will **not** satisfy any
client-side "pings done" predicate. Its measured benefit is **zero**. See §6.5 for why it is cut.

### 2.9 No Angelscript involvement

Case-insensitive search for `latenc|region|ping|LatencyManager|LatencyMeasurer` across all 78
decompiled modules in `tools/asdump/out/modules/**` (110 classes, 1,463 functions) returns **no
matches**; the only hits anywhere under `tools/asdump/out/` are the `binds_*.csv` native bind
tables. `[M*]` The subsystem is entirely native C++ — no script hook to intercept, no script gate to
be the blocker.

---

## 3. What actually gates BATTLE and PRACTICE

### 3.1 The dispatch, from the client's own bytecode `[M]`

`Comp_MainMenu_QueueController` (`tools/extractor/out/bpdump_*`):

```
TILE VISIBILITY
  ExecuteUbergraph_WBP_UI_ActivityTile_Base:
      SetVisibility( SwitchValue( IsQueueAvailable(QueueID), <visible>, <Collapsed> ) )

IsQueueAvailable(ID):
  [2]  q1 = PartyModel.FindQueueByID(ID, bIsRanked = EX_False)   → IsValid ⇒ TRUE
  [9]  q2 = PartyModel.FindQueueByID(ID, bIsRanked = EX_True )   → IsValid ⇒ TRUE
  [13] IsSpecialQueueName_CustomGame(ID) ⇒ ClientConfig.GetNextOrCurrentTimespanForAction(...)
  [19] IsSpecialQueueName(ID)            ⇒ ClientConfig.GetNextOrCurrentTimespanForAction(...)
  else FALSE

FIND MATCH → ExecuteUbergraph_Comp_MainMenu_QueueController:
  HasSelectedSpecialQueue(out Mode):
      if PartyModel.GetPartyState() == 2 (CustomGame) → TRUE, Mode=""
      else for q in PartyModel.GetCurrentQueues(): if IsSpecialQueueName(q.ID) → TRUE, Mode=q.ID
      else FALSE
  TRUE  → [56] PartyManager.TryStartSoloMode(Mode, PrimaryAssetId{None,None}, TrainingStartPosition, cb)
  FALSE → [70] GetPartyManager → [71] IsValid → [72] PopExecutionFlowIfNot
          [74] BindDelegate "On Try Join Queue"
          [75] PartyManager.TryJoinQueue(cb)          ← ONE parameter: the delegate
          [76] PopExecutionFlowIfNot → [77] BeginAction
```

### 3.2 ★ C1 — the "most dangerous remaining assumption" is CLOSED

The evidence skeptic's top residual risk was that nobody knew what `FindQueueByID`'s second boolean
means — if it consulted a static preset list, the whole "the served queue list is the only input"
finding would collapse. **It is resolved.** `binds_members.csv:45939` declares it verbatim `[M]`:

```
UQueueModel FindQueueByID(const FString& QueueID, bool bIsRanked)
```

and `UQueueModel` carries `bIsRanked` as property 1 and `bIsSpecial` as property 23 `[M]`. The bool
is a **ranked-variant selector over the same model list**, not a different data source. **The served
`/party/matchmaking/info` queue list is the only input to `IsQueueAvailable` for a non-special
queue.** Risk retired.

### 3.3 ★ C2 — the decisive experiment costs ZERO backend change

Chain, every link measured `[M]`:

1. `queueIDs` (`interactive.go:868`) = `{"tutorialNew", "training", "practice", "bots"}` — **`bots`
   is served today.**
2. `DT_QueueDisplayDataTable.json` has a `bots` row; the ActivityPicker widget tree contains
   `ActivityTile_Bots`. So a bots tile exists as an asset.
3. `IsQueueAvailable("bots")` → `FindQueueByID("bots", false)` hits the served model ⇒ **TRUE** ⇒ the
   tile is not `Collapsed`.
4. Native `UPartyManager::IsSpecialQueue` (`fn 0x5854F5F`, 1903 B, `.pdata` exact) — I ran
   `strxref func` on it myself; its complete string set is:
   `queues`, `special`, then **`practice`, `customgame`, `dropin`, `tutorialNew`, `training`**
   (each twice). **`bots` is NOT special.**
5. `IsSpecialQueueName(ID)` is a one-line BP wrapper that calls exactly that native `[M]`.
6. ⇒ `HasSelectedSpecialQueue` returns FALSE for `bots` ⇒ **FIND MATCH takes the
   `TryJoinQueue` branch.**
7. Restrictions: `Comp_MainMenu_QueueController` CDO `QueueToGameFeature` has **exactly three rows** —
   `deathmatch`, `customgame`, `custom` `[M]`. `bots` is unrestricted, and we serve no
   `queue.restrictions.bots` feature toggle.

> **Three of the four queues we advertise are solo-mode queues. The fourth, `bots`, is the real
> matchmaking path — and it has been sitting there, clickable, for ~45 sessions.** Every sibling
> plan proposed restoring the queue list *first*; none noticed the experiment was already available.

**Honest caveat.** I cannot prove from disk that the BOTS tile is *currently drawn on screen* `[U]` —
no screenshot exists and `coverage-audit-s101.md:572` lists "PLAY tiles" as PARTIAL/DEFECTIVE. There
is also an `ActivityTile_Tutorial_BotGame` in the same tree, so the tile carrying queue id `bots`
must be identified visually. That is a 10-second read at the top of the probe, not a research task.

### 3.4 ★ C3 — there is no Blueprint-level gate between FIND MATCH and native `TryJoinQueue`

Read directly from the ubergraph (§3.1): between the branch and the native call there is
`GetPartyManager` → `IsValid` → `PopExecutionFlowIfNot` → `BindDelegate` → **call**. `[M]`

**No latency check. No region check. No readiness predicate.** Whatever preconditions exist are
*inside* `UPartyManager::TryJoinQueue`, on a page that has never been decrypted. This is the single
cleanest structural argument that latency is not a *client-side* gate on joining a queue — and it is
also exactly why the *native* gate list is unknown.

### 3.5 ★ C5 — `TryJoinQueue` takes only a delegate

`TryJoinQueue(cb)` receives **one parameter** `[M]`. It carries no queue id, so the queue must already
be the party's *current* queue — set through `POST .../setTargetQueues`, a route we have never served
and which has **0 hits** in `docs/capture.log` `[M]`. Selection and join are two separate writes, and
neither has ever fired.

### 3.6 Ranked candidates for the BATTLE/PRACTICE gate

Ordered by evidence strength. **QoS is at the bottom, marked "not a gate" — not "disproven."**

| # | Candidate | Applies to | Evidence | Tag |
|---|---|---|---|---|
| **1** | **`default` is absent from the served queue list**, so `IsQueueAvailable("default")` is FALSE and the Breach tile is `SetVisibility(Collapsed)` — not drawn, let alone blocked. | BATTLE only | §3.1 bytecode + `interactive.go:868` | `[M]` |
| **2** | **`Party.State` is never served.** `UPartyManager::TryStartSoloMode` GATE-2 requires `"default"`/`"Matchmaking"` at `PartyModel+0x558+0x18`; S61 satisfied it with a live memory poke. `FParty` property 2 is `FString State` ⇒ offset `0x10(ID) + 0x08(Version) = 0x18`. **Name and offset now agree independently.** Also participates in the FIND MATCH dispatch (§3.1). | PRACTICE + all solo modes | `binds_members.csv:18400` + S61 disasm | `[M]` — upgraded from `[SI]` |
| **3** | **`POST .../setTargetQueues` is unserved** and has never fired; `TryJoinQueue` carries no queue id, so selection must land server-side first. | BATTLE | §3.5 + `capture.log` 0 hits | `[M]` mechanism, `[SI]` that it blocks |
| **4** | **`TryJoinQueue`'s own native preconditions.** Page `0x5875000` is 100 % zero. | BATTLE | §2.5 | **`[U]` — the largest residual** |
| **5** | **`ActionInProgress` latch.** `CanSwitchQueue = !ActionInProgress && IsPartyOwner()`; `EndAction` is only reached from the four completion callbacks. `/setTargetQueues`, `/joinQueue`, `/leaveQueue` all fall to the `{}` catch-all. If a `{}` body fails to complete a callback, the latch wedges every later click. | both | mechanism `[M*]`; that `{}` wedges it `[SI]` | `[SI]` |
| **6** | The 15 s excluded-regions PLAY-button delay. **Self-clearing, not a wall** — `OnMaxTimeForExcludedRegions` calls `SetIsEnabled(TRUE)` unconditionally after 15.0 s. Any past "the button is greyed out" taken in the first 15 s is not evidence. | both | `bpdump_ExecuteUbergraph_WBP_UI_PartyJoinLeaveQueue_CTA_V3` (`Button_FindMatch`, `Value: 15`) | `[M]` |
| — | **Account level.** **Not a gate.** `CanControlQueue` loops `GetCurrentQueues` — I counted: **25 occurrences of `GetCurrentQueues`, 0 of `GetQueues`** — so advertising ids cannot enter the loop; and its `GetLevelGameFeatureUnlocked` call takes a **hardcoded** `PrimaryAssetId{GameFeature, Ranked}` whose result feeds a `level` **format argument for an error string**. | — | `bpdump_CanControlQueue.txt` | `[M]` |
| — | **AccelByte QoS UDP ping responder.** **Not a gate.** Not on the path; §1.3. | — | §1.3 | `[M]` |

### 3.7 C10 — a correction two sibling docs need

`CanControlQueue`'s gate #2 is `UClientConfigManager::IsClientVersionValid()` `[M]` — a check of the
**client build** against `ClientConfiguration.ClientVersions`. It is **not** `FParty.ClientVersion`.
Two sibling plans proposed serving `Party.ClientVersion` partly on that basis. Different object,
different field. (`FParty.ClientVersion` does pair with `PartyManager.cpp:387`
*"Client version not valid, leaving matchmaking"*, Warning — but that fires inside matchmaking, not
at `CanControlQueue`.)

---

## 4. The `/core-game/regions` negative — EXPLAINED (this was the crux)

FK-5 flagged this as a spent lever:

> **⚠ Trap** — the obvious remedy is already spent: `/core-game/regions` **was** served with
> `PingHost: 127.0.0.1` and the client never pinged.

**That trap note must be RETRACTED. The experiment was malformed, so its negative result carries no
information.** Three independently sufficient defects, all in our own payload:

Current handler, `server/internal/interactive/interactive.go:718-732` `[M]`:

```go
region := map[string]any{
    "RegionName": "na", "RouteName": "na", "DisplayName": "Local",
    "Host": "127.0.0.1", "PingHost": "127.0.0.1", "Address": "127.0.0.1",
    "Port": 443, "Enabled": true,
}
writeJSON(w, map[string]any{"Regions": []any{region}})
```

Target struct is `FRegionHost{Name, Addr, Port, CanExclude, Routes}` (§2.0).

| # | Defect | Consequence | Tag |
|---|---|---|---|
| **A** | **`PingHost`/`PingPort` are `FRegionRoute` fields *inside* `FRegionHost.Routes` — a `TMap` we have never sent.** Of our eight keys, exactly **one** (`Port`) matches a real `FRegionHost` property. | The route loop body never runs. No ping target exists. | `[M]` |
| **B** | **`CanExclude` is omitted ⇒ defaults `false` ⇒ `0x57DE016` skips the region *before* the route loop.** | Even a correct `Routes` map would be skipped. | `[M]` §2.2 |
| **C** | **`Name` is omitted ⇒ empty region name.** | `measurer.Region` would be `""`; the latency widget's `ST_ServerLocations` lookup gets an empty key. | `[M]` |

Per the project's own validity model (unmatched keys are silently ignored), the client parsed our
body **cleanly** into one `FRegionHost{Name:"", Addr:"", Port:443, Routes:{}}` — and there is
positive evidence it parsed rather than failed: `docs/capture.log` shows **7 × `GET
/core-game/regions → 200`** in the 2026-07-26 session, with **zero** `LogLokiPlatformQuery` and
**zero** `LogJson` lines in the matching `Loki.log` `[M]`.

⇒ Zero routes ⇒ zero `ULatencyMeasurer`s ⇒ **the ping code was never reached**, which is exactly
what §2.5's all-zero page at `0x1F8CFC0` shows at instruction level. The chain closes.

> **Downgrade (evidence skeptic wins).** One sibling doc called
> `LogStringTable: Warning: Failed to find string table entry for '…ST_ServerLocations…' ''`
> (`Loki.log:2151`) *"the single best positive measurement."* It is not. It fires **once**, and its
> immediate neighbour (`:2152`) is `ST_Cosmetics_Categories 'none'` — an unambiguous construct-time
> default. It cannot distinguish *"our payload parsed into a Name-less region"* from *"zero regions
> exist."* **Demoted to weak corroboration.** `[M]`

### 4.1 What "explained" does and does not mean

**Does mean:** the observation *"we served `PingHost` and the client never pinged"* is fully accounted
for by our own payload shape, and is therefore **retracted as evidence for anything about QoS,
loopback, or the client's willingness to ping.**

**Does not mean:** that fixing the payload will produce a ping. Defects A, B and C are each
*necessary* to fix; **sufficiency is unmeasured** `[U]`. `FRegionRoute.Enabled`, the `Routes` map key,
and the field-name casing are all unverified against a live parse. The one-bit test is §7 Step 6.

**Also does not mean:** that this is on the BATTLE path. It is not. It is the `??? — ms` latency
readout. Fixing it is worth doing; **doing it first would be scope drift** — which is precisely how
FK-5 was written.

---

## 5. The tutorial-queue diff — the one working example

`tutorialNew` is the only queue in the project's history that has gone tile → latch →
`POST /startSoloMode` → travel to `LVL_Tutorial`. The diff against BATTLE is the cheapest available
argument, and it is decisive on the QoS question:

| property | `tutorialNew` (works) | `bots` (untested, servable today) | `default` (not served) |
|---|---|---|---|
| in served `queueIDs` | **yes** | **yes** | **no** |
| `IsQueueAvailable` | TRUE | TRUE | **FALSE ⇒ tile Collapsed** |
| native `IsSpecialQueue` | **yes** | **no** | **no** |
| FIND MATCH branch | `TryStartSoloMode` | **`TryJoinQueue`** | n/a — not drawn |
| `Party.State` gate | required; **satisfied by a live memory poke** | not on this path | not on this path |
| `LogLatencyManager` lines emitted | **0** | ? | ? |
| any QoS/latency HTTP call | **none** | ? | ? |

**What it implies** `[M]`:

1. **The tile → latch → solo-start → travel chain runs with zero latency machinery.** Not "latency
   was fast enough" — *no measurer has ever existed*. Latency is provably not required for that
   chain.
2. It is **silent about matchmaking**, because `tutorialNew` is special and never touches
   `TryJoinQueue`. The two buttons take **different code paths**, which is why
   `coverage-audit-s101.md:572`'s *"BATTLE **and PRACTICE** tiles are degraded [by the trim]"* is
   half wrong: `practice` **is** in the served list. PRACTICE is not queue-list-blocked; PRACTICE is
   blocked at the same `TryStartSoloMode` gate the tutorial is (candidate #2), and the tutorial only
   clears it via a memory poke.
3. `bots` sits in exactly the gap: **served like the tutorial, dispatched like BATTLE.** It is the
   only queue that isolates the matchmaking path with no backend change.

---

## 6. Proposed backend changes — ranked, with regression risk

**None of these are required to answer FK-5.** §7 Steps 0–2 settle it with zero code. These are the
follow-ons, ranked by (evidence strength × payoff ÷ risk). **`server/` was not modified by this
session.** Diffs are drafts for review.

### 6.1 — `queueIDs`: restore the 10 PresetQueues ids · **risk LOW** · rank 1

`server/internal/interactive/interactive.go:855-869`

```diff
-// DIAGNOSTIC TRIM (S60): Comp_MainMenu_QueueController.CanControlQueue loops over the current
-// queues calling GetLevelGameFeatureUnlocked; with the served account level = 0, any level-gated
-// queue (tournament/deathmatch/ranked) fails that loop -> CanControlQueue false -> every activity
-// click errors "Unable to modify activity". Trim to the new-player / level-0 set (tutorials +
-// practice + co-op) to test whether removing gated queues clears the modify block. If it does,
-// the real fix is serving a high account level (unlocks all features) so the full set can return.
-var queueIDs = []string{
-	"tutorialNew", "training", "practice", "bots",
-}
+// 2026-07-27 (S105, FK-5): the S60 DIAGNOSTIC TRIM above is FALSIFIED from the client's own
+// Blueprint bytecode. It is preserved here only so the reasoning is not re-derived:
+//
+//   (1) CanControlQueue loops PartyModel.GetCurrentQueues() -- the party's SELECTED queues --
+//       not GetQueues(). Counted in bpdump_CanControlQueue.txt: GetCurrentQueues x25,
+//       GetQueues x0. Advertising an id cannot put it in that loop.
+//   (2) Its GetLevelGameFeatureUnlocked call sits behind EX_PopExecutionFlowIfNot(q.bIsRanked)
+//       and ...(!bIsRankedEligible); we serve IsRanked:false on every queue, so the arm is dead.
+//       Its argument is a HARDCODED EX_StructConst PrimaryAssetId{GameFeature, "Ranked"} whose
+//       result feeds a "level" FORMAT ARGUMENT for an error string -- it never gated a queue.
+//   (3) Real per-queue restrictions live in IsQueueIDPremadeOrOverQueueLevel, driven by the
+//       Comp_MainMenu_QueueController CDO map QueueToGameFeature, which has exactly THREE rows:
+//       deathmatch, customgame, custom. Neither "default" nor "bots" is restricted.
+//
+// => NO ACCOUNT LEVEL IS REQUIRED. `default` missing is why the BATTLE (Breach) tile is not drawn
+// at all: IsQueueAvailable("default") is false and WBP_UI_ActivityTile_Base SetVisibility()s
+// itself Collapsed. FindQueueByID(ID, bIsRanked) -- Binds.Cache: "UQueueModel FindQueueByID(
+// const FString& QueueID, bool bIsRanked)" -- is a ranked-VARIANT selector over the same served
+// list, so the list is that predicate's only input.
+//
+// DELIBERATELY EXCLUDES domination/prismabank: they have DT rows and tiles but are NOT in
+// WBP_ActivityPickerScreen.InitializeQueues' PresetQueues set, so they would also draw a
+// DUPLICATE generic tile. Keep the game's own misspelling "armorydeathmath" verbatim.
+var queueIDs = []string{
+	"default", "deathmatch", "practice", "dropin", "customgame",
+	"bots", "tutorialNew", "training", "armorydeathmath", "tournament",
+}
```

Pair with a bump of `matchmakingETag` (`:876`) to `"revival-queues-v2"` — **not a second variable**,
an anti-ambiguity control (see §7 note on ETags).

**Risk LOW.** Worst case a `QueueDetails` deserialization failure empties `GetQueues()` and *all*
tiles collapse, including the tutorial — the only working match-setup path. Visible immediately as
`ImportText (Queues)` / `Deserialization failure` in `Loki.log`. One-line revert; the client re-polls
`/party/matchmaking/info` in ~30 s.

### 6.2 — `buildSoloParty`: serve `Party.State` · **risk LOW** · rank 2

`server/internal/interactive/interactive.go:1208-1209`

```diff
 		"isOpen":          false,
 		"fillTeam":        false,
+		// 2026-07-27 (S105): FParty.State. Binds.Cache declares it verbatim as property 2 --
+		// `FString State` -- so with ID(FString,0x10) + Version(int64,0x08) it lands at +0x18,
+		// which is EXACTLY the address S61 disassembled as TryStartSoloMode GATE 2
+		// (PartyModel+0x558+0x18, case-insensitive "default"/"Matchmaking"; live-poked to prove
+		// it). Name and offset now agree independently. Values are EPartyState names
+		// {Default, Matchmaking, CustomGame, Unknown}. This closes handleStartSoloMode's own
+		// open note ("the durable fix is populating that party JSON field (key not yet mapped)").
+		// It is also (a) the guard PartyManager.cpp:300 prints as "skipping set latencies,
+		// party state: %s" and (b) read FIRST by the FIND MATCH dispatch
+		// (HasSelectedSpecialQueue: `if GetPartyState()==2 /*CustomGame*/ -> solo`).
+		// WARNING: never serve "Matchmaking" at idle -- IsInQueue() reads GetPartyState() and
+		// the PLAY button flips to CANCEL.
+		"state": "default",
```

**Risk LOW.** A *matched* key of the *correct* type (Str), so it cannot trip the "Deserialization
failure" class. The hazard is semantic, not structural: a wrong **value** moves a state machine.
Canary: the party panel must still show hero preview + avatar.

### 6.3 — `handleCoreGameRegions`: the real `FRegionHostList` · **risk MEDIUM** · rank 3

`server/internal/interactive/interactive.go:718-732`. **Keep the existing 2026-06-29 comment block**;
append the new provenance.

```diff
 func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
-	region := map[string]any{
-		"RegionName":  "na",
-		"RouteName":   "na",
-		"DisplayName": "Local",
-		"Host":        "127.0.0.1",
-		"PingHost":    "127.0.0.1",
-		"Address":     "127.0.0.1",
-		"Port":        443,
-		"Enabled":     true,
-	}
-	writeJSON(w, map[string]any{
-		"Regions": []any{region},
-	})
+	// 2026-07-27 (S105, FK-5) -- the body above matched the target struct in exactly ONE field.
+	// Ground truth from the shipped Loki/Script/Binds.Cache (tools/asdump/out/binds_members.csv),
+	// which is a better type oracle than mappings.usmap for script-exposed containers:
+	//   FRegionHostList { TArray<FRegionHost> Regions ; FString ETag }
+	//   FRegionHost     { FString Name ; FString Addr ; int Port ; bool CanExclude ;
+	//                     TMap<FString, FRegionRoute> Routes }
+	//   FRegionRoute    { bool Enabled ; bool IsAccelerator ; FString Host ; int Port ;
+	//                     FString PingHost ; int PingPort ; bool RequiresToken }
+	// PingHost/PingPort live on the ROUTE, inside Routes -- a TMap we never sent. Of the 8 old
+	// keys only `Port` matched anything, so the client parsed a clean but empty region
+	// {Name:"", Routes:{}} and had nothing to ping. That is why "we served PingHost and the
+	// client never pinged" is NOT evidence about QoS or loopback.
+	//
+	// *** CanExclude MUST be true. *** The measurer loop fn 0x57DDCA0 gates on it BEFORE the
+	// route loop -- verified byte-for-byte in dumps/merged.dump.exe:
+	//     0x57DE016  80 7b dc 00        cmp byte ptr [rbx-0x24], 0    ; region+0x24 = CanExclude
+	//     0x57DE01A  0f 84 29 01 00 00  je  0x57DE149                 ; skips the factory
+	//     0x57DE035  e8 b6 0c fe ff     call 0x57BECF0                ; measurer factory
+	// (rbx = region_base+0x48 per `lea rax,[rbx-0x48]` at 0x57DE199; stride 0x78 == sizeof
+	// FRegionHost.) With CanExclude:false this handler produces ZERO measurers and NO parse
+	// error -- indistinguishable from the old failure.
+	//
+	// Name feeds measurer.Region and the ST_ServerLocations key (live log looked it up as '').
+	// The Routes map KEY becomes measurer.Route. PingPort 7778 is deliberately disjoint from
+	// the DS stub's UDP 7777.
+	writeJSON(w, map[string]any{
+		"Regions": []any{map[string]any{
+			"Name":       "na",
+			"Addr":       "127.0.0.1",
+			"Port":       7777,
+			"CanExclude": true,
+			"Routes": map[string]any{
+				"default": map[string]any{
+					"Enabled":       true,
+					"IsAccelerator": false,
+					"Host":          "127.0.0.1",
+					"Port":          7777,
+					"PingHost":      "127.0.0.1",
+					"PingPort":      7778,
+					"RequiresToken": false,
+				},
+			},
+		}},
+		"ETag": "revival-regions-v1",
+	})
 }
```

**Risk MEDIUM, contained.** `Routes` is a `MapProperty` of a struct — the shape most likely to be
wrong. A mismatch trips `Deserialization failure` on this route only; nothing but
`CoreGameManager.ValidRegions` consumes it. **Watch the request rate in `capture.log`** — a parse
failure once produced a ~100 req/s retry storm (the `progressiontracks` incident). Run **alone**,
never bundled.

### 6.4 — DO LATER, GATED: UDP echo responder · **risk LOW** · rank 4

New `server/internal/udpping/udpping.go`, flag-gated, default **off**. Bind
`127.0.0.1:<PingPort>/udp`; on each datagram log length + source + a **hexdump**, then write the
bytes back **verbatim**.

**Rationale.** `0x1F8CFC0` is an all-zero page, so **the packet format is unreadable offline** `[M]`.
A verbatim echo is format-agnostic *and* the hexdump recovers the format on the first datagram. Note
`'LokiPing'` — 8 ANSI bytes, NUL-terminated, at `0x079C6E80` `[M*]` — sits inside Epic's own ICMP
translation unit between UE's wide `UDPPing` thread name and `IcmpWindows.cpp`'s log record. Every
neighbour there is Epic's; that one is not, and ANSI in a UE string block is the tell. `[SI]` **Do not
assume the stock UE packet format.**

**Do not build first.** With no measurer there is nothing to answer, and with a measurer but no
responder the expected `Could not ping target host: 127.0.0.1:7778. Result: N` (Warning, prints free)
is itself a **positive** result proving the measurer exists.

### 6.5 — NOT PROPOSED (recorded so it is not silently re-added)

| item | why not |
|---|---|
| **`FPartyMember.Latencies` on the party document** | **Cut.** *Skeptics win on the disagreement:* probe 1 rated it LOW risk (type is exact), probe 3 rated it HIGH (party doc is load-bearing). Both are half right — but **measured benefit is zero** (§2.8: 8 widget JSONs read the local measurer, 0 read `AvgLatency`; `AllMeasurersReported()` is local state). Non-zero risk to the project's largest asset for a measured-zero payoff. |
| **Any account-level change** | Provably unnecessary (§3.6) and it would make the probe ambiguous. |
| **`coregamerouting` feature toggle** | Can break the one travel path that works (§2.7). |
| **Registering `POST .../latencies` before it fires** | **Actively harmful.** Unmatched routes fall to `capture.StubHandler` → `200 {}` (`capture.go:175`), while `Logger.Middleware` writes the full request body (up to 1 MB) for **every** request, matched or not (`capture.go:92-123`) `[M]`. The first call therefore hands us the ground-truth request shape and the true route (`.../{partyId}/latencies` vs `.../players/{id}/latencies`) **for free**. Registering early destroys that. |
| **`Party.ClientVersion`** | Not what `CanControlQueue` checks (§3.7). Separate variable, only matters inside matchmaking. |
| **`ClientConfiguration` as a region source** | Falsified (§2.7). Remove from the roadmap. |

### 6.6 ⚠ A calibration caveat on the validity model itself

`buildSoloParty` serves `"fillTeam": false` — a JSON **bool** — against `FParty.FillTeam`, which
`Binds.Cache` types as the **enum `EPartyFillPreference`** `[M]`. That is a *wrong-typed matched key*
on the load-bearing party document, and **the party document demonstrably works today** (avatar,
hero preview, `Version` gating all function — S85).

The mechanism is not established `[U]` — UE may coerce bool→number→enum, or the key may not match at
all. But the observation stands: **the project's stated rule ("a wrong-typed matched field rejects the
whole doc") has a live counter-example inside our own party payload.** Every "risk: low/high" call in
the four sibling documents is calibrated against a rule with at least one exception. Treat risk
ratings here as ordinal, not absolute. *(Credit: the evidence skeptic flagged this; I verified it.)*

---

## 7. The live probe

**Design principles.** One variable per step. Every step has an **interpretable negative**. A **null
control** runs first so a flat log is distinguishable from a broken harness. A **stop rule** fires the
moment FK-5 is answered, so the session cannot drift into chasing a subsystem — the exact failure that
produced FK-5.

### 7.0 Configuration (all steps)

- **Elevated PowerShell.** **Steam running first** (else `Auth Failure 14005`).
- `.\configs\launch-redirect.ps1` — **the default shim set, NOT `-NoHook`.**
  *Skeptics disagreed; the plan skeptic wins.* `-NoHook` drops `catalog_store_fix`, so the roster does
  not render and the hero-pick → party-member path is non-representative. Every prior menu observation
  (including S60's `Unable to modify activity`) was made **with** shims; results must be comparable.
  No shim touches `PartyModel` queues or `CoreGameManager` regions. A long menu session also discharges
  the pending triple-PI-hooker validation for free.
- **No force-open. No memory poke.** A poke would mask Step 4. (There is no poke script in
  `tools/re/` — only `poke_scale.py` / `poke_toggles.py` — so the baseline is genuinely poke-free.)
- Second terminal: `.\configs\shim-status.ps1 -Watch`.
- **Before each step, record the last `#NNNN` request id in `docs/capture.log`**, or the diff is
  unreadable. None of the four sibling plans specified this.

**Mid-session backend swap — no relaunch, no cert work.** `tlscert.EnsureCert`
(`server/internal/tlscert/tlscert.go:41-46`) returns early when `root.crt`/`server.crt`/`server.key`
all exist and load; `configs/launch-redirect.ps1:185` is the **only** cert wipe `[M*]`. A manual
restart against the same `-certs` dir keeps an identical chain and `cacert.pem` stays valid.

```powershell
# rotate the capture, rebuild, restart -- ~2-3 min per variable
Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags
# ... restart ags with the SAME -certs dir and -admin as the launcher used ...
```

**Anti-ambiguity rule: bump the in-body `ETag` on every mid-session content change.**
`matchmakingETag` (`:876`) is a constant. `If-None-Match` appears 0× in `capture.log` `[M]`, so
HTTP caching is not the hazard — but whether the client short-circuits re-ingest on an unchanged
*in-payload* `ETag` is unresolved `[U]`. Bumping costs nothing and removes a whole ambiguity class.

**Grep patterns (corrected — see §2.6/C6):**

```powershell
$L = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
Select-String -Path $L -Pattern 'LogLatencyManager|latency measurer|Could not ping target host'
Select-String -Path $L -Pattern 'LogPartyManager:'      # NOT 'LogPartyManager: Log:' -- Log has no token
Select-String -Path $L -Pattern 'ImportText|Deserialization failure|LogJson'
Select-String -Path 'G:\git\Supervive Revival Project\docs\capture.log' `
  -Pattern 'joinQueue|setTargetQueues|latencies|startSoloMode|leaveQueue|setExcludedRegions'
```

---

### STEP 0 — Null control. **Zero change.**

Log in; sit at the main menu ~30 s.

**One bit:** does `LogPartyManager: Warning: skipping set referral code, player not in party` appear
in the live `Loki.log`?

- **No** → the harness is broken (wrong log file, login failed, shims mis-injected). **STOP and fix.**
  Every later negative would be uninterpretable.
- **Yes** → proceed. `[M]` This line is `PartyManager.cpp:453 Warning` — the *sibling guard* of the
  five `skipping set latencies` strings: same translation unit, same category, and it appears in
  **1 of 1** in all 14 archived Loki logs `[M]`. Its presence proves the category prints.

---

### STEP 1 — Tile inventory. **Still zero change.**

Open PLAY. Photograph / list every activity tile drawn. Identify which tile carries queue id `bots`
(there is both an `ActivityTile_Bots` and an `ActivityTile_Tutorial_BotGame`).

**One bit A:** is a BATTLE / Breach tile drawn?
- **Absent** (predicted) → the tile-visibility model holds.
- **Present** → §3.1's model is wrong. **STOP and re-derive** before changing anything.

**One bit B:** is a BOTS tile drawn?
- **Present** (predicted) → **Step 2 is available at zero cost.**
- **Absent** → skip to Step 3 (restore the queue list), then return.

---

### STEP 2 — ★ THE FK-5 ANSWER. **Still zero backend change.**

Select **BOTS**. Confirm the selection latches (pink border, the way BASIC TRAINING does). Then click
**FIND MATCH**. Wait 60 s. Read `docs/capture.log` **in request order** from the boundary you recorded.

`bots` is served, is **not** special (§3.3), and is unrestricted — so FIND MATCH dispatches to
`UPartyManager::TryJoinQueue`, the real matchmaking path, which has **never executed in any dumped
state**.

**One bit: what is the FIRST unserved route the client asks for?**

| observation | reading |
|---|---|
| `POST .../setTargetQueues` or `.../joinQueue`, **no latency call** | **FK-5 is FALSE.** Answer obtained. → **STOP RULE** |
| `POST .../latencies` or `.../setExcludedRegions` **first** | **FK-5 is mis-scoped, not right** — latency is on the critical path. Record it that way. §6.3 reopens. |
| tile latches, FIND MATCH does nothing, **no HTTP** | Read the PLAY-button tooltip — `CanControlQueue`'s distinct `ReasonText` names the gate. This is the interpretable negative. |
| selection itself refuses (`Unable to modify activity`) | That string is `Queue.AddError` in `catalog/st/ST_ErrorMessages.json` — **on-screen only, never a log line** `[M*]`. Suspect the `ActionInProgress` latch (§3.6 #5): if the *first* click works and every later one fails, reopening the modal will not clear it — restart the flow. |

> ### ⛔ STOP RULE
> **The moment Step 2 yields a first-unserved-route, FK-5 is answered and the assignment is complete.**
> Write the result into this document **before touching anything else.** Steps 3-6 are opportunistic
> work on an already-open game — not part of the verdict. This is exactly the point at which FK-5's
> original error was made: a subsystem got chased instead of a question answered.

---

### STEP 3 — Restore the queue list. **One variable** (§6.1 + ETag bump).

Rebuild, restart, wait one `/party/matchmaking/info` poll (~30 s), re-open PLAY.

**One bit:** is the Breach (BATTLE) tile now **drawn**?
- **Yes** → candidate #1 confirmed; the level-gate hypothesis is dead.
- **No, and `ImportText (Queues)` / `Deserialization failure` in `Loki.log`** → a `QueueDetails`
  element is malformed — a *different* bug, and the client just named it.
- **All tiles vanish** → regression. **REVERT `:868`, rebuild, restart. Do not proceed until the menu
  is back.**

Then click BATTLE → FIND MATCH and repeat Step 2's one-bit read. (If Step 2 already fired the stop
rule, this is confirmation, not discovery.)

---

### STEP 4 — Close S61: `Party.State`. **One variable** (§6.2).

Rebuild, restart, wait one poll. **Canary first: does the party panel still show hero preview +
avatar?** If blank → the document was rejected; **revert immediately.**

Click **PRACTICE** → PLAY.

**One bit:** does `POST /party/parties/party-<id>/startSoloMode` appear in `capture.log` **with no
memory poke**?
- **Yes** → S61's explicitly-open durable fix is closed; the poke is retired.
- **No** → read which guard printed. Next candidates `partyState` / `matchmakingState`; a live RPM
  read of `PartyModel+0x558+0x18` right after a `/party` poll settles it in seconds.

---

### STEP 5 — Verbosity bump. **Only if a latency guard is suspected. Needs its own control.**

Add to `configs/launch-redirect.ps1`'s existing `-ini:` block (lines ~299-310):

```
"-ini:Engine:[Core.Log]:LogPartyManager=Verbose",
"-ini:Engine:[Core.Log]:LogLatencyManager=Verbose",
```

**Positive control (mandatory).** Four of five `SetLatencies` skip reasons are Verbose, so *absence*
of Verbose lines is ambiguous by construction. `LogPartyManager`'s **compile-time** verbosity is
unmeasured `[U]` — if declared below `Verbose`, the bump is inert. **Pair it with a category you know
emits Verbose in this build: `LogSentrySdk` (13 lines observed)** `[M]`. If `LogSentrySdk: Verbose:`
still appears and `LogPartyManager: Verbose:` never does under a state that should hit a guard, the
bump did not take — do not read that as "guard not hit."

**Do not run this for the positive signals** — `Creating new latency measurer` (Display),
`Could not ping target host` (Warning), `setting new latency` / `Member latencies set` (Log, **no
token**) and `Failed to set latencies` (Error) all print for free.

---

### STEP 6 — Regions shape. **One variable, with the CORRECTED body** (§6.3).

**`CanExclude: true` is load-bearing.** With `false` this step produces an uninterpretable null.

Rebuild, restart, wait 60 s or leave/re-enter PLAY to force `RefreshRegionsHandle`. **Watch the
`/core-game/regions` request rate in `capture.log`** — a spike means a parse-failure retry storm;
revert on sight.

**One bit:** does `LogLatencyManager: Display: Creating new latency measurer for na default` appear —
a string absent from **all 14** archived logs?
- **Yes** → the regions negative is fully closed. `ST_ServerLocations`'s key should also flip from
  `''` to `na`.
- **`ImportText (Regions)` / `Deserialization failure`** → the element type or a field name is wrong
  and the client just named it. One variable settled; revert.
- **Silence, no parse error, `ST_ServerLocations` still `''`** → `Name` did not bind. Check field
  casing, then the `Routes` key, then `FRegionRoute.Enabled`.

**Follow-on (same step, free):** `Could not ping target host: 127.0.0.1:7778. Result: N` is Warning
and prints without any logging change — that warning is itself the positive result proving the
measurer is alive, and `Result: N` names the UE failure enum. Expect the **first** ping ~30 s after
the payload lands (timer = `29.75 + Rand()/32768`, looping) and a completed average after **5**
samples — so a 20-second look proves nothing.

---

### DEFERRED — explicitly not this sitting

- **UDP echo responder** (§6.4) — gated on Step 6 producing a measurer.
- **`dumpimage` + `mergedumps` after a BATTLE/BOTS FIND MATCH click.** This commits page
  `0x5875000` and makes `TryJoinQueue` disassemblable — **the single highest-value capture available**,
  because it is the only way to read the one thing this pass could not.
  ```powershell
  .\tools\usmapdump\usmapdump.exe dumpimage SUPERVIVE-Win64-Shipping.exe dumps\battleclick\
  .\tools\usmapdump\usmapdump.exe mergedumps dumps\merged.dump.exe dumps
  # then: python tools\strxref\strxref.py func 0x5875E90
  ```
  ⚠ **RETRACTED 2026-08-14 (FK-19):** `mergedumps` no longer requires a matching module base — it
  merges `.text` (which carries 0 of the image's 1,403,750 base relocations) from any dump. **The
  BATTLE-click capture does NOT have to share a launch with the existing dumps.**

### Time

**Steps 0-2: ~20 minutes and zero code.** Steps 0-4: one sitting, ~60-75 min. Steps 5-6 and the
deferred items: a second sitting.

---

## 8. What remains unknown, and what would settle it

| # | Unknown | Why it is unknown | What settles it | Cost |
|---|---|---|---|---|
| **1** | **`UPartyManager::TryJoinQueue`'s own preconditions.** *The largest residual.* Whether anything in it requires a completed latency measurement is genuinely `[U]`. | Page `0x5875000` is 100 % zero across every dump we own. | One BATTLE/BOTS FIND MATCH click, then `dumpimage` + `mergedumps` + `strxref func 0x5875E90`. | one click + minutes |
| **2** | Whether fixing `/core-game/regions` is **sufficient** (not merely necessary) to construct a measurer. `FRegionRoute.Enabled`, the `Routes` map key, and field-name casing are unverified against a live parse. | Never once parsed correctly. | §7 Step 6. | one restart |
| **3** | The UDP ping **packet format**. | `0x1F8CFC0` has never executed; unreadable offline. | The verbatim-echo + hexdump responder (§6.4) recovers it on the first datagram. | ~40 lines, gated |
| **4** | The **true route** for `POST …/latencies` — `.../parties/{id}/latencies` or `.../players/{id}/latencies`. | The call site is on an undecrypted page. | Let the catch-all log it. `capture.log` names the winner on the first POST. **Free — do not pre-register.** | 0 |
| **5** | Which `EPartyState` values the `PartyManager.cpp:300` guard admits. | Verbose-only, never emitted. | §7 Step 5 with its control; the guard prints the rejected value verbatim. | one relaunch |
| **6** | Whether `LogPartyManager` was compiled with `Verbose` available at all. | Compile-time verbosity is not in the log record. | The `LogSentrySdk` positive control in §7 Step 5. | free |
| **7** | Whether the in-payload `ETag` short-circuits re-ingest. | `If-None-Match` never sent; in-body semantics unread. | Bump it every time; if a content change lands with an unchanged ETag, the question is moot. | free |
| **8** | Whether `ActionInProgress` actually wedges on a `{}` response. | `/setTargetQueues`, `/joinQueue`, `/leaveQueue` have never fired. | Step 2/3: if the first click works and every later one errors, that is the latch. | free |
| **9** | Whether the bool→enum `fillTeam` coercion means the validity model has a general exception. | Mechanism unread. | Serve `"fillTeam": "Fill"` (an `EPartyFillPreference` name) as its own single variable and diff. | one restart |

---

## 9. Recording rules for whoever runs this

Both mirror-errors are live risks here. FK-5 exists because a hedged *"A OR B"* was recorded as *"A"*.
Do not now record *"not A"* as *"definitely C"*.

- If Step 2 shows **no latency call** → record **"latency is not the first blocker on the matchmaking
  path"**. **Not** "QoS is disproven" (already true, §1.3), and **not** "the regions payload is the
  gate" (unsupported).
- If Step 2 **does** show a latency call → record **"FK-5 is mis-scoped: it is Theorycraft's
  `ULatencyManager` + a UE UDP echo against a host *we* advertise, and it is the Nth blocker."**
  **Not** "FK-5 was right."
- If a step is skipped or a signal is ambiguous, write **"unresolved"** — not the more comfortable
  neighbouring claim.
- The `[M]` / `[SI]` / `[U]` tags in this document are load-bearing. Preserve them when quoting.

---

## Appendix A — Where the skeptics won

Recorded explicitly, per the review contract.

| Disagreement | Winner | Resolution |
|---|---|---|
| `CanExclude` `true` vs `false` in the regions body (probe 1 vs probes 3 & 4) | **Skeptics + probe 1** | `true`. I re-derived the gate byte-for-byte (§2.2). A `false` payload would have burned a launch on an uninterpretable null. |
| `FPartyMember.Latencies` risk LOW (probe 1) vs HIGH (probe 3) | **Plan skeptic** | **Cut entirely.** Both risk ratings are defensible; measured benefit is zero, so the trade is bad in any ordering. |
| Probe 4's `-NoHook` baseline | **Plan skeptic** | Default shim set. Comparability with every prior menu observation. |
| Probe 4's Step 1 ("click BATTLE, zero change") | **Plan skeptic** | Not executable — the tile is `Collapsed`. Replaced (and improved on) by the BOTS route, §3.3. |
| Probes 1 & 3 ranking the regions fix top-2 | **Both skeptics** | Scope drift. Regions is rank 3 and explicitly off the BATTLE path. |
| Account level (probes 3 & 4) | **All skeptics** | Cut. Falsified by the `GetCurrentQueues` count. |
| `ST_ServerLocations ''` as "the single best positive measurement" (probe 3) | **Evidence skeptic** | Demoted to weak corroboration (§4). |
| "provably never executed" (probes 1 & 2) | **Evidence skeptic** | Restated as "never executed in any **dumped** state" (§2.5). |
| `coregamerouting` toggle (probe 3 proposed it *and* flagged it) | **The flag** | Do not enable. |

**Contributed this session, beyond all four probes and both reviews:**
**C1** `FindQueueByID`'s bool resolved (§3.2, closes the top residual risk) ·
**C2** `bots` makes the decisive experiment free (§3.3) ·
**C3** no BP gate between FIND MATCH and native `TryJoinQueue` (§3.4) ·
**C4** `HasSelectedSpecialQueue` reads `GetPartyState()` first (§3.1) ·
**C5** `TryJoinQueue` takes only a delegate (§3.5) ·
**C6** `Log`-verbosity lines print with **no token** — every sibling grep pattern was broken (§2.6) ·
**C7** the Verbose bump may be inert and needs a positive control (§2.6) ·
**C8** `FParty.State` upgraded `[SI]` → `[M]` from the bind table (§3.6 #2) ·
**C9** `fillTeam` bool→enum is a live counter-example to the validity model (§6.6) ·
**C10** `IsClientVersionValid` ≠ `FParty.ClientVersion` (§3.7) ·
**C11** `FConnectionDetails` also carries a `Routes` map (§2.0) ·
plus the log-record decoder **validated against an observed ground-truth line** (§2.6).
