# FK-5 settled: QoS is **not** the gate on BATTLE / PRACTICE

**Date:** 2026-07-27 · **Scope:** offline only (no game launched, no injection, `server/` unmodified)
**Method:** client Blueprint bytecode (`extractor bpdump`), usmap reflection schema (`schema.txt`),
`tools/strxref` over `dumps/merged.dump.exe`, capstone disasm of the merged dump, `git log`.

> Every claim below is tagged **[M] MEASURED** (read directly out of the client's own bytecode /
> reflection data / our own source) or **[I] INFERRED**. FK-5 exists because a hedged "A **or** B" was
> recorded as "A". This document tries hard not to make the mirror error.

---

## 0. Headline

**BATTLE and PRACTICE are blocked by two different things, and neither is QoS, latency, or regions.**

| Button | Queue id | Client path | What actually blocks it today |
|---|---|---|---|
| **BATTLE** (Breach) | `default` | matchmaking (`TryJoinQueue` → `POST /party/parties/{id}/joinQueue`) | **`default` is not in the list we serve at `GET /party/matchmaking/info`**, so `IsQueueAvailable("default")` is false and the tile is `SetVisibility(Collapsed)` — *not even drawn*. **[M]** |
| **PRACTICE** | `practice` | **solo** (`TryStartSoloMode`) — same path the tutorial uses | **`Party.State` is never served.** `UPartyManager::TryStartSoloMode` GATE 2 requires the party's `State` string to be `"default"` or `"Matchmaking"`; ours is empty ⇒ bail before any HTTP. **[M]** |

Both fixes are **backend-only, single-field, and require no account level, no QoS responder, no shim.**

---

## 1. The PLAY-menu flow, reconstructed from the client's own bytecode

Assets (all in `tools/extractor/out/`, re-dumpable with
`extractor.exe bpdump "<asset>" "<UFunction>"`):

* `Comp_MainMenu_QueueController` (PlayerController component — owns every gate)
* `WBP_ActivityPickerScreen` (the PLAY modal)
* `WBP_UI_ActivityTile_Base` (each tile)
* `WBP_UI_PartyJoinLeaveQueue_CTA_V3` (the FIND MATCH / PLAY button)
* `BPFL_Matchmaking`, `DT_QueueDisplayDataTable`

```
menu idle
  └─ GET /party/matchmaking/info  → QueueInfo{Queues[],ETag,LastUpdated}
        → PartyModel.GetQueues()  = list of UQueueModel objects (ID, bIsRanked, MaxPartySize, Priority…)
  └─ GET /party/players/{id}, GET /party/parties/{id} → FParty → PartyModel

PLAY modal opens → WBP_ActivityPickerScreen.InitializeQueues()          [M]
   PresetQueues = { default deathmatch practice dropin customgame bots
                    tutorialNew training armorydeathmath tournament }
   for q in GetQueues():
       if PresetQueues.Contains(q.ID):  SKIP   ← preset tiles are hand-placed widget children
       if AddedQueues.Contains(q.ID):   SKIP
       else: create a generic WBP_UI_ActivityTile_Default_C, SetStringPropertyByName(tile,"QueueID",q.ID)
   (post-loop) ClientConfigManager.GetNextOrCurrentTimespanForAction("startCustomGame") → custom-game row

each tile ticks ExecuteUbergraph_WBP_UI_ActivityTile_Base                [M]
   [95..98] SetVisibility( QueueController.IsQueueAvailable(QueueID) ? shown : Collapsed )
   [89..92] IsQueueIDPremadeOrOverQueueLevel(QueueID, out CanQueue, out Reason, out UnlockLevel)
            → SetupManual(..., locked, ..., UnlockLevel, ...)      ← the padlock + "requires level N"
   [150..152] on CLICK: if !CanQueue → swallow the click
   [104..105] on CLICK: QueueController.TryAddQueue(QueueID, false)

TryAddQueue → ubergraph → CanControlQueue → PartyManager.TryAddTargetQueue(...,OnSelectQueueComplete)
   → POST /party/parties/{id}/setTargetQueues                        (NOT SERVED — falls to {} catch-all)

FIND MATCH / PLAY button (CTA_V3)                                       [M]
   Update Button Enable Status → SetCanControlQueue( CanControlQueue(out ReasonText), tooltip )
   click → QueueController.TryJoinSelectedQueue → ubergraph @662:
        [40] HasSelectedSpecialQueue?
             YES → PartyManager.TryStartSoloMode(mode, HeroId, pos, OnStartSoloModeComplete)
                       → POST /party/parties/{id}/startSoloMode?mode=&hero=&soloModeStartPosition=
             NO  → PartyManager.TryJoinQueue(On Try Join Queue)
                       → POST /party/parties/{id}/joinQueue        (NOT SERVED)
```

### 1.1 The special/solo vs matchmaking split — **[M]**

`Comp_MainMenu_QueueController.IsSpecialQueueName` → native `UPartyManager::IsSpecialQueue`, impl
`fn 0x5854F5F` (1903 B, `.pdata`-exact). Disassembly shows a two-level ClientConfiguration lookup
`Config["queues"]["special"]`, and when that is absent it builds the **hardcoded default list**
(five `lea`s at +0x14C…+0x18C and again at +0x1C9…+0x209):

```
special (default) = { practice, customgame, dropin, tutorialNew, training }
```

⇒ **`practice`, `dropin`, `customgame`, `tutorialNew`, `training` take the SOLO path
(`TryStartSoloMode`). `default`, `deathmatch`, `bots`, `armorydeathmath`, `tournament`,
`domination`, `prismabank` take the MATCHMAKING path (`TryJoinQueue`).**

Note that `queues.special` is a **ClientConfiguration key we control** — we could move `default`
onto the solo path if we ever want to, though that is a different experiment.

### 1.2 Queue-id → tile mapping — **[M]**, from `catalog/dt/DT_QueueDisplayDataTable.json`

| queue id | tile art | tile in `WBP_ActivityPickerScreen` |
|---|---|---|
| **`default`** | `TX_UI_ActivityArt_Breach` | **`ActivityTile_Breach`** (Featured) = **BATTLE** |
| `deathmatch` | `TX_UI_ActivitArt_Arena` | `ActivityTile_Arena` |
| `armorydeathmath` | `TX_UI_ActivitArt_Arena` | (armory variant) |
| `domination` | `TX_UI_ActivityArt_Domination` | `ActivityTile_Domination` |
| `prismabank` | `TX_UI_ActivityArt_PrismaBank` | `ActivityTile_PrismaBank` |
| `tournament` | `TX_UI_ActivityArt_Tournament` | `ActivityTile_Tournament` |
| `dropin` | `TX_UI_Warmup1` | `ActivityTile_Warmup` |
| `customgame` | `TX_GroupHero2` | `ActivityTile_CustomGame` |
| `bots` | `TX_UI_TutorialGraphic_BotGame` | `ActivityTile_Bots` |
| `practice` | `TX_UI_Practice` | `ActivityTile_Practice` |
| `tutorial`, `internal1`, `holiday`, `duos-ranked`, `*-ranked` | — | — |

The **queue-id → art** column is **[M]** (straight out of the DataTable). The **art → tile-widget**
column is **[I]**, on name identity (`TX_UI_ActivityArt_Breach` ↔ `ActivityTile_Breach`); the tiles'
own `QueueID` instance overrides read back as "(no properties)" through CUE4Parse — the known
`index_catalog.go:194` / CDO-default serialization defect, not an absence.

**18 ids exist**, not 10. The "10" in the backend comment is only `InitializeQueues`' `PresetQueues`
set. `domination` and `prismabank` have tiles but are **absent from `PresetQueues`**, so if served
they would additionally get a duplicate generic tile — cosmetic, worth knowing.

---

## 2. `CanControlQueue` — the real gate list, in order — **[M]**

`bpdump_CanControlQueue.txt`, 202 bytecode entries. Full trace:

| # | Gate | Fails when | Our state |
|---|---|---|---|
| 1 | `CanSwitchQueue()` = `!ActionInProgress && IsPartyOwner()` | a previous action never completed, or the party owner ≠ me | `ActionInProgress` is a **latch**: `BeginAction` sets it, and only `EndAction` (called from `OnSelectQueueComplete` / `OnStartSoloModeComplete` / `On Try Join Queue` / `OnLeaveQueueComplete`) clears it. **A request whose callback never completes wedges every later click for the rest of the session.** ⚠ |
| 2 | `GetClientConfigManager().IsClientVersionValid()` | `ClientConfiguration.ClientVersions` doesn't contain the build | served (`loki.go`) — passes **[I]** |
| 3 | per **CURRENT** queue: `members.Num > q.MaxPartySize` | party bigger than the queue allows | we serve `MaxPartySize:3`, solo party = 1 → passes **[M]** |
| 4 | per **CURRENT** queue, **only if `q.bIsRanked`**: `GetScheduleForQueue(...)` window | ranked schedule closed | we serve `IsRanked:false` for all → **branch never entered** **[M]** |
| 5 | per **CURRENT** queue, **only if `q.bIsRanked` AND `!PartyModel.bIsRankedEligible`**: `GetLevelGameFeatureUnlocked(PrimaryAssetId(GameFeature,"Ranked"))` | account level below the ranked unlock | **branch never entered** (see #4) **[M]** |
| 6 | `Has Premade Restriction` → `party_size` / `rank_disparity` / `mmr_disparity` | member premade keys set | our members have none → passes **[M]** |
| 7 | `PartyManager.GetActiveRestrictionSchedules(...)` | a restriction window is live | none served → passes **[I]** |
| 8 | `IsPremadeOrOverQueueLevel()` → per CURRENT queue `IsQueueIDPremadeOrOverQueueLevel` | see §3 | passes for every id except `deathmatch`/`customgame`/`custom` **[M]** |
| — | else | | returns **true** |

### ★ 2.1 The S60 rationale for trimming the queue list is **FALSIFIED**

`server/internal/interactive/interactive.go:855-870` says:

> *"DIAGNOSTIC TRIM (S60): `Comp_MainMenu_QueueController.CanControlQueue` loops over the current
> queues calling `GetLevelGameFeatureUnlocked`; with the served account level = 0, any level-gated
> queue (tournament/deathmatch/ranked) fails that loop → `CanControlQueue` false → every activity
> click errors 'Unable to modify activity'."*

Three separate errors, each measurable from the bytecode:

1. **It loops `GetCurrentQueues()`, not `GetQueues()`.** `GetCurrentQueues` is the party's *selected*
   queues. An advertised-but-unselected queue is never examined. Adding ids to
   `/party/matchmaking/info` therefore **cannot** by itself fail `CanControlQueue`. **[M]**
2. **The `GetLevelGameFeatureUnlocked` call is guarded by `q.bIsRanked`.** Bytecode `[143]` is
   `EX_PopExecutionFlowIfNot(q.bIsRanked)` and `[181/182]` is
   `EX_PopExecutionFlowIfNot(!PartyModel.bIsRankedEligible)`. We serve `IsRanked:false` on every
   queue, so this branch is dead. **[M]**
   *Jump graph verified by statement offset, not by eye:* `[15] PushExecutionFlow(4898)` → `[136]`
   (`stmt 4907`, the loop increment) → `[138] Jump 165` (loop head); `[25] JumpIfNot → 4972` lands on
   `[139]` (`4967 + 5`); `[143]` (`stmt 5144`) pops back to `4898`; `[150]/[152] JumpIfNot → 6433`
   lands on `[179]` (`6428 + 5`); `[182]` (`stmt 6547`) is the last thing before `[183]`. So
   **`[144]`–`[196]` — the ranked schedule *and* the level check — are entirely inside the
   `q.bIsRanked == true` arm.**
3. **Its argument is hardcoded `PrimaryAssetId(GameFeature, "Ranked")`** — *not* a per-queue feature.
   So it never gated `tournament` or `deathmatch` in this function at all. **[M]**

**Consequence: restoring the queue ids does not require serving any account level.** The prescription
in `docs/coverage-audit-s101.md` Tier-1 §1.9 ("Serve a high `lastSeenAccountLevel`, restore the 10
ids") is over-specified; the account-level half is unnecessary. It is also *harmless*, but it is not
the variable — and bundling it would make the result ambiguous, which is exactly the failure mode
`CLAUDE.md` warns about.

Provenance of the trim: `git log -L` shows `queueIDs` entered the tree **already trimmed** in
`ccdb847` ("S59: update documentation and functionality for front-end systems", 2026-07-09). There is
no commit that shows 10 ids working and then being cut, and no log/doc anywhere in `docs/` records a
*measurement* of the trim helping. **[M]** The comment's own framing ("to test whether removing
gated queues clears the modify block. **If it does**, the real fix is…") is a hypothesis that was
apparently never falsified or confirmed — and it is now falsified statically.

---

## 3. The real level gate: `IsQueueIDPremadeOrOverQueueLevel` — **[M]**

```
key = "queue.restrictions." + QueueID
if ClientConfigManager.GetFeatureToggle(key) EXISTS:
        required = int( toggle.Config["Level"] )      // SelectInt default = 3 when the key is missing
        CanQueue = (PartyModel.GetSelf().AccountLevel >= required) OR (members.Num > 1)
elif QueueToGameFeature.Find(QueueID):                 // CDO map on Comp_MainMenu_QueueController_C
        CanQueue = PlayerHasGameFeature(feature) OR (members.Num > 1)
        UnlockLevel = GetLevelGameFeatureUnlocked(feature)
else:
        CanQueue = TRUE                                 // NO RESTRICTION
```

`bpdump_Comp_MainMenu_QueueController_PROPS.txt` — the CDO map has exactly **three** rows:

```
QueueToGameFeature (MapProperty):
   [0] deathmatch
   [1] customgame
   [2] custom
```

⇒ **`default`, `bots`, `dropin`, `practice`, `training`, `tutorialNew`, `armorydeathmath`,
`tournament`, `domination`, `prismabank` carry no level restriction whatsoever.** Only Arena
(`deathmatch`) and Custom Game are level-gated, and even those are overridable three ways: party
size > 1, a `PlayerHasGameFeature` unlock, or a `queue.restrictions.deathmatch` feature toggle in
**our own** `/configuration/client` payload (`ClientConfiguration.FeatureToggles` is a
`TMap<FString, FFeatureToggle{Config: TMap<FString,FString>}>`, already served by `loki.go`).

---

## 4. `IsQueueAvailable` — why the BATTLE tile is invisible — **[M]**

```
IsQueueAvailable(QueueID) -> bQueueAvailable:
    if IsValid(PartyModel.FindQueueByID(QueueID,false)): return TRUE
    if IsValid(PartyModel.FindQueueByID(QueueID,true )): return TRUE
    if IsSpecialQueueName_CustomGame(QueueID):
        return ClientConfigManager.GetNextOrCurrentTimespanForAction("startCustomGame", …)
    if IsSpecialQueueName(QueueID):
        return ClientConfigManager.GetNextOrCurrentTimespanForAction("startSoloMode", …)
    return FALSE
```

The **only** input for a non-special queue is "is this id in `PartyModel.GetQueues()`", i.e. in
`GET /party/matchmaking/info`. **[M]**

The tile then does `SetVisibility(SwitchValue(IsQueueAvailable(QueueID), …))` over the two byte
constants set immediately before it — `Temp_byte_Variable_4 = 4` and `Temp_byte_Variable_5 = 1`
(`ExecuteUbergraph_WBP_UI_ActivityTile_Base` `[93]…[98]`). **[M]** In `ESlateVisibility` those are
`SelfHitTestInvisible` (drawn) and `Collapsed` (not drawn). CUE4Parse does not print the
`FKismetSwitchCase` values, so **which** byte pairs with `true` is **[I]** — but a `K2Node_Select`
on a bool emits True-then-False, the same `4 / 1` pair is used at `[17]…[20]` for the unlock-level
label, and no ordering makes "unavailable ⇒ drawn" sensible.

⇒ an unserved non-special queue's tile is **collapsed, not "locked"**. `default` is unserved ⇒
**the BATTLE/Breach tile is not drawn at all right now.** That is a one-line backend fix.

(Corollary: the existing backend comment "A tile whose queue isn't in that set renders 'locked' — it
shows a hover highlight but a CLICK can't latch" is wrong about the symptom. **[M]**)

---

## 5. PRACTICE (and every solo mode): `Party.State` is the missing field — **★ the biggest find**

S61 (`docs/session-61-tutorial-match-setup.txt`) disassembled `UPartyManager::TryStartSoloMode`
(`rva 0x587A980`) live and fully decoded **GATE 2**:

> `FString1 @ PartyModel+0x558+0x18` must case-insensitively equal `"default"` (Num 8) or
> `"Matchmaking"` (Num 12), else `xor al,al` → bail with no HTTP. **LIVE it was EMPTY.**
> A memory poke of `"default"` made it proceed and `/startSoloMode` fired. The session recorded:
> *"DURABLE FIX: populate this field in the ags /party response … **Need the JSON field name**."*

**That field name is now recovered — statically, from the usmap reflection schema (`schema.txt:39866`):**

```
Party : (17 props)
    ID              StrProperty      // +0x00, FString = 0x10 bytes
    Version         Int64Property    // +0x10, 8 bytes
    State           StrProperty      // +0x18   ← EXACTLY the offset S61 poked
    ClientVersion   StrProperty
    IsOpen          BoolProperty
    FillTeam        EnumProperty
    OwnerID         StrProperty
    DiscordJoinSecret StrProperty
    Members         ArrayProperty
    TargetQueueIDs  ArrayProperty<StrProperty>
    ExcludedRegions ArrayProperty
    Requests        ArrayProperty
    CustomGameDetails Struct
    MillisInQueue   IntProperty
    QueueJoinTime   DateTime
    TargetQueueID   StrProperty
    IsRanked        BoolProperty
```

The offset arithmetic is exact: `ID`(0x10) + `Version`(0x08) = **0x18**. **[M]** (offsets), **[I]**
(that the poked field *is* `State` — but the match is exact on offset, type, and accepted values.)

The accepted values are the `EPartyState` enum names (`schema.txt:65623`):
`EPartyState::{Default=0, Matchmaking=1, CustomGame=2, Unknown=3}` — and `TryStartSoloMode` compares
against the strings `"default"` / `"Matchmaking"`. **[M]**

**⇒ `buildSoloParty` must emit `"state": "default"`.** We currently emit no `state` key at all
(`interactive.go:1188-1207`, verified by read). **[M]**

### 5.1 Two consumers of `State` you must not break

* `Comp_MainMenu_QueueController.IsInQueue()` reads `PartyModel.GetPartyState()` **[M]** — so
  `"Matchmaking"` makes the client believe it is *already queued* and flips PLAY → CANCEL. Serve
  `"default"` while idle; only move to `"Matchmaking"` when a real queue join is in flight.
* `HasSelectedSpecialQueue()` short-circuits to `true` when `GetPartyState() == 2` (CustomGame) **[M]**.

---

## 6. The region / latency subsystem: what it actually gates — **[M]**

This is where FK-5's "QoS is the blocker" came from, and the truth is both smaller and more concrete.

### 6.1 The one real region gate is a **15-second soft delay** on the PLAY button

`ExecuteUbergraph_WBP_UI_PartyJoinLeaveQueue_CTA_V3`, entries `[2]…[15]` and `[77]…[85]`:

```
[3]  pm = GetPartyManager()
[4]  if pm.GetInitialExcludedRegionsSet():
[6]      Button_Play.SetIsEnabled(TRUE)
     else:
[8]      Button_Play.SetIsEnabled(FALSE)
[9,10]   K2_SetTimerDelegate(OnMaxTimeForExcludedRegions, 15.0s, looping=false)
[12..15] bind OnExcludedRegions to PartyModel.OnExcludedRegionsUpdated
...
[77] OnMaxTimeForExcludedRegions:  Button_Play.SetIsEnabled(TRUE)     ← fires after 15 s regardless
[80] OnExcludedRegions:            Button_Play.SetIsEnabled(TRUE)
```

**The PLAY button is disabled for at most 15 seconds while waiting for excluded regions, then
enables itself unconditionally.** It is a startup delay, not a wall. **[M]** Any prior observation of
"the PLAY button is greyed out" taken inside the first 15 s of the menu is not evidence of a block.

### 6.2 `/core-game/regions` — we are serving the **wrong shape**, so the "PingHost" experiment was never actually run

Ground truth from `schema.txt`:

```
RegionHostList : (2 props)          ← the response envelope
    Regions   Array<RegionHost>
    ETag      Str
RegionHost : (5 props)
    Name      Str
    Addr      Str
    Port      Int
    CanExclude Bool
    Routes    Map<Str, RegionRoute>
RegionRoute : (7 props)
    Enabled Bool · IsAccelerator Bool · Host Str · Port Int
    PingHost Str · PingPort Int · RequiresToken Bool
```

`handleCoreGameRegions` currently emits
`{"Regions":[{"RegionName","RouteName","DisplayName","Host","PingHost","Address","Port","Enabled"}]}`.
Of those, **only `Port` matches a real `RegionHost` UPROPERTY.** `Name`, `Addr`, `CanExclude` and
`Routes` are all absent ⇒ the client builds a nameless, address-less region with **zero routes**.
`ULatencyMeasurer` (`Host`, `Region`, `Route`, `Port`, `PingHost…`) is constructed per **route**, so
with no routes there is nothing to ping. **[M]**

> **★ This retires the FK-5 register's "⚠ TRAP — the obvious remedy is already spent".**
> The register says *"`/core-game/regions` **was** served with `PingHost: 127.0.0.1` and the client
> never pinged."* It never pinged because `PingHost` was placed as a **top-level key on `RegionHost`,
> where no such property exists** — the correct location is `Regions[i].Routes["<route>"].PingHost`.
> Per the project's own validity model, an unmatched key is silently ignored. **The experiment was
> malformed; its negative result carries no information.** **[M]**

### 6.3 `/latencies` is party member state, and it is optional

Confirmed from `.rdata` (PartyManager.cpp translation unit, `0x08B4B220`–`0x08B4B6B0`) and the
reflection schema:

```
MemberLatencies : (1 props)  Latencies : Array
PartyMember.Latencies : Array          ← latency lives ON THE PARTY MEMBER
guards: 'skipping set latencies, no valid party' / '…party state: %s' /
        '…player not in party' / '…no changes' / '…no changes over set threshold'
POST /party/parties/{id}/latencies  (string 0x08B4C378)
```

There is **no UDP responder anywhere in this chain.** The pings are ordinary
`ULatencyMeasurer` ICMP/host pings against `RegionRoute.PingHost:PingPort` (log string
`'Could not ping target host: %s:%d. Result: %d'`), and the *result* is uploaded over HTTPS as party
member state. **The AccelByte `QosManager` is not on this path** — consistent with FK-5's own
evidence (`QosManagerServerUrl=` empty in all 12 `DefaultEngine.ini` env sections; one call-site).

**[I]** The most likely purpose of the whole region/latency limb is (a) the menu's `??? — ms`
readout, (b) computing `ExcludedRegions` so matchmaking doesn't place you on a far server. Neither is
a hard precondition for *entering* a queue in any bytecode I can read. The one place it touches a
gate is §6.1, and that self-clears in 15 s.

---

## 7. Endpoints the BATTLE path needs that we do not serve — **[M]**

From the UTF-16 endpoint table in `.rdata` (`UPartyManager`), with resolved call sites where the page
is decrypted:

| Route | String RVA | Builder fn | Served? |
|---|---|---|---|
| `POST /party/parties/{id}/joinQueue` | `0x08B4C218` | `0x584C520` (501 B, exact) → caller `0x5875E90` = `UPartyManager::TryJoinQueue` | ❌ `{}` catch-all |
| `POST /party/parties/{id}/setTargetQueues` | `0x08B4C328` | page undecrypted | ❌ |
| `POST /party/parties/{id}/leaveQueue` | `0x08B4C3A8` | — | ❌ |
| `POST /party/parties/{id}/setExcludedRegions` | `0x08B4C350` | `0x5868270` (1044 B, exact) | ❌ |
| `POST /party/parties/{id}/latencies` | `0x08B4C378` | page undecrypted | ❌ |
| `POST /party/parties/{id}/refreshRanks` / `refreshLevel` / `refreshMastery` / `refreshXPBoosts` / `refreshRankedEligibility` | `0x08B4C268…0x08B4C300` | — | ❌ |

**Diagnostic worth recording:** `UPartyManager::TryJoinQueue`'s entry (`0x5875E90`) sits in page
`0x5875000`, which is **100 % zero in `dumps/merged.dump.exe`** — i.e. across every game state we
have ever dumped, **that function has never executed**. BATTLE has literally never been clicked in a
captured session. `/setTargetQueues` and `/latencies` likewise have 0 resolved xrefs. **[M]**
This is a strong, independent argument that "QoS blocks BATTLE" was never an observation — there is
no run in which the client got far enough to want QoS.

---

## 8. Ranked list of candidate gates

| # | Candidate gate | Evidence | Confidence | Cost to clear |
|---|---|---|---|---|
| **1** | **`default` absent from `/party/matchmaking/info`** ⇒ BATTLE tile collapsed | `IsQueueAvailable` bytecode + our own `queueIDs` list | **MEASURED, near-certain** | one line |
| **2** | **`Party.State` never served** ⇒ `TryStartSoloMode` GATE 2 bails ⇒ PRACTICE / every solo mode dead | S61 live disasm + `schema.txt` `Party.State @ +0x18` | **MEASURED (offset+type exact); [I] on the name** | one line |
| **3** | `POST /joinQueue` unhandled (`{}` catch-all) ⇒ after BATTLE is visible+clickable, the join has no server | `.rdata` route table; 0 handlers in `server/` | **MEASURED that it's unserved; [I] that it's the next wall** | new handler, shape unknown |
| **4** | `ActionInProgress` latch wedges all further clicks when a callback never completes | `BeginAction`/`EndAction`/`CanSwitchQueue` bytecode | **MEASURED mechanism; [I] that it fires today** | make every party write return a well-formed body |
| **5** | `/core-game/regions` served in the wrong shape ⇒ 0 routes ⇒ no ping, no ExcludedRegions ⇒ 15 s PLAY-button delay + `??? — ms` | `RegionHostList`/`RegionHost`/`RegionRoute` schema vs our handler | **MEASURED** | rewrite one handler; **soft gate only** |
| 6 | `deathmatch` / `customgame` level restriction via `QueueToGameFeature` | CDO map (3 rows) | MEASURED | `queue.restrictions.<id>` toggle, or party>1, or account level |
| 7 | `IsClientVersionValid()` false | `CanControlQueue` gate 2; `loki.go` already serves `clientVersions` | [I] passes | — |
| 8 | AccelByte **QoS UDP responder** | one call-site; `QosManagerServerUrl` empty ×12; not referenced anywhere in the party/latency chain | **[I] NOT a gate** | — |

---

## 9. The live probe — designed to be decisive, **single-variable**

Do **not** bundle. Run in this order; each step has a one-bit read.

### Probe A (first) — "is the BATTLE tile's only gate the queue list?"

**Change (one variable):** `server/internal/interactive/interactive.go`, `queueIDs` →

```go
var queueIDs = []string{
    "default", "deathmatch", "practice", "dropin", "customgame",
    "bots", "tutorialNew", "training", "armorydeathmath", "tournament",
}
```

Nothing else. **Do not** touch account level, regions, or feature toggles.

**Read (one bit):** open PLAY → BATTLE. **Is the Breach tile drawn?**
* **Drawn** ⇒ candidate #1 confirmed; the level-gate hypothesis is dead; proceed to Probe B.
* **Not drawn** ⇒ my reading of `IsQueueAvailable` or of `Queues[]` deserialization is wrong.
  Check `Loki.log` for `Deserialization failure on … /party/matchmaking/info` first — a wrong-typed
  matched key rejects the *whole* document and would empty `GetQueues()`.

**Also read, free:** whether Arena / Custom Game show a padlock + "requires level N" (that is #6
firing, and it is expected and correct).

### Probe B — "what does the client ask for next?"

Click the Breach tile, then FIND MATCH. Watch `docs/capture.log` **in order**:

| First unserved request seen | Verdict |
|---|---|
| `POST …/setTargetQueues` | selection is the wall — implement it; response shape almost certainly `Party` |
| `POST …/joinQueue` | **the tile+selection layer is solved**; matchmaking session allocation is the frontier |
| `POST …/latencies` or `…/setExcludedRegions` | latency *is* on the critical path after all — re-open §6 with the corrected `RegionHost.Routes` shape |
| *nothing at all* | a client-side gate bailed before HTTP. `Loki.log` + `CanControlQueue`'s tooltip text on the PLAY button names which one (each gate in §2 writes a distinct `ReasonText`). |

**This is the measurement FK-5 asks for**: *"If it stalls before any QoS/latency call, QoS was never
the first blocker."* Given §7 (the `TryJoinQueue` page has never executed), I expect `joinQueue` or
`setTargetQueues`, and **no** latency call.

### Probe C (independent, can run the same session) — PRACTICE / solo

**Change (one variable):** add `"state": "default"` to `buildSoloParty`'s returned map.

**Read (one bit):** click PRACTICE → PLAY. Does
`POST /party/parties/{id}/startSoloMode?mode=practice&…` appear in `capture.log` **without any
memory poke**?
* **Yes** ⇒ S61's open "durable fix" is closed, and the entire solo family (practice, dropin,
  customgame, tutorialNew, training) becomes reachable from the real menu — which is also the
  cleanest possible input to the tutorial route.
* **No** ⇒ the field name is wrong; next candidates are `partyState` / `matchmakingState`, and a live
  RPM read of `PartyModel+0x558+0x18` after a `/party` poll tells you immediately.

### Hygiene for all probes

* Watch for the **`ActionInProgress` latch** (§2 #1). If the first click works and every subsequent
  click reports "Unable to modify activity", that is the latch, not a new gate. Reopening the PLAY
  modal will not clear it; only a completing callback or a relaunch will.
* Ignore the PLAY button being greyed out for the **first 15 s** after the menu loads (§6.1).
* `capture.log` should be rotated before the run so the ordering read in Probe B is clean.

---

## 10. Proposed backend diffs (NOT applied — `server/` untouched by this pass)

### 10.1 `server/internal/interactive/interactive.go` — restore the queue list

Replace the trimmed `queueIDs` (line ~867) and **replace the falsified comment**:

```go
// queueIDs is the set of matchmaking queue ids advertised at GET /party/matchmaking/info.
// This list is the ONLY input to Comp_MainMenu_QueueController.IsQueueAvailable for a
// non-special queue, and WBP_UI_ActivityTile_Base does SetVisibility(available ? shown :
// Collapsed) — so an id missing here means the tile is not drawn at all.
//
// The S60 "DIAGNOSTIC TRIM" rationale that used to live here is FALSIFIED (2026-07-27,
// docs/fk5-battle-practice-gate-s105.md): CanControlQueue loops GetCurrentQueues() (the
// party's SELECTED queues), not GetQueues(), and its GetLevelGameFeatureUnlocked call is
// guarded by q.bIsRanked (we serve IsRanked:false everywhere) with a hardcoded
// PrimaryAssetId(GameFeature,"Ranked") argument. Advertising ids here cannot fail it, and
// no account level is required.
//
// Level restrictions live in IsQueueIDPremadeOrOverQueueLevel and apply ONLY to the three
// rows of the Comp_MainMenu_QueueController_C CDO map QueueToGameFeature:
// {deathmatch, customgame, custom}. Overridable via the ClientConfiguration feature toggle
// "queue.restrictions.<id>" -> Config["Level"].
//
// Full id vocabulary from DT_QueueDisplayDataTable (18): the 10 below plus
// domination, prismabank, holiday, internal1, tutorial, duos-ranked, *-ranked.
// domination/prismabank are NOT in InitializeQueues' PresetQueues, so serving them would
// ALSO create a duplicate generic tile — left out deliberately.
var queueIDs = []string{
	"default", "deathmatch", "practice", "dropin", "customgame",
	"bots", "tutorialNew", "training", "armorydeathmath", "tournament",
}
```

**Risk:** low. Worst case is a deserialization failure on the whole `QueueInfo` doc, which empties
`GetQueues()` and reverts to today's behaviour — visible immediately in `Loki.log`. Reversible.

### 10.2 `server/internal/interactive/interactive.go` — `buildSoloParty`: serve `Party.State`

```go
	return map[string]any{
		"partyId": "party-" + id,
		"id":      "party-" + id,
		// FParty.State (usmap Party, StrProperty @ +0x18 — ID(0x10)+Version(0x08)).
		// LOAD-BEARING for every SOLO mode: UPartyManager::TryStartSoloMode
		// (base+0x587A980) GATE 2 case-insensitively compares this string against
		// "default" (Num 8) / "Matchmaking" (Num 12) and returns false with no HTTP
		// otherwise. S61 proved it live with a memory poke; this is the durable fix.
		// Values are EPartyState names {Default, Matchmaking, CustomGame, Unknown}.
		// ⚠ Do NOT serve "Matchmaking" at idle: IsInQueue() reads GetPartyState() and
		// the PLAY button would flip to CANCEL.
		"state": "default",
		...
	}
```

**Risk:** low, and it is a *matched* key of the correct type (Str), so it cannot trip the
"Deserialization failure" class. Reversible.

### 10.3 `server/internal/interactive/interactive.go` — `handleCoreGameRegions`: correct shape

Only after Probes A–C, and only if latency turns out to matter:

```go
func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
	// usmap RegionHostList{ Regions []RegionHost, ETag string };
	// RegionHost{ Name, Addr, Port, CanExclude, Routes map[string]RegionRoute };
	// RegionRoute{ Enabled, IsAccelerator, Host, Port, PingHost, PingPort, RequiresToken }.
	// The pre-2026-07-27 body used RegionName/RouteName/PingHost as TOP-LEVEL keys, none of
	// which are RegionHost UPROPERTIES — so the client built a region with ZERO routes and
	// had nothing to ping. That is why "we served PingHost and it never pinged".
	writeJSON(w, map[string]any{
		"Regions": []any{map[string]any{
			"Name": "na", "Addr": "127.0.0.1", "Port": 7777, "CanExclude": false,
			"Routes": map[string]any{
				"default": map[string]any{
					"Enabled": true, "IsAccelerator": false,
					"Host": "127.0.0.1", "Port": 7777,
					"PingHost": "127.0.0.1", "PingPort": 7777,
					"RequiresToken": false,
				},
			},
		}},
		"ETag": "revival-regions-v2",
	})
}
```

**Risk:** medium — `Routes` is a MapProperty of a struct; a wrong container shape trips
"Deserialization failure" on `/core-game/regions`. That is a contained failure (regions only), but
it *is* the shape most likely to be wrong, so run it alone.

### 10.4 Not proposed

* **No account-level change.** It is not required by any measured gate (§2.1, §3) and would make
  Probe A ambiguous.
* **No QoS UDP responder.** Nothing in the measured path asks for one.
* **No `/joinQueue` handler yet** — its request/response shapes are unknown and its code page has
  never executed, so guessing now would be a bundled change. Probe B is what names it.

---

## 11. What I could NOT determine offline

* **`UPartyManager::TryJoinQueue`'s own preconditions.** Its entry page (`0x5875000`) is 100 % zero
  in the merged dump — never executed, never demand-decrypted. There may be gates inside it that no
  static pass can see. **This is the single largest residual unknown**, and it is exactly what
  Probe B resolves. (After one BATTLE click the page commits and becomes disassemblable — worth a
  `dumpimage` from that state.)
* **`/joinQueue` and `/setTargetQueues` request/response models.** Not recoverable from the usmap by
  name alone; needs a live capture.
* **Whether `IsClientVersionValid()` currently passes.** Inferred from `loki.go` serving
  `clientVersions`, not observed.
* **Whether `ActionInProgress` is latched in practice.** Mechanism is measured; occurrence is not.
* **The exact `Latencies` element struct** (`PartyMember.Latencies`) — the usmap gives
  `Array<Str>`, which is the known container-type defect; the log format
  `Host: %s, Region: %s, Route: %s, current: %f` implies a 4-field struct. **[I]**

---

## 12. Verdict on FK-5

**FK-5 is upheld and then some.** "BATTLE/PRACTICE need an AccelByte QoS UDP ping responder" is not
merely weakly-supported — it is *pointing at a different subsystem than the one that is broken*, and
the two things that ARE broken are both one-line backend omissions that have been sitting in
`interactive.go` for 18 days and ~45 sessions.

The register's own **⚠ TRAP** note also needs retracting: the `PingHost: 127.0.0.1` experiment was
malformed (wrong nesting level, §6.2), so "the obvious remedy is already spent" is false. The remedy
was never correctly attempted. That said — §6.1 shows the region limb gates only a 15-second
button delay, so it should stay *below* the queue-list and `Party.State` fixes in priority, which is
where §8 puts it.

**Tools/artifacts produced by this pass** (all under `docs/` and scratch, `server/` untouched):
this document; 20 new `bpdump_*.txt` files in `tools/extractor/out/`
(`IsQueueAvailable`, `IsPremadeOrOverQueueLevel`, `IsQueueIDPremadeOrOverQueueLevel`, `IsPartyOwner`,
`Has Premade Restriction`, `GetQueueModel`, `CanSelectRanked`, `BeginAction`, `EndAction`,
`IsInQueue`, `OnSelectQueueComplete`, `On Try Join Queue`, `Update Play Button Enable Status`,
`Update Button Enable Status`, `RefreshVisibleButtons`, `OnExcludedRegions`,
`OnMaxTimeForExcludedRegions`, `UpdateButtonText`, `UpdateQueues`,
`Comp_MainMenu_QueueController_PROPS`, `WBP_ActivityPickerScreen_PROPS`,
`BPFL_Matchmaking_ALL` + `Queue ID to Name` / `GetGameModeDataForQueue` / `GetBotQueueID` /
`Get Custom Game Queue ID`).
