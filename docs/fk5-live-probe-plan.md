# FK-5 — the decisive live probe (design + runnable script)

**Status:** DESIGN ONLY. Nothing in this document has been applied. No game was launched, no shim
injected, no file under `server/` modified. Every diff below is a **proposal**.

**FK-5 (from `docs/ignorance-map-s101.md:238`):** *"The BATTLE/PRACTICE blocker is an AccelByte QoS
UDP ping responder."* Severity CRITICAL because it points the roadmap at the wrong subsystem.

**Every claim in this document is tagged `MEASURED` / `STRONG_INFERENCE` / `HYPOTHESIS`.** FK-5 exists
because a hedged "A **OR** B" was recorded as "A". This document must not commit the mirror error, so
nothing below is written as "definitely C" unless a measurement supports it.

---

## 0. What changed offline before this probe was designed

Read this section first — it changes what the probe should test, and it means Step 1 is not the same
experiment the audit proposed.

### 0.1 The menu latency pipeline, recovered end to end

`MEASURED` — from `schema.txt` (the project's own extracted reflection schema), `tools/strxref/strxref.py`
against `dumps/merged.dump.exe`, and 7 archived `Loki.log` files.

```
GET /core-game/regions
  └─> CoreGameManager.ValidRegions : FRegionHostList              [schema.txt:13007,13016]
        FRegionHostList { Regions : TArray<...>,  ETag : FString } [schema.txt:43179]
        FRegionHost     { Name, Addr, Port, CanExclude,
                          Routes : TMap<...> }                     [schema.txt:43173]
        FRegionRoute    { Enabled, IsAccelerator, Host, Port,
                          PingHost, PingPort, RequiresToken }      [schema.txt:43182]
  └─> ULatencyManager   { OnRegionsUpdated, OnAllRegionsUpdated,
                          OnRegionRoutePreferencesUpdated,
                          CoreGameManager, ClientConfigManager,
                          Latencies, UserRegionRoutePreferences,
                          DefaultRegionRoutePreferences }          [schema.txt:21975]
        logs  "Creating new latency measurer for %s %s"            [rdata 0x08B43410]
  └─> ULatencyMeasurer  { Host, Region, Route, Port,
                          PingHostHandle, Received,
                          bHasReceivedPings, PreviousLatency }     [schema.txt:21984]
        logs  "setting new latency, Host: %s, Region: %s, Route: %s, current: %f"   [0x08B4B520]
              "setting changed latency, ... current: %f, prior: %f, chg: %f"        [0x08B4B440]
  └─> UPartyManager::SetLatencies                                  [PartyManager.cpp, 0x08B4B270]
        guards, all LogPartyManager:
              "skipping set latencies, no valid party"             [0x08B4B220]
              "skipping set latencies, party state: %s"            [0x08B4B2E0]
              "skipping set latencies, player not in party"        [0x08B4B350]
              "skipping set latencies, no changes"                 [0x08B4B3D0]
              "skipping set latencies, no changes over set threshold" [0x08B4B5D0]
  └─> POST /party/parties/{partyId}/latencies                      [suffix 0x08B4C378]
        body ≈ FMemberLatencies { Latencies : [ FMemberServerLatency
                                   { Host, Region, Route, AvgLatency } ] }
                                                                   [schema.txt:30765, 30774]
        success  fn 0x585D1E0 (69 B) → "Member latencies set"      [0x08B4B660]
        failure  fn 0x585D230 (144 B) → "Failed to set latencies, status: %d, ..." [0x08B4B6B0]
```

### 0.2 The route for `/latencies` is now pinned

`MEASURED` — `strxref near 0x08B4C378` shows `/latencies` sitting inside `PartyManager.cpp`'s endpoint
**suffix** pool, between `/setExcludedRegions` and `/referral`, in a run that also contains
`/members/`, `/setIsOpen/`, `/joinQueue`, `/leaveQueue`, `/setTargetQueues`, `/refreshLevel`,
`/startSoloMode?mode=`, `/reconcile`, `/voiceToken`. Two of those (`/startSoloMode?mode=`,
`/setIsOpen/True`) are already **capture-confirmed** as `/party/parties/{partyId}/<suffix>`.

`STRONG_INFERENCE` — the route is **`POST /party/parties/{partyId}/latencies`**.

`MEASURED` — it is **not registered** in `server/` (0 hits) and therefore already falls through to
`capture.StubHandler` → **HTTP 200 `{}`, and the request line + body are written to `docs/capture.log`**
(`server/internal/capture/capture.go:175` for the stub; `Logger.Middleware` in the same file reads and
logs the body of every request, matched or not).
⇒ **We do not need a handler to detect it. It self-reports the moment it fires.**

### 0.3 The three measurements that dethrone "QoS is the blocker"

| # | Measurement | Source |
|---|---|---|
| M1 | `"Creating new latency measurer"` has **never** appeared in any `Loki.log` the project holds (7 logs, 2026-07-05 → 2026-07-26). | `grep -h "latency measurer" *.log` → empty |
| M2 | `LogLatencyManager` has **never emitted a single line**, ever. | `grep -h "LogLatencyManager" *.log` → empty |
| M3 | The region widget's string-table lookup fails with an **EMPTY key**: `Failed to find string table entry for '.../Latency/ST_ServerLocations.ST_ServerLocations' ''`. Present on **every** launch. | `Loki.log:2151` and 5 backups |

`STRONG_INFERENCE` — the client has **never created a latency measurer**, so it has **never pinged
anything**, so `SetLatencies` has **never run**, so `POST /latencies` was never suppressed by a missing
ping responder — **there was never a measurement to report.** The "??? — ms" display is an *empty region
key*, not a *timed-out ping*.

### 0.4 Why: our `/core-game/regions` body matches the target struct in exactly one field

`MEASURED` — `server/internal/interactive/interactive.go:718-732` currently serves:

```json
{"Regions":[{"RegionName":"na","RouteName":"na","DisplayName":"Local",
             "Host":"127.0.0.1","PingHost":"127.0.0.1","Address":"127.0.0.1",
             "Port":443,"Enabled":true}]}
```

Target: `FRegionHostList{ Regions, ETag }` → `FRegionHost{ Name, Addr, Port, CanExclude, Routes }`.

- `Regions` matches (good).
- Of the element's 8 keys, **only `Port` matches `FRegionHost`.** `RegionName`/`RouteName`/`DisplayName`/
  `Address`/`Enabled` match nothing; `PingHost`/`Host` belong to `FRegionRoute`, **one level down inside
  the `Routes` map** — and **we never serve `Routes` at all**.
- Per the project's validity model (`server/internal/menu/menu.go`), unmatched keys are silently
  ignored ⇒ the client builds **one `FRegionHost` with `Name=""`, `Addr=""`, `Routes={}`** and logs nothing.
- Zero routes ⇒ zero `(Region, Route)` pairs ⇒ zero measurers. That is M1/M2/M3 exactly.

`MEASURED` (negative evidence, and it is the useful kind): **no** `ImportText (Regions)` error and **no**
`Deserialization failure on ... /core-game/regions` in any log. Contrast `QueueInfo.Queues`, where serving
a **string** array against a **struct** array produced the loud
`ImportText (Queues): Missing opening parenthesis: default`.
`STRONG_INFERENCE` — `RegionHostList.Regions` is really `TArray<FRegionHost>`, and the usmap's
`ArrayProperty<StrProperty>` is the *same lie it told about `QueueInfo.Queues`*. (This is also a
**self-diagnosing** step: if the usmap is right for once, Step 5 will produce that exact `ImportText`
error and name its own fix.)

### 0.5 The FK-5 "untried lever" list needs one correction and one addition

- `FALSIFIED offline` — *"the region list may ride `ClientConfiguration`, which we already control."*
  `MEASURED`: `ClientConfiguration` has exactly 12 props (`schema.txt:11158`) and **none** is a region
  or host list. `ValidRegions` lives on `CoreGameManager`, fed by `GET /core-game/regions`.
- `STILL LIVE` — `ULatencyManager::OnClientConfigUpdated` is real (`0x08B43230`), but what it reads from
  client config is `minLatencyDifference` / `minRouteLatencyDifference` (+ `Invalid minRouteLatencyDifference
  value: %s`, all in `LatencyManager.cpp`). `HYPOTHESIS` — those are **thresholds**, and they gate
  `"skipping set latencies, no changes over set threshold"`, not the region list.
- `NEW, and it closes an item open since S61` — see §0.6.

### 0.6 ★ `Party.State` is S61's undecoded gate, and we have never served it

`MEASURED` (S61, `docs/session-61-tutorial-match-setup.txt:315-336`): `TryStartSoloMode` GATE-2 reads the
struct at `PartyModel+0x558` and requires `FString1 @ +0x18` == `"default"` (Num 8) or `"Matchmaking"`
(Num 12). S61 recorded the other fields it saw: `party-id @+0x00`, `count @+0x10` **= 1**,
`FStrings @+0x18, +0x28, +0x40, +0x50`, `bytes @+0x38/0x39`. It closed with *"Need the JSON field name"* —
still open.

`MEASURED` (`schema.txt:39846`) `Party : (17 props)`, first eight in declaration order, laid out with
`FString`=16 B / `int64`=8 B / `bool`=1 B:

| offset | schema field | S61's live observation | match |
|---|---|---|---|
| +0x00 | `ID` StrProperty | party-id FString, Num 39 | ✔ |
| +0x10 | `Version` Int64Property | "count @+0x10 **= 1**" — and `partyVersion` was **pinned to 1** at S61 | ✔✔ |
| +0x18 | **`State` StrProperty** | **FString1, must be `"default"` / `"Matchmaking"`** | ✔✔ |
| +0x28 | `ClientVersion` StrProperty | FString @+0x28 | ✔ |
| +0x38 | `IsOpen` BoolProperty | byte @+0x38 | ✔ |
| +0x39 | `FillTeam` Enum\<Str\> | byte @+0x39 | ✔ |
| +0x40 | `OwnerID` StrProperty | FString @+0x40 | ✔ |
| +0x50 | `DiscordJoinSecret` StrProperty | FString @+0x50 | ✔ |

**8 of 8.** `STRONG_INFERENCE` — S61's unnamed field is `FParty.State`; JSON key **`"state"`** (UE matches
case-insensitively).

`MEASURED` — `EPartyState` has exactly four values: `Default`, `Matchmaking`, `CustomGame`, `Unknown`
(`.rdata` 0x08ABD2A8-0x08ABD390). Exactly the two GATE-2 literals plus two more.

`MEASURED` — `buildSoloParty` (`interactive.go:1190-1219`) serves **no `state` key**, and `ClientVersion`
is likewise absent.

⇒ One three-character JSON key plausibly (a) satisfies the `"skipping set latencies, party state: %s"`
guard, and (b) retires the S61 live memory poke that `TryStartSoloMode` has needed since session 61.

### 0.7 Scope correction on "QoS"

`MEASURED` — `FNetPing`, `EPingType::{ICMP,UDPQoS}`, `net.NetPingTypes`, `ServerSetPingAddress` all live in
`Engine/Source/Runtime/Engine/Private/Net/NetPing.cpp` — that is the **in-match NetConnection** ping, not
the menu region ping. The menu path is Theorycraft's `Services/CoreGame/LatencyManager.cpp` plus UE's
`Online/ICMP` module (`IcmpModule.cpp`, `IcmpWindows.cpp`, `LogIcmp` all present).

`MEASURED` — AccelByte `QosManagerServerUrl=` is empty in all 12 environment blocks of
`tools/extractor/out/DefaultEngine.ini`, and AccelByte `QosManager` has one call-site string against
77-117 latency strings.

`HYPOTHESIS`, and this is the honest surviving form of FK-5's "OR": once measurers exist, the transport is
either **ICMP** (`FIcmpPing` — loopback `127.0.0.1` replies with **zero** server work on Windows) or a
**UDP echo** to `FRegionRoute.PingPort` (`FUDPPing::UDPEcho`). If it turns out to be the latter, a
responder is ~30 lines of Go, **not** an AccelByte QoS protocol reimplementation. Step 7 decides it and
**nothing before Step 7 depends on the answer.**

---

## 1. Launch procedure — exact, and the two things that kill a run

**Terminal A — ELEVATED PowerShell** (hosts file + `:443` + killing the prior elevated `ags`).
The script self-elevates via `Start-Process -Verb RunAs` if you forget, but then the console you're
reading is not the one holding the game.

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -NoHook
```

`-NoHook` is deliberate: **this probe needs no shim.** It is a menu-only, backend-only experiment.
Injecting the default shim set adds six variables and the "full set crashes" risk noted in the audit,
for zero benefit here. (`MEASURED`: the store/roster/missions/passes shims touch catalog, missions and
progression — none touches `CoreGameManager`, `LatencyManager` or `PartyManager`.)

**Terminal B — normal PowerShell, read-only, opened *before* you click anything:**

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\shim-status.ps1        # expect every row "absent" or "leftover" under -NoHook. That is correct.
Get-Content "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log" -Wait -Tail 0
```

**The two gotchas, both fatal and both silent:**

1. **Steam must already be running** before the launcher, or login dies with `Auth Failure 14005`
   (SteamAPI init). *(Note for the record: `docs/ignorance-map-s101.md` FK-12 grades this belief
   **MEDIUM-HIGH / N=1, never retested**. Do not spend this session testing it — just start Steam.)*
2. **Do not launch from Steam.** Steam starts the exe with no `-ini:` overrides, so the whole redirect
   is inert and every result below is meaningless.

**Where the logs land:**

| What | Path |
|---|---|
| HTTP traffic (every request, matched or not, **with bodies**) | `G:\git\Supervive Revival Project\docs\capture.log` |
| previous run / previous `ags` restart | `...\docs\capture.log.prev` |
| client log | `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` |
| `ags` stderr | `...\docs\server.out.log` |
| admin panel (while `ags` runs) | `http://127.0.0.1:9210/` |

⚠ `capture.log` **rotates to `.prev` on every `ags` start** (`capture.go:46`). Since this probe restarts
`ags` between steps, snapshot each step before the next restart (command in §3).

---

## 2. Operational constraints

| Constraint | Applies here? | Detail |
|---|---|---|
| ~3-5 min code-integrity check on `.text` patches | **No** | No shim, no patch. `-NoHook`. |
| 173-201 s force-open crash budget (use-after-free vdispatch on the force-spawned CameraActor) | **No** | We never force-open. The session stays at the main menu. `MEASURED` (FK-7/FK-8): the deterministic crash cluster is a *force-open* signature. A plain menu session is not time-boxed — a clean no-injection session held **17+ min** (S81). |
| cert re-append after an `ags` rebuild | **No, for mid-session restarts** | `MEASURED`: `tlscert.EnsureCert` (`server/internal/tlscert/tlscert.go:33-46`) **reuses** `certs/{root.crt,server.crt,server.key}` when all three exist and load. `launch-redirect.ps1:185` wipes `certs\` — a **manual** restart with the same `-certs` dir does not, so the chain is identical and `cacert.pem` stays valid. **Do not delete `certs\` between steps.** |
| Does a backend change need a game relaunch? | **No** | `MEASURED` from `docs/capture.log` timestamps: `/configuration/client` every ~30 s, `/party/matchmaking/info` every ~30 s, `/core-game/regions` re-fetched at 15:20:04, 15:21:06, 15:21:08, 15:22:29, 15:22:30 (`CoreGameManager.RefreshRegionsHandle` is a `TimerHandle`). **Park the game at the menu and iterate `ags`.** Allow ≤ 60 s for re-ingest, or force it by navigating away from and back to PLAY. |
| Admin-panel progression writes | **No restart at all** | `MEASURED` (`server/internal/admin/admin.go:203-213`): `PUT /api/progression/{id}` takes effect on the client's ~61 s progression poll. |

**Rebuild + restart `ags` without disturbing anything else (Terminal A, elevated):**

```powershell
cd "G:\git\Supervive Revival Project"
Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags
if ($?) { Start-Process -FilePath "G:\git\Supervive Revival Project\server\ags.exe" `
  -ArgumentList '-http :8080 -https :443 -log "G:\git\Supervive Revival Project\docs\capture.log" -certs "G:\git\Supervive Revival Project\certs"' `
  -WorkingDirectory "G:\git\Supervive Revival Project\server" `
  -RedirectStandardError "G:\git\Supervive Revival Project\docs\server.out.log" }
```

---

## 3. The observation kit — paste these, don't improvise greps

Save as `tools/fk5/watch.ps1` (or just paste). All read-only.

```powershell
# ---- FK5-A : has the latency subsystem run AT ALL?  (the whole probe in one grep)
$L = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
Select-String -Path $L -Pattern 'latency measurer|LogLatencyManager|setting new latency|setting changed latency|skipping set latencies'

# ---- FK5-B : did the party gate print, and WHICH gate?
Select-String -Path $L -Pattern 'LogPartyManager'

# ---- FK5-C : null control — proof the LogPartyManager/Warning channel is alive
Select-String -Path $L -Pattern 'skipping set referral code, player not in party'

# ---- FK5-D : deserialization verdict on any new body we serve
Select-String -Path $L -Pattern 'Deserialization failure|Invalid response received|ImportText|Unable to parse json|JsonValueToUProperty'

# ---- FK5-E : matchmaking / queue / version aborts
Select-String -Path $L -Pattern 'Unable to modify activity|Client version not valid|leaving matchmaking|CanControlQueue|GameFeatureUnlocked'

# ---- FK5-F : region display (cosmetic only — NOT a failure criterion)
Select-String -Path $L -Pattern 'ST_ServerLocations'

# ---- FK5-G : what did the client ASK for?  (route census of this step)
$C = "G:\git\Supervive Revival Project\docs\capture.log"
Select-String -Path $C -Pattern '^#\d+ .* (GET|POST|PUT|DELETE) ' |
  ForEach-Object { ($_.Line -split '\s\s+')[-1] } |
  ForEach-Object { $_ -replace 'party-[0-9a-f]+','party-{ID}' -replace '[0-9a-f]{24,}','{ID}' -replace '\?.*','' } |
  Group-Object | Sort-Object Count -Descending | Select-Object Count,Name -First 40

# ---- FK5-H : the money grep — anything the backend has never seen before
Select-String -Path $C -Pattern 'latencies|joinQueue|leaveQueue|setTargetQueues|setExcludedRegions|startSoloMode|refreshLevel|matchmaking|/core-game/'
```

**Snapshot a step before restarting `ags` (which rotates `capture.log`):**

```powershell
$n = "step1"   # change per step
Copy-Item "G:\git\Supervive Revival Project\docs\capture.log" "G:\git\Supervive Revival Project\docs\fk5-$n.capture.log" -Force
Copy-Item "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"   "G:\git\Supervive Revival Project\docs\fk5-$n.loki.log"    -Force
```

---

## 4. The ordered probe

**Rules.** One variable per step. Revert a failed probe **before** starting the next. Record the one-bit
criterion **before** looking at the log. Steps 0-2 require **no** backend change.

---

### Step 0 — Baseline + null controls (no change) — 6 min

**Do:** start Steam → Terminal A `.\configs\launch-redirect.ps1 -NoHook` → log in → **sit at the main
menu for 60 s and touch nothing.**

**Run:** FK5-C, then FK5-G.

**ONE-BIT CRITERION (harness alive):** FK5-C prints
`LogPartyManager: Warning: skipping set referral code, player not in party`.

- `MEASURED`: this exact line appears in **every** archived log (2026-07-05, 2026-07-19, 2026-07-26), at
  ~T+3 s. It is the sibling guard of the latency guards — **same file, same category, same Warning
  verbosity**. Its presence proves that *if a `skipping set latencies, …` line were emitted, we would see
  it.* Its absence means the **harness** is broken (wrong log file, `-NoHook` didn't take, login failed) —
  **stop and fix that**, do not interpret anything else.
- FK5-G must show `GET /party/players/…`, `GET /party/matchmaking/info`, `GET /core-game/regions`,
  `GET /configuration/client`. If `capture.log` is empty, the redirect didn't apply (Steam-launch trap).

**Also record (expected-flat baseline):** FK5-A → **empty**. FK5-F → the `''` empty-key warning.

---

### Step 1 — ★ THE VERDICT STEP. Click BATTLE and PRACTICE. **No backend change.** — 10 min

This is first because it is load-bearing and free. If the client stalls *before* any latency traffic,
FK-5's premise is void and Steps 5-7 are optional refinement rather than the critical path.

**Do:** PLAY → click the **BATTLE** tile. Then click **PRACTICE**. Then press **FIND MATCH** if it is
enabled. Wait 60 s between clicks (the polls are ~30 s). Note *visually* for each tile: does it
highlight on hover? does the pink selection border **latch**? does an error toast appear?

**Run:** FK5-H, FK5-E, FK5-A, FK5-B, FK5-D.

**ONE-BIT CRITERION:** does **`POST /party/parties/party-<id>/latencies`** appear in FK5-H?

| Outcome | Reading | Next |
|---|---|---|
| **1a.** No `/latencies`, no `/joinQueue`, and FK5-E prints `Unable to modify activity` (or the tile never latches) | **FK-5 is FALSE as stated.** The first blocker is the **queue/tile gate**, upstream of anything latency-shaped. | → Step 3 |
| **1b.** No `/latencies`, but `POST .../joinQueue` **does** fire | Tiles are fine; matchmaking starts and dies later. Read FK5-E for `Client version not valid, leaving matchmaking`. | → Step 3, then §5.2 |
| **1c.** FK5-A prints `skipping set latencies, …` | The setter **is** reached — my §0.3 inference is wrong. Whichever guard printed **is** the blocker. | → Step 6 directly |
| **1d.** `POST .../latencies` fires with a body | Latency reporting already works; FK-5 is void in the strongest sense. | Serve the endpoint (§5.4), move on |
| **1e.** FK5-D prints a new `Deserialization failure` / `Invalid response received` naming a route | That route is the real first blocker, whatever it is. | Follow it; this plan yields |

`STRONG_INFERENCE` (predicted): **1a**. Recorded here *before* the run so it can be scored.

⚠ **Do not read "no `/latencies`" as "QoS is needed".** It is the *absence of a measurement*, which is
what §0.3 already measured. Only outcome **1c** would put a ping responder on the critical path.

---

### Step 2 — NULL CONTROL: restart `ags` with **no** code change — 3 min

Purpose: distinguish "the *change* did something" from "*restarting* perturbs the client". Every later
step involves an `ags` restart, so this must be characterised once.

**Do:** snapshot Step 1 (§3), then run the rebuild+restart block from §2 **with zero edits**. Wait 60 s.
Do not touch the game.

**Run:** FK5-A, FK5-D, FK5-G.

**ONE-BIT CRITERION (expected result = "nothing changes"):** FK5-A stays **empty** and FK5-D produces
**no new** error.

- **Flat** → good, the harness is stable and later deltas are attributable.
- **Not flat** (a restart alone moves the log) → **stop.** Every subsequent single-variable claim is
  confounded until you know why. Likely causes: a dropped `/notifications` socket forcing a party resync,
  or a transient 5xx window while `ags` rebinds.

---

### Step 3 — Restore the 10 queue ids (single variable) — 8 min

This is the audit's own item 1.9, and Step 1 outcome 1a makes it the actual first blocker.

**Proposed diff — `server/internal/interactive/interactive.go:867-869` (DO NOT APPLY; propose to the user):**

```go
// S60 diagnostic trim RESTORED 2026-07-27 (FK-5 probe step 3). The trim to the level-0
// set was a diagnostic, never reverted; it actively degrades BATTLE + PRACTICE.
var queueIDs = []string{
	"default", "deathmatch", "practice", "dropin", "customgame",
	"bots", "tutorialNew", "training", "armorydeathmath", "tournament",
}
```

(`armorydeathmath` is the game's own misspelling — keep it verbatim.)

**Do:** apply, rebuild+restart (§2), wait 60 s, re-click **BATTLE**.

**ONE-BIT CRITERION:** does the BATTLE tile's selection border **latch** (the same visible behaviour
"BASIC TRAINING now LATCHES, pink border holds" already records for tutorialNew)?

- **Latches** → the trim *was* the blocker. Go to Step 5. Leave the restore in permanently.
- **Does not latch**, FK5-E prints `Unable to modify activity` → `CanControlQueue`'s
  `GetLevelGameFeatureUnlocked` loop is failing on a level-gated queue. → Step 4.
- **Whole tile row breaks / every tile locks** → a `QueueDetails` element is malformed. Check FK5-D for
  `ImportText (Queues)`. **Revert to the 4-id set before continuing.**

---

### Step 4 — Raise the account level. **No restart, no relaunch.** — 5 min

Only if Step 3 hit the level gate.

⚠ **Correction to the audit.** `docs/coverage-audit-s101.md:589` says *"Serve a high `lastSeenAccountLevel`"*.
`MEASURED`: `lastSeenAccountLevel` is a field of **`ClientProfileData.clientVisibilityTracking`** — it is
**client-written** state for "NEW" badges (the client POSTs it back to us; see `capture.log` bodies), not
an authority on level. Serving it high is expected to do **nothing**.

`HYPOTHESIS` — the menu account level is the **Hunter's Journey / AccountPass Level** that the backend
already owns and that S83 proved the client's native ingester adopts (`0x585A570`; PM+0x17C Level 0→12→34,
live-verified twice).

**Do (Terminal B, no restart):**

```powershell
# player id = the JWT `sub` seen in docs/capture.log
$id = "9b9d2c887e2524f918e383a895f2f1c2"
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:9210/api/progression/$id" `
  -ContentType "application/json" -Body '{"Level":85,"XP":0}'
Invoke-RestMethod -Uri "http://127.0.0.1:9210/api/progression/$id"   # read back
```

Wait ~60 s (the client's progression poll), confirm the menu level badge moved, then re-click BATTLE.

**ONE-BIT CRITERION:** the BATTLE tile latches *now* where it did not at Step 3.

- **Yes** → account level *is* the gate and it is backend-controllable. Item closed.
- **No, but the level badge visibly moved** → the level ingest works and the gate is **not** account level.
  `HYPOTHESIS` worth exactly one more test: `GetLevelGameFeatureUnlocked` sits in the same reflection
  cluster as `GetFeatureTogglesReady` / `IsGameFeatureUnlockedForLevel` / `GetFeatureToggleValue`
  (`.rdata` 0x08970D98-0x08971190, `MEASURED` adjacency only) — i.e. the gate may be the **game-feature-toggle**
  system, which S88/S89 characterised as a wall. **If so, say so and stop** — that is a different
  subsystem with its own record, and it would mean the BATTLE blocker is neither QoS nor account level.
- **The level badge did not move** → the admin write didn't land; fix that before concluding anything.

**Revert** the level to its prior value if it perturbs PASSES.

---

### Step 5 — ★ Serve the real `FRegionHostList`. The untried lever. — 10 min

**Proposed diff — replace `handleCoreGameRegions`, `interactive.go:718-732` (DO NOT APPLY):**

```go
// FK-5 probe step 5 (2026-07-27). The prior body matched the target struct in exactly ONE
// field (Port). Ground truth from schema.txt:
//   FRegionHostList{ Regions: TArray<FRegionHost>, ETag: FString }        (43179)
//   FRegionHost    { Name, Addr, Port, CanExclude, Routes: TMap<...> }    (43173)
//   FRegionRoute   { Enabled, IsAccelerator, Host, Port, PingHost,
//                    PingPort, RequiresToken }                            (43182)
// The usmap calls Regions ArrayProperty<StrProperty>; it told the SAME lie about
// QueueInfo.Queues, which the live client corrected to a STRUCT array. If the usmap is right
// this time, Loki.log will say `ImportText (Regions): Missing opening parenthesis` and name
// its own fix. Without a Routes map the client creates ZERO ULatencyMeasurers, which is why
// "Creating new latency measurer" has never appeared in any log.
func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
	route := map[string]any{
		"Enabled":       true,
		"IsAccelerator": false,
		"Host":          "127.0.0.1",
		"Port":          7777,
		"PingHost":      "127.0.0.1",
		"PingPort":      7777,
		"RequiresToken": false,
	}
	region := map[string]any{
		"Name":       "na",
		"Addr":       "127.0.0.1",
		"Port":       7777,
		"CanExclude": false,
		"Routes":     map[string]any{"default": route},
	}
	writeJSON(w, map[string]any{
		"Regions": []any{region},
		"ETag":    "revival-regions-v2",
	})
}
```

**Do:** apply, rebuild+restart (§2), wait 60 s (or leave PLAY and come back to force `RefreshRegionsHandle`).

**Run:** FK5-A first, then FK5-D, then FK5-F.

**ONE-BIT CRITERION:** does `Loki.log` now contain **`Creating new latency measurer for`** — a string that
has **never** appeared in 7 archived logs?

| Outcome | Reading | Next |
|---|---|---|
| **5a.** measurer line appears | ★ The region model was the blocker. §0.3/§0.4 confirmed. | → Step 6 |
| **5b.** FK5-D prints `ImportText (Regions): Missing opening parenthesis` | The usmap was right — `Regions` really is `TArray<FString>`. Serve region-id **strings** and find where the host/route detail lives (likely a second endpoint). | Re-run Step 5 with strings |
| **5c.** FK5-D prints `Deserialization failure ... /core-game/regions` | A matched key has the wrong type. Most likely `Routes` (map vs array) or `Port` (string vs int). Change **one** key and repeat. | iterate |
| **5d.** Nothing at all changes | The body is accepted and still yields no measurer ⇒ either the ingest is gated elsewhere, or `/core-game/regions` is not the feed. **Revert and stop guessing** — go read `CoreGameManager.ValidRegions` live with `tools/usmapdump/usmapdump.exe peek`. | RE, not probing |

**Not a failure criterion:** FK5-F may still print the `ST_ServerLocations` warning if `"na"` is not a key
in that string table. That is a **display-name** miss only. (Optional 2-min offline pre-work to get the
real keys: `extractor dump` on
`/Game/Loki/UI/Widgets/FrontEnd/MainMenu/Party/Latency/ST_ServerLocations`.)

---

### Step 6 — Serve `Party.State` — 5 min

**Ordering is a hard constraint:** run this **after** Step 5. If no measurer exists, `SetLatencies` is
never called, so the party-state guard cannot print and this step is **unobservable**. (This is why the
brief's "batch what you can" answer is "not these two, in this order" — see §6.)

**Proposed diff — `buildSoloParty` return map, `interactive.go:1190-1219` (DO NOT APPLY):**

```go
	// FK-5 probe step 6 / closes S61's open item. FParty.State (schema.txt:39849) is the
	// FString at struct +0x18 that S61 disassembled as TryStartSoloMode's GATE 2
	// (accepts "default" | "Matchmaking", case-insensitive wide compare) and left as
	// "key not yet mapped" — satisfied by a live memory poke ever since. The 8-field
	// offset table matches S61's live observations 8/8, including Version==1 at +0x10,
	// which was our own pinned value at the time. EPartyState = {Default, Matchmaking,
	// CustomGame, Unknown}. Also gates UPartyManager::SetLatencies
	// ("skipping set latencies, party state: %s").
	"state": "default",
	// FParty.ClientVersion (+0x28) — the client sends this build id as a header on every
	// request; PartyManager.cpp carries "Client version not valid, leaving matchmaking".
	"clientVersion": "release2.4.live-156430-shipping",
```

⚠ Two keys is two variables. If you want strict single-variable discipline, add `"state"` alone first;
`clientVersion` only matters once matchmaking actually starts (§5.2 / Step 3 outcome 1b).

**Do:** apply, rebuild+restart (§2), wait 60 s.

**Run:** FK5-B, FK5-A, FK5-H.

**ONE-BIT CRITERION:** does `POST /party/parties/party-<id>/latencies` appear in FK5-H?

- **Yes** → the chain is complete. Capture the **body** from `capture.log` — it is the ground truth for
  `FMemberLatencies` and confirms/corrects `MemberLatencies.Latencies` being
  `TArray<FMemberServerLatency>` rather than the usmap's `TArray<FString>`.
- **No, and FK5-A now prints `skipping set latencies, party state: %s`** → read the printed value. If it
  is empty, `"state"` didn't land (wrong key or wrong nesting). If it prints `default`, then `default` is
  not an accepted state for *this* call and `Matchmaking` is the next single variable.
- **No, and FK5-A prints `no changes over set threshold`** → the thresholds bite. `HYPOTHESIS`: add
  `"minLatencyDifference":"0"` / `"minRouteLatencyDifference":"0"` to the client-config body
  served by `handleClientConfig` in `server/internal/loki/loki.go` (the `writeJSON` map that already
  carries `serviceHostnames` / `clientVersions` / `featureToggles`) — unmatched keys are free, so this is
  a safe superset probe. Note `ClientConfiguration` has only 12 reflected props (`schema.txt:11158`) and
  none is named for a threshold, so these most likely ride `VendorConfigs` / `CohortConfigs` (both
  `MapProperty`); if a flat key does nothing, try nesting under those.
- **No, and FK5-A prints `no valid party` / `player not in party`** → the party doc is not being adopted
  at all. Check `partyVersion` is still strictly advancing (`store.partyVersion()`).

---

### Step 7 — Ping transport (ICMP vs UDP echo) — 10 min. **Only reachable from 5a.**

This is the **first** step at which any "responder" question is even well-posed.

**Do:** with measurers alive, watch for `setting new latency, Host: ... current: %f` (FK5-A).

**ONE-BIT CRITERION:** does a latency **value** ever get set?

- **A value appears** → transport is ICMP-to-loopback (or the UDP echo is being answered by something).
  **No responder is needed. FK-5 is fully retired.**
- **Measurers exist but no value ever prints** → the ping is unanswered. Now, and only now, decide the
  transport. Cheap discriminator, no code: run
  `netstat -anb | Select-String "UDP.*7777"` while the game is at the menu, and/or point `PingPort` at a
  port you can watch. If UDP datagrams arrive at `PingPort`, write a ~30-line UDP echo (reflect the
  received bytes back to the sender) and re-run.
  **Record this outcome as "a UDP echo responder is required", NOT as "FK-5 was right"** — the belief
  under test was *"the blocker is an AccelByte QoS UDP ping responder"*, and by this point four upstream
  blockers would already have been the actual gate.

---

## 5. Conditional side-quests (do not run unless a step points at them)

- **5.1 `POST .../latencies` handler.** Not needed for detection (catch-all logs it and returns 200 `{}`).
  Add one only if the **failure** callback (`fn 0x585D230`, `"Failed to set latencies, status: %d, …"`)
  fires — that means 200 `{}` is not a valid success body. Echo the party doc, as `startSoloMode` does.
- **5.2 `Client version not valid, leaving matchmaking`.** If FK5-E prints it, `Party.ClientVersion`
  (Step 6's second key) is the single variable.
- **5.3 `POST .../joinQueue` / `.../leaveQueue` / `.../setTargetQueues`.** `MEASURED`: all three exist as
  `PartyManager.cpp` suffixes and **none is served**. They will self-report through the catch-all the
  moment BATTLE actually starts matchmaking. Do not pre-implement them — let them appear first.
- **5.4 `-LogCmds`.** If Steps 5-7 go dark, FK-11 says the cheapest instrument is unexercised:
  `-LogCmds="LogLatencyManager VeryVerbose, LogPartyManager VeryVerbose"`, or append a `[Core.Log]` block
  to `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini` (`MEASURED`: the shipped
  `DefaultEngine.ini` already carries a `[Core.Log]` block at line 790, and the launcher already proves
  that user ini is honoured). This is a **separate variable** — do not fold it into a content step.

---

## 6. Time budget and what may safely be batched

| Step | Change | Restart? | Time |
|---|---|---|---|
| 0 Baseline + null controls | none | launch | 6 min |
| 1 **Click BATTLE / PRACTICE** | none | no | 10 min |
| 2 Null control restart | none | yes | 3 min |
| 3 Restore 10 queue ids | 1 var | yes | 8 min |
| 4 Account level (conditional) | 1 var | **no** | 5 min |
| 5 **Real `FRegionHostList`** | 1 var | yes | 10 min |
| 6 `Party.State` | 1 var | yes | 5 min |
| 7 Ping transport (conditional) | 0-1 var | maybe | 10 min |
| | | **total** | **~55-60 min**, ~75 with slack |

**Safe to batch:**
- **Step 3 + Step 4.** Disjoint mechanisms (queue-id list vs account level) and Step 4 needs no restart, so
  you can do 3, observe, then 4 without a rebuild. Sequential, not simultaneous.
- **Step 5 + Step 6** *would* be safe on the general principle that their proximal observables are disjoint
  (`Creating new latency measurer` from `LogLatencyManager` vs `skipping set latencies, …` from
  `LogPartyManager`) — **except** that Step 6's observable is unreachable until Step 5 succeeds. Batching
  them therefore buys one restart (~2 min) and costs the ability to attribute a Step-5 failure. **Don't.**

**Never batch:**
- Step 1 with anything. It is the verdict step and its value is entirely in being unperturbed.
- Step 5 with Step 3. Both change what the PLAY menu does; a tile that suddenly works would be
  unattributable.
- Any content step with `-LogCmds` (§5.4). Changing the instrument and the subject at once is how FK-4
  survived for 60 sessions.

---

## 7. What each terminal outcome means for FK-5 (write this into the record, verbatim)

| Terminal outcome | Verdict to record |
|---|---|
| Step 1 = 1a/1b, and Steps 3-6 reach `POST /latencies` | **FK-5 FALSE.** The blocker was a degraded queue list and a wrong `/core-game/regions` model — both pure backend. No QoS responder was ever required. |
| Step 5 = 5a, Step 7 = a latency value appears | **FK-5 FALSE, strongest form.** The full latency loop runs against loopback with zero responder code. |
| Step 5 = 5a, Step 7 = pings unanswered, UDP datagrams observed on `PingPort` | **FK-5 PARTIALLY TRUE, and mis-scoped.** A **UDP echo** responder is needed — but it is the *fifth* blocker, not the first, and it is ~30 lines, not an AccelByte protocol. |
| Step 1 = 1c | **FK-5's premise stands and §0.3 is wrong.** Whichever `skipping set latencies` guard printed is the real gate. |
| Step 4 = level moves but tile stays locked | **A different subsystem owns the gate** (candidate: game-feature toggles, S88/S89). FK-5 is false *and* the audit's replacement fix is also false. Record both. |
| Step 5 = 5d (revert, nothing changes) | **Unresolved.** Record as UNKNOWN with the live-RPM follow-up named. Do **not** record "QoS is not the blocker" as proven — record "the region-model hypothesis is falsified, the blocker is unlocated." |

**Anti-pattern to avoid on write-up** (the exact failure that produced FK-5, and that FK-4 repeated hours
after its own retraction): do not compress "we did not observe X" into "X does not happen." Every negative
in this document is scoped to an instrument — `capture.log` sees **one** of the four network stacks in the
process, and `.text` in `merged.dump.exe` is only **52.29%** decrypted, so `refs=0` never means "unreferenced."
