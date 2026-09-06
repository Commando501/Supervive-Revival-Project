# FK-5 probe: backend gap analysis + why the `/core-game/regions` negative happened

Date: 2026-07-27. Scope: **offline only.** No game launched, no injection, `server/` NOT modified.
Every claim below is tagged **[M]** measured, **[SI]** strong inference, **[H]** hypothesis.

---

## 0. Headline

**The `/core-game/regions` payload we serve does not match the target struct.** Ground truth from
`schema.txt`:

```
CoreGameManager (UClass:PlatformManager)
    ValidRegions        StructProperty (UStruct:RegionHostList)   <-- the parse target
    RefreshRegionsHandle StructProperty (UStruct:TimerHandle)

RegionHostList : (2 props)
    Regions             ArrayProperty<...>        <-- inner type mis-rendered, see §2.2
    ETag                StrProperty

RegionHost : (5 props)
    Name                StrProperty
    Addr                StrProperty
    Port                IntProperty
    CanExclude          BoolProperty
    Routes              MapProperty              (reflection also emits `Routes_Key`)

RegionRoute : (7 props)
    Enabled             BoolProperty
    IsAccelerator       BoolProperty
    Host                StrProperty
    Port                IntProperty
    PingHost            StrProperty              <-- lives HERE, not on the region
    PingPort            IntProperty
    RequiresToken       BoolProperty
```

`interactive.go:718-732` serves region objects with the keys
`RegionName / RouteName / DisplayName / Host / PingHost / Address / Port / Enabled`.
Against `FRegionHost` **only `Port` matches.** `PingHost` is a field of `FRegionRoute`, which lives
inside `FRegionHost.Routes` — and we send **no `Routes` map at all**.

Per the project's own validity model (unknown keys are ignored, only wrong-typed *matched* keys
reject), the client parsed our body **successfully** into one region with
`Name="" Addr="" Port=443 CanExclude=false Routes={}`.

> **A region with no name and no routes.** That is why nothing pinged: `ULatencyMeasurer` needs a
> `Host`/`Port` that only exists on a `FRegionRoute`. There were no routes, so no measurer, so no
> ping, so no `POST /latencies`. **The negative was never evidence about QoS. It was a shape bug.**

---

## 1. Route-by-route inventory of what `ags` serves today

| Route | Handler | Shape served | Real / stub | Client outcome |
|---|---|---|---|---|
| `GET /party/matchmaking/info` | `handleMatchmakingInfo` (`:919`) | `{Queues:[QueueDetails×4], ETag, LastUpdated}` | **real**, but the queue list is a **diagnostic trim** (`queueIDs` `:867` = `tutorialNew, training, practice, bots`) | accepted; only 4 tiles unlock **[M]** |
| `GET /party/matchmaking/customGameModes` | `handleMatchmakingCustomGameModes` (`:931`) | `{Modes:[], ETag, LastUpdated}` | typed-empty stub | accepted **[M]** |
| `GET /core-game/regions` | `handleCoreGameRegions` (`:718`) | `{Regions:[{RegionName,RouteName,DisplayName,Host,PingHost,Address,Port,Enabled}]}` | **wrong shape** (§0) | parses to an EMPTY region **[SI]** |
| `GET /core-game/players/{id}` | `handleCoreGamePlayer` (`:574`) | `{ID, MatchID, Version, CanDisassociate}` | real `CoreGamePlayer`; `MatchID` empty unless `SoloMode` set | correct **[M]** |
| `GET /core-game/matches/{id}` | `handleCoreGameMatch` (`:604`) | full `MatchInfo` (19 props) | real, tutorial-hardcoded (`GameMode:"tutorialNew"`, `address:"127.0.0.1:7777"`) | drives travel **[M]** |
| `GET /party/players/{id}` | `handleGetParty` (`:758`) | `buildSoloParty` | real | party applies **[M]** |
| `GET /party/parties/{partyId}` | `handleGetPartyDetail` (`:811`) | `buildSoloParty` | real | party panel renders **[M]** |
| `POST /party/parties/{id}/startSoloMode` | `handleStartSoloMode` (`:838`) | echoes party, records `SoloMode` | real | fires; travel via `/core-game/players` **[M]** |
| `POST\|PUT .../members/{memberId}` | `handleSetPartyMember` | persists hero | real | **[M]** |
| **`POST .../joinQueue`** | **none** | `{}` catch-all | — | the **non-special** queue path (`default`, `deathmatch`, `bots`) **[M]** |
| **`POST .../leaveQueue`** | **none** | `{}` | — | |
| **`POST .../latencies`** | **none** | `{}` | — | never called (§3) **[M]** |
| **`POST .../setExcludedRegions`** | **none** | `{}` | — | |
| **`POST .../setTargetQueues`, `/reconcile`, `/refreshLevel`, `/refreshRanks`, `/refreshMastery`, `/refreshXPBoosts`, `/refreshRankedEligibility`, `/voiceToken`, `/referral`, `/setFillTeam`, `/setIsOpen`, `/setDiscordUserID`, `/owner`, `/leave`, `/join?joinSecret=`** | **none** | `{}` | — | full table recovered from `.rdata` `0x08B4C1B8-0x08B4C4D0` **[M]** |
| WS `/lobby` | `lobby.Handle` | AccelByte v1 text protocol; answers `listOfFriends*`, `setUserStatus`; everything else logged only | real-ish | **[M]** |
| WS `/notifications*` | `lobby.Handle` + messenger registry | heartbeat 30 s; **dropped on loadout write** (`enableMessengerDrop = true`) | real | the S85 latency fix **[M]** |
| WS `phantomDsPush` / `phantomMatchmakingFlow` | `lobby.go:385/453` | `matchmakingNotif` pushes | **DISABLED** (`phantomDsPushDelay = 0`, `phantomMatchmakingSequence = false`) | inert **[M]** |

### 1.1 `buildSoloParty` vs the real `FParty` (17 props)

Served and **matched**: `id`→`ID`, `version`→`Version`, `ownerId`→`OwnerID`, `members`→`Members`,
`targetQueueId(s)`→`TargetQueueID(s)`, `isOpen`→`IsOpen`, `fillTeam`→`FillTeam`.

Served and **ignored** (no such UPROPERTY): `partyId`, `leader`, `leaderId`, `invitees`,
`invitationToken`, `joinSecret`, `inQueue`, `createdAt`. **[M]**

**Never served but real:** `State` (Str), `ClientVersion` (Str), `IsRanked`, `MillisInQueue`,
`QueueJoinTime`, `ExcludedRegions`, `Requests`, `CustomGameDetails`, `DiscordJoinSecret`.

> ★ `Party.State` is the field the `handleStartSoloMode` comment calls *"the durable fix … (key not
> yet mapped)"* for the `PartyModel+0x558+0x18 == "default"/"Matchmaking"` memory poke. **It is
> mapped: `Party.State`, a `StrProperty`.** Enum `EPartyState::{Default,Matchmaking,CustomGame,Unknown}`
> at `.rdata 0x08ABD2A8-0x08ABD390`. **[M]** for the field+enum, **[SI]** that `"default"` is the
> accepted wire value (the native comparison is against a lowercased string per the existing note).

On the member (`FPartyMember`, 23 props) we serve `id/userId/memberId`, `displayName`, `ready`,
`heroAssetId`, `personalizationLoadout`. **Never served but real: `Latencies`, `AccountLevel`,
`MasteryLevel`, `Rating`, `Rank`, `IsRankedEligible`, `ReferralCode`, `XPBoosts`.** `region` is
served and is **not** a `FPartyMember` field — it is silently dropped. **[M]**

---

## 2. Why the regions negative happened — the full mechanism

### 2.1 What was measured, and what was *not*

**[M]** `docs/capture.log` shows 7 × `GET /core-game/regions → 200` in the 2026-07-26 session
(lines 187, 5718, 5981, 10761, 10847, 13002, 13118).

**[M]** The live `Loki.log` for that same session (`…/Saved/Logs/Loki.log`, `20:20-20:24` UTC =
`15:20-15:24` local) contains **zero** `LogLokiPlatformQuery` and **zero** `LogJson` lines. Those
categories do fire when a parse fails (`Loki_2.log:2848` has one). **⇒ the current object-envelope
body is accepted without a parse error.** The 2026-06-29 `Deserialization failure` was against the
*bare array*; the `{"Regions":…}` flip fixed the envelope and the fix was never re-examined.

**[M]** `Loki.log:2151`:
```
LogStringTable: Warning: Failed to find string table entry for
  '/Game/Loki/UI/Widgets/FrontEnd/MainMenu/Party/Latency/ST_ServerLocations.ST_ServerLocations' ''.
```
The lookup key is the **empty string**. The latency widget ran and asked for the display name of a
region whose name is `""`.

**[M]** `LogLatencyManager` appears in **zero** Loki logs on disk (12 files checked). Neither
`Creating new latency measurer for %s %s`, nor `Could not ping target host: %s:%d. Result: %d`, nor
`Member latencies set` has ever been emitted.
*Caveat, stated because it matters:* absence of a log line is weak evidence on its own — the
measurer-creation line may be `Verbose` and suppressed in Shipping. The ping-failure line would
almost certainly be `Warning` and would have fired on a loopback timeout, which is why the silence
corroborates "no measurer was ever created" rather than "the ping failed". **[SI]**

**[M]** `QosManagerServerUrl=` is empty in **all 12** AccelByte env sections of
`tools/extractor/out/DefaultEngine.ini` — independently reproduced this session.

### 2.2 The mechanism

**[M]** from the binary (`tools/strxref`, `dumps/merged.dump.exe`):

| Evidence | Address |
|---|---|
| `/core-game/regions` referenced exactly once, by `fn 0x57B56B0` (2582 B), which also touches `Bearer `, `Authorization`, `If-None-Match` | site `0x57B5F85` |
| `LatencyManager.cpp` TU string cluster | `0x08B43230-0x08B43480` |
| `&ULatencyManager::OnClientConfigUpdated`, `&ULatencyManager::OnLatencyUpdated` | `0x08B43230`, `0x08B43280` |
| `Creating new latency measurer for %s %s` — **two** `%s` | `0x08B43410`, in `fn 0x57BECF0` (862 B) |
| `Could not ping target host: %s:%d. Result: %d` — host **and port** and a status code | `0x08B43480`, in `fn 0x57DAB63` (363 B) |
| `ULatencyMeasurer` props: `Host, Region, Route, Port, PingHostHandle, Received, PreviousLatency, bHasReceivedPings` | `schema.txt:21984` |
| `ULatencyManager` props: `OnRegionsUpdated, OnAllRegionsUpdated, OnRegionRoutePreferencesUpdated, CoreGameManager, ClientConfigManager, Latencies(Map), UserRegionRoutePreferences(Map), DefaultRegionRoutePreferences(Map)` | `schema.txt:21975` |

Chain **[SI]** (each link individually **[M]**):
`UCoreGameManager` fetches `/core-game/regions` on `RefreshRegionsHandle` → stores `ValidRegions`
(`FRegionHostList`) → broadcasts `OnRegionsUpdated` → `ULatencyManager` creates one
`ULatencyMeasurer` **per (Region, Route)** — matching the two `%s` and the measurer's `Region`+`Route`
fields — seeded with `FRegionRoute.PingHost` / `.PingPort` → the measurer pings and, on change,
`UPartyManager` POSTs `/latencies`.

Our payload supplies zero `Routes` ⇒ zero measurers ⇒ zero pings ⇒ zero `/latencies` ⇒
`ST_ServerLocations['']`.

### 2.3 The inner-type trap (this is the QueueInfo bug repeating)

`schema.txt` renders `RegionHostList.Regions` as `ArrayProperty<StrProperty>`. **Do not trust that.**
The same file renders:

* `QueueInfo.Queues` as `ArrayProperty<StrProperty>` — **live-falsified**; it is
  `ArrayProperty<StructProperty QueueDetails>` (`interactive.go:880-886` records the exact client error).
* `AccelByteModelsQosRegionLatencies.Data` as `ArrayProperty<StrProperty>` — the AccelByte SDK
  declares `TArray<FAccelByteModelsQosRegionLatency>`.
* `MemberLatencies.Latencies` and `PartyMember.Latencies` as `ArrayProperty<StrProperty>` — while a
  `MemberServerLatency {Host, Region, Route, AvgLatency}` struct exists and is referenced by nothing else.
* `LatencyMeasurer.Latencies` as `ArrayProperty<StructProperty TimerHandle>`, and
  `CoreGameMatchDetails.Participants`/`StateEnum` with the struct name attached to the wrong property.

**⇒ [M]: `schema.txt`'s array inner-types are unreliable; `ArrayProperty<StrProperty>` frequently
means "array of an unresolved struct".** For `RegionHostList.Regions` the intended element is
`FRegionHost` **[SI]** (it is the only struct shaped like a region host and nothing else references it).

If the inference is wrong the client will say so by name, exactly as it did for `Queues`:
`ImportText (Regions): Missing opening parenthesis: …` — one launch settles it.

---

## 3. `POST /latencies` — what it is, and what it is not

**[M]** the guard strings, all in `Services/Party/PartyManager.cpp` (`0x08B4B270`):

```
0x08B4B220  'skipping set latencies, no valid party'
0x08B4B2E0  'skipping set latencies, party state: %s'
0x08B4B350  'skipping set latencies, player not in party'
0x08B4B3D0  'skipping set latencies, no changes'
0x08B4B440  'setting changed latency,  Host: %s, Region: %s, Route: %s, current: %f, prior: %f, chg: %f'
0x08B4B520  'setting new latency, Host: %s, Region: %s, Route: %s, current: %f'
0x08B4B5D0  'skipping set latencies, no changes over set threshold'
0x08B4B660  'Member latencies set'                                                fn 0x585D1E0 (69 B)
0x08B4B6B0  'Failed to set latencies, status: %d, connected: %hhd, msg: %s - %s'  fn 0x585D230 (144 B)
```

`Host / Region / Route / <float>` is **exactly** `FMemberServerLatency {Host, Region, Route, AvgLatency}`.
This is a **party member-state write**, not a QoS handshake. **[M]**

Zero hits today is fully explained without any QoS hypothesis: no measurers ⇒ no latency values ⇒
`no changes` ⇒ the POST is skipped client-side before any HTTP is attempted. **[SI]**

### 3.1 Request shape (client → us)

```json
{ "Latencies": [ { "Host":"127.0.0.1", "Region":"na", "Route":"default", "AvgLatency": 3.0 } ] }
```
`FMemberLatencies` **[SI]** — `MemberLatencies` is the only struct with a lone `Latencies` array and
its name is the UStruct registered at `0x08ABBBF8`.

### 3.2 Route

**[M]** the builder pattern is `'/party/parties/' + '/joinQueue'` (`fn 0x584C520`, `POST`).
`'/latencies'` sits in the same endpoint table but its call site is in an undecrypted `.text` page
(`refs=0`), so the exact assembly is unresolved. Two candidates:
`POST /party/parties/{partyId}/latencies` or `POST /party/parties/{partyId}/members/{memberId}/latencies`.
**Register both** — the loser never fires, and `docs/capture.log` will print the true path the first
time a measurer exists.

### 3.3 Response

Success callback is 69 bytes and logs one line with no fields ⇒ it reads nothing from the body **[SI]**.
Echo the party document, consistent with `startSoloMode` / `setPartyMember`.

---

## 4. The `ClientConfiguration` lever — real, but narrow. It is **not** the region source.

**[M]** `ULatencyManager::OnClientConfigUpdated` is `fn 0x57DC9CD` (1377 B) and touches exactly four
strings, in order:

```
+0x1DC  'coregamerouting'              (ASCII)
+0x20B  'minLatencyDifference'         (ASCII)
+0x2E2  'minRouteLatencyDifference'    (ASCII)
+0x3AB  'Invalid minRouteLatencyDifference value: %s'
```

**[M]** `ClientConfiguration` has 12 props — `ClientVersions, ServiceHostnames, FeatureToggles,
PlaytestEnabled, PlaytestWindows, InventoryFreeVersion, StatusMessages, VendorConfigs, CohortConfigs,
BannerConfigs, ETag, LastUpdated`. **There is no region/host/latency container in it.**

**[SI]** `coregamerouting` is a **FeatureToggle key**: `FFeatureToggle {Config: TMap<FString,FString>}`
(already RE'd, `loki.go`), the two sub-keys are read as strings ("Invalid … value: %s"), and the
consumer `fn 0x58B9D30` logs `'coregamerouting is enabled'` — the classic toggle predicate.

> **Answer to "is ClientConfiguration the cheapest lever?" — No.** It carries only two float
> *thresholds* for route preference. The region/host list travels on `/core-game/regions` and nowhere
> else. Recording the opposite would be the mirror of the FK-5 error.

### 4.1 …and enabling it is currently a **risk**, not a win

**[M]** `fn 0x58B9D30` (3116 B) is the **match-travel** function:

```
'Attempting to travel to Match: ID:"%s" Address:"%s" Fleet:"%s" Region:"%s" Machine:"%s" '
'coregamerouting is enabled'
'using route preference [%s] for region [%s]'
'no route preference found for region [%s], falling back to default route'
'force_route'
'forcing route to [%s] for region [%s]'
'route [%s] is disabled, falling back to default route'
'route [%s] not found for region, falling back to default route'
'using route [%s]: address [%s], requiresToken [%d]'
'routing token required but LokiSocketSubsystem not found'
'failed to decode routing token: %s'
'setting routing token: %s'
'ConnectionSecret=%s' / 'ClientBuildVersion=%s'
'starting match transition, address: %s'
```

With the toggle enabled, travel resolves its address **from the route table** instead of from
`MatchInfo.ConnectionDetails.address`. Turning it on before `/core-game/regions` carries a valid
`Routes` map could break the one thing that currently works. **Leave it absent (= disabled) until
step 1 lands.**

---

## 5. Proposed diffs — **NOT APPLIED.** `server/` untouched.

### P1 — `handleCoreGameRegions`: emit the real `FRegionHostList`  ★ highest value / lowest risk

```go
// interactive.go, replacing lines 718-732 (keep the 2026-06-29 comment block, append this):
//
// 2026-07-27 — PROBE #3: SHAPE CORRECTION. The object envelope (probe #2) parses cleanly
// (live Loki.log 2026-07-26 has zero LogLokiPlatformQuery / LogJson lines across 7 fetches),
// but it deserialized into an EMPTY region. Ground truth, schema.txt:
//   UCoreGameManager.ValidRegions : FRegionHostList{ Regions[], ETag }
//   FRegionHost { Name, Addr, Port, CanExclude, Routes: TMap<FString,FRegionRoute> }
//   FRegionRoute { Enabled, IsAccelerator, Host, Port, PingHost, PingPort, RequiresToken }
// PingHost is a field of the ROUTE, not the region — and we sent no Routes at all, so
// ULatencyManager had nothing to build a ULatencyMeasurer from ("Creating new latency
// measurer for %s %s" = Region + Route; measurer fields are Host/Region/Route/Port).
// That is why the client never pinged and why the latency widget looked up
// ST_ServerLocations with an EMPTY key (Loki.log:2151).
//
// TRAP: schema.txt renders Regions as ArrayProperty<StrProperty>. It rendered QueueInfo.Queues
// the same way and was WRONG (live: "ImportText (Queues): Missing opening parenthesis"). The
// element is FRegionHost. If this is wrong the client names it the same way — read Loki.log.
func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
	route := map[string]any{
		"Enabled":       true,
		"IsAccelerator": false,
		"Host":          "127.0.0.1",
		"Port":          7777,          // the DS/stub port MatchInfo already advertises
		"PingHost":      "127.0.0.1",
		"PingPort":      7777,          // must match the UDP echo responder (P5)
		"RequiresToken": false,         // no routing token; we have no LokiSocketSubsystem
	}
	region := map[string]any{
		"Name":       "na",             // <- the ST_ServerLocations key; "" today
		"Addr":       "127.0.0.1",
		"Port":       7777,
		"CanExclude": false,            // never let the region be excluded away
		"Routes":     map[string]any{"default": route},
	}
	writeJSON(w, map[string]any{
		"Regions": []any{region},
		"ETag":    "revival-regions-v1", // bump on any content change (see If-None-Match below)
	})
}
```

Notes:
* `fn 0x57B56B0` sends `If-None-Match`. The handler ignores it and always 200s — correct, but bump
  `ETag` whenever the body changes so a caching client cannot latch stale content.
* `Name:"na"` must equal `MatchInfo.Region` (`interactive.go:692` already `"na"`) and
  `ConnectionDetails.RegionID`.
* **Risk:** if `Regions` really is `TArray<FString>`, the whole doc is rejected → `ValidRegions`
  empty, i.e. **today's state**, plus a named `LogJson` warning. The one real hazard is a
  parse-failure retry storm (the `progressiontracks` failure once produced ~100 req/s). Watch the
  `/core-game/regions` rate in `capture.log`; if it spikes, revert immediately.

### P2 — restore the queue list + serve an account level  ★ required to even click BATTLE

```go
// interactive.go:867 — the S60 diagnostic trim was never reverted.
var queueIDs = []string{
	"default", "deathmatch", "practice", "dropin", "customgame",
	"bots", "tutorialNew", "training", "armorydeathmath", "tournament",
}
```
The "served account level = 0" the S60 comment blames has **two** candidate sources. Try the
zero-code one first:

**(a) NO CODE — set it from the admin panel.** `GetLevelGameFeatureUnlocked` / `GetAccountLevel` /
`GetLocalAccountLevel_BP` are reflected UFUNCTIONs (`0x08972358`, `0x08A27078`, `0x08A28458`) **[M]**,
and in SUPERVIVE the account level *is* the Hunter's Journey ladder **[SI]** (`AccountLevelItemUnlocks`,
`LastSeenAccountLevel`, and `clientProfile.lastSeenAccountLevel` at `interactive.go:200` all sit
alongside the pass). The backend already owns that number: `GET /progression/players/{id}` serves
`AccountPass{Level,XP,Cleared}`, admin-settable via `PUT 127.0.0.1:9210/api/progression/{id}`, with a
live round-trip verified at tier 34 (S83). **Set the level high there and re-test — no rebuild, no
restart, revertible in one PUT.**

**(b) belt-and-braces, one line each** — `FPartyMember.AccountLevel`/`MasteryLevel` are real Int props
we have never served:
```go
// interactive.go, inside buildSoloParty's `member` literal (~:1128)
"accountLevel": 50,
"masteryLevel": 1,
```
**Risk: low.** Both are Int against Int-typed matched props. If `CanControlQueue` still fails, the
trim is re-applied as a one-line revert.
**Why it matters for FK-5:** `default` (= BATTLE) is not advertised at all today, so the cheapest
experiment in the FK-5 brief *cannot run* until this lands. **[M]**

### P3 — serve `Party.State` (durably replaces the memory poke)

```go
// interactive.go, in buildSoloParty's returned map (~:1190):
// FParty.State (StrProperty). EPartyState::{Default,Matchmaking,CustomGame,Unknown}
// (.rdata 0x08ABD2A8..0x08ABD390). This is the field handleStartSoloMode's note calls
// "the durable fix … (key not yet mapped)" for the PartyModel+0x558+0x18 gate, and it is
// also what 'skipping set latencies, party state: %s' reads.
"state":         partyState,   // "default"
"clientVersion": "release2.4.live-156430-shipping", // FParty.ClientVersion; PartyManager.cpp
                                                    // logs 'Client version not valid, leaving matchmaking'
"isRanked":      false,
```
**Risk: medium-low.** New matched Str props on a load-bearing document; wrong *value* only changes
the state machine, wrong *type* is impossible (both are Str). Test alone.

### P4 — register the unserved party writes (pure additive, zero risk)

```go
// interactive.go Register(), after the startSoloMode line (~:136).
// Recovered verbatim from the exe's party endpoint table (.rdata 0x08B4C1B8..0x08B4C4D0);
// all of these currently fall through to the {} capture stub.
mux.HandleFunc("POST /party/parties/{partyId}/joinQueue",  s.handleJoinQueue)
mux.HandleFunc("POST /party/parties/{partyId}/leaveQueue", s.handleLeaveQueue)
mux.HandleFunc("POST /party/parties/{partyId}/setExcludedRegions", s.handleSetExcludedRegions)
// The /latencies call site is in an undecrypted .text page, so the path is unresolved.
// Register BOTH candidates; the loser never fires and capture.log prints the truth.
mux.HandleFunc("POST /party/parties/{partyId}/latencies", s.handleSetLatencies)
mux.HandleFunc("POST /party/parties/{partyId}/members/{memberId}/latencies", s.handleSetLatencies)
```
```go
// handleSetLatencies answers the party member-latency write. Body is FMemberLatencies
// { Latencies: []FMemberServerLatency{Host, Region, Route, AvgLatency} } — recovered from
// PartyManager.cpp's own log formats:
//   'setting new latency, Host: %s, Region: %s, Route: %s, current: %f'
//   'setting changed latency,  Host: %s, Region: %s, Route: %s, current: %f, prior: %f, chg: %f'
// The success callback (fn 0x585D1E0, 69 B) logs 'Member latencies set' and reads nothing from
// the response, so echoing the party is safe and keeps every party write uniform.
// NOTE: reaching this handler at all is the FK-5 experiment's success signal.
func (s *Service) handleSetLatencies(w http.ResponseWriter, r *http.Request) {
	id := playerIDFromParty(r) // same partyId-prefix-then-JWT recovery the siblings use
	var body struct {
		Latencies []struct {
			Host, Region, Route string
			AvgLatency          float64
		}
	}
	_ = json.NewDecoder(r.Body).Decode(&body)   // best-effort; never fail the write
	log.Printf("interactive: setLatencies player=%s path=%s n=%d %+v",
		id, r.URL.Path, len(body.Latencies), body.Latencies)
	s.store.update(id, func(st *playerState) { /* persist for §P6 echo-back */ })
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id),
		s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))
}
```
`handleJoinQueue` should mirror `handleStartSoloMode`: log `mode/queue`, record it, echo the party.
**Risk: none** — these paths already return `{}` 200 via the catch-all; we are only adding logging,
persistence and a correct body.

### P5 — a UDP echo responder on `PingPort` (only meaningful after P1)

`'Could not ping target host: %s:%d. Result: %d'` carries **a port**, so the measurer uses UE's
`FIcmp::UDPEcho` rather than raw ICMP (`Result` = `EIcmpResponseStatus`). **[SI]** — UE's ICMP module
*is* linked in this build (`IcmpModule.cpp`, `IcmpWindows.cpp` strings present) and the ICMP variant
takes no port.

~40 lines in `server/cmd/ags` (or a new `server/internal/qos`): bind `udp4 127.0.0.1:7777`, echo
every datagram back to its sender verbatim. UE's `UDPEcho` sends a small payload and matches the
reply.
**Risk: none to the menu** (separate socket, separate goroutine).
**Do not build this first.** With P1 unlanded there is nothing to answer; with P1 landed and no
responder, the expected log is `Could not ping target host: 127.0.0.1:7777. Result: <timeout>` —
which is itself a *positive* result: it proves the measurer exists.
**⚠ Port collision:** `127.0.0.1:7777` is the DS stub's port. The DS stub binds **UDP** 7777 too
(UE netdriver). If the stub is running, pick a distinct `PingPort` (e.g. 7788) in P1.

### P6 — member latencies on the party document (probe #5)  ⚠ do this LAST and ALONE

```go
// buildSoloParty member literal — FPartyMember.Latencies.
"latencies": []any{map[string]any{
	"Host": "127.0.0.1", "Region": "na", "Route": "default", "AvgLatency": 3.0,
}},
```
**Does it sidestep measurement?** Partially, and only in one of two worlds:
* If the START gate is **server-side** (a real backend refusing to matchmake a member with no
  latencies) — we *are* the server, so this fully sidesteps it. **[H]**
* If the gate is **client-side** — `ULatencyManager::GetFastestRegionMeasurer` /
  `AllMeasurersReported` (both reflected UFUNCTIONs, `0x08863328` / `0x088632C8`) read the client's
  own measurer map, which this cannot populate. Then it does nothing. **[SI]**

**⚠ This is the single riskiest proposal.** `Latencies` is a **matched** key on the party document,
whose rejection empties the whole party — party panel, hero preview, avatar, target queue. The inner
type is the same `ArrayProperty<StrProperty>` render that was wrong for `Queues` (§2.3). If the
element really is a plain string, a struct array rejects the doc and **the working menu regresses.**
Gate it behind a `const serveMemberLatencies = false`, flip it in isolation, and revert on any
`LogJson` warning naming `Latencies`.

### P7 — `featureToggles["coregamerouting"]` — **hold**

Do not add it. Absent = disabled = the current, working travel path (§4.1). Once P1 serves a real
`Routes` map with `RequiresToken:false`, the follow-up is
`{"config":{"default":"true","minLatencyDifference":"20","minRouteLatencyDifference":"20"}}` in
`loki.go`'s `featureToggles` map — as a **separate single-variable test**.

---

## 6. Ranking: (moves the needle) / (risk to the working menu)

| # | Change | Moves needle | Menu risk | Verdict |
|---|---|---|---|---|
| **P1** | real `FRegionHostList` on `/core-game/regions` | **high** — it is the actual defect | **low** (worst case = today + a named warning; watch for a poll storm) | **do first, alone** |
| **P2** | restore `queueIDs` + serve `accountLevel` | **high** — BATTLE is not clickable without it; the FK-5 experiment can't run | low | **do second** |
| **P4** | register `joinQueue` / `latencies` / `leaveQueue` / `setExcludedRegions` | medium — turns a silent `{}` into evidence | **none** | **do with P2** (free) |
| **P3** | `Party.State` / `ClientVersion` | medium — retires a memory poke; feeds the `/latencies` guard | med-low | third |
| **P5** | UDP echo responder on `PingPort` | medium — only after P1 creates a measurer | none | fourth |
| **P6** | member `Latencies` on the party doc | low-medium, world-dependent | **HIGH — can empty the party document** | last, gated, alone |
| **P7** | enable `coregamerouting` | low | **can break working travel** | hold |

**Anything that could regress the working menu:** P6 (party-doc rejection — the serious one), P3
(new matched props on the same document), P2's `accountLevel` (Int-on-Int, near-zero), and P1 only
via a parse-failure retry storm. P4 and P5 cannot regress anything.

---

## 7. The decisive live experiment (for the USER to run — one launch)

Apply **P1 + P2 + P4 only.** Nothing else. Then:

1. Launch normally, reach the main menu, open PLAY.
2. `capture.log`: `GET /core-game/regions` rate must stay at its current ~7/session. A spike = P1
   parse failure → revert P1.
3. `Loki.log`, in order — each line is one bit:
   * `LogJson … ImportText (Regions)` → **P1's inner type is wrong**; element is a string, not `FRegionHost`. Done, one variable settled.
   * `LogStringTable … ST_ServerLocations 'na'` (or the warning **gone**) → **the region name reached the UI.** P1 landed.
   * `LogLatencyManager: Creating new latency measurer for na default` → **a measurer exists.** The regions negative is fully explained and closed.
   * `Could not ping target host: 127.0.0.1:<port>` → measurer alive, no responder. **Build P5.**
   * *(no ping line, no measurer line)* → measurer creation has a gate we have not found; next probe is `fn 0x57BECF0`'s caller.
4. Click **BATTLE** (now advertised by P2), then **FIND MATCH**.
   * `capture.log` shows `POST /party/parties/…/joinQueue` → **QoS was never the first blocker**; the blocker is the unserved `joinQueue`/matchmaking flow. This is the single most informative outcome.
   * `capture.log` shows `POST …/latencies` → the latency subsystem came alive end-to-end.
   * Neither, and no BP/native log → the bail is inside native `TryJoinQueue`; next probe is a live
     RPM/disasm of it (the S60 note already localised it there).

**One-bit criterion for FK-5 itself:** does the click reach `POST …/joinQueue` **before** anything
latency-shaped is requested? If yes, QoS/latency is not the gate and the roadmap should point at the
matchmaking write path.

---

## 8. Corrections this probe makes to the record

1. **[M]** `/core-game/regions` is **accepted** today (no parse error) — the audit's implicit "it was
   served correctly and the client refused to ping" is wrong on the first half.
2. **[SI]** The client never pinged because it never had a ping **target**: `PingHost` belongs to
   `FRegionRoute` inside `FRegionHost.Routes`, and we send no `Routes`.
3. **[M]** `/latencies` is a **party member-state write** (`FMemberServerLatency{Host,Region,Route,AvgLatency}`),
   not a QoS ping responder.
4. **[SI]** `ClientConfiguration` does **not** carry the region list. `coregamerouting` is a
   FeatureToggle carrying two route-preference thresholds. The "region list may ride
   ClientConfiguration" hypothesis is **falsified as a supply route** (it remains true as a *tuning*
   route).
5. **[M]** `Party.State` is the previously-unmapped key behind the `startSoloMode` memory poke.
6. **[M]** `queueIDs` is still the S60 diagnostic trim — `default` (BATTLE) is not advertised, so the
   FK-5 "cheapest experiment" cannot be run as written until P2 lands.
7. **[M]** `schema.txt` array inner-types are unreliable; four independent mis-renders documented in §2.3.

**What this probe does NOT establish:** whether a completed latency measurement is *required* to
matchmake. Nothing found offline gates `TryJoinQueue` on latency. That remains open and is exactly
what §7 step 4 measures.
