# S122 — the unserved-endpoint sweep, and the CAREER badge (2026-08-15)

Status: **SHIPPED AND CONFIRMED LIVE, in both directions, with the version gate isolated.**
Backend-only — no shim, no injection, no `.text` write. **Zero launches spent**: all five arms were
flown on one continuously-running client (uptime 1h41m at the end).

Claims are labelled **[M]** measured / **[I]** inferred / **[S]** speculative.

---

## 1. The method — invert S121's toggle probe

S121's biggest result was that a feature toggle is a probe for hidden **backend** surface: flipping
`leaderboards` made the client call three endpoints it had never been observed to call. That works,
but it is a search — one key at a time, each needing a config change and a wait.

S122 inverted it. **Parse the whole conversation the client has already had with us, and diff it
against the mux's registered routes.** That enumerates every endpoint the client wants and we do not
answer, in one pass, offline, for free.

Tools shipped: `tools/re/endpoint_surface.py` (parse `capture.log` into distinct client routes) and
`tools/re/unserved_routes.py` (diff against the Go mux, honouring `{x}` / `{x...}` patterns).

### [M] The result: 56 client routes, 8 unserved

    147  POST /party/parties/{party}/members/{id}/latencies     <- upload, no surface
    145  GET  /party/players/{id}/voice                         <- Vivox token; service externally dead
     73  POST /game-telemetry/v1/protected/events               <- upload, no surface
      1  POST /discord-api/account/token
      1  GET  /referral/player/{id}
      1  GET  /referral/player/{id}/points
      1  GET  /mmr/player-ratings/{id}/rank                     <- ★ this one
      1  POST /party/parties/{party}/members/{id}/refreshLevel

Three of the eight are client→server uploads with nothing to render. `referral` (2 routes) is the
other one with real UI behind it and is **still open**.

### ⚠⚠ The User-Agent filter was load-bearing, not hygiene

[M] Of 24,767 request records, **23,050 were not the game** — 23,047 from our own
`supervive-loadout-shim`. Unfiltered, every count above would have been garbage. The game is
`Loki/UE5-CL-0`. `endpoint_surface.py` prints the rejected count and its UA breakdown so the filter
is visible rather than silent.

### ⚠ A poll that looked pathological and was not

`GET /storefront/battlepass/progressiontracks` shows **730** calls — 5× any other endpoint. Dividing
total by elapsed gives "a 6 s poll", which reads as a defect. [M] The actual shape is a **~728-call
burst over 54 s at menu init**, then 2 calls in the following hour. Not a leak.
⇒ **Never infer cadence from a total; look at the timestamps.**

---

## 2. Why this endpoint — the consumer was measured, not assumed

Full-corpus census over the extracted assets (⚠ **FILE counts, not occurrence counts**):

| symbol | assets |
|---|---|
| `HasRankedRewardsToClaim` | **2** — `WBP_UI_MainMenu_NormalMainMenu`, `WBP_ProfileScreen` |
| `QueueRankRating` / `GetRankFromScore` / `GetPointsPerRank` | **9** — RankedScreen, RankedProgress, RankedToggle, RankedBadgeToggle, RankedScreenBadge, RankedInfoPopup, ProgressionTracker_RankedV2, ActivityTile_Base, EoG_RankMedal |

★★★ And the main menu's own bytecode says exactly what the boolean drives
(`bpdump_ExecuteUbergraph_WBP_UI_MainMenu_NormalMainMenu.txt`, statements 156–158):

    [156] CallFunc_HasRankedRewardsToClaim_ReturnValue = GetMMRManager()->HasRankedRewardsToClaim()
    [157] NavButtonFlyout_Career->ShowBadge(false, CallFunc_HasRankedRewardsToClaim_ReturnValue, …)
    [158] NavButtonMain_Career  ->ShowBadge(false, CallFunc_HasRankedRewardsToClaim_ReturnValue, …)

⇒ ONE boolean, sourced only from this endpoint, drives the notification badge on **both** CAREER nav
buttons — on the **main menu**, which is always built, so it needs no navigation to observe. And it
is an **ubergraph local**, so it is directly readable by RPM.

**That is the whole reason this target was picked over the other seven: it comes with its own
readout.** A surface you cannot observe is a surface you cannot test.

---

## 3. The model [M] — UHT oracle, not guessed

    FPlayerRank       ID FString · Version int32
                      QueueRankRating TMap<FString, FQueueRankRating>
                      RewardsToClaim  TMap<FString, FRankedReward>
    FQueueRankRating  Rating int32 · Rank ERank · Cost int32 · Updates TArray<FMatchRankedRating>
    FRankedReward     ID FString · Entitlement FPrimaryAssetId

- ⚠ Both containers are `TMap` → JSON **objects**, not arrays (the S120 `UnclaimedRewards` failure).
- ⚠ `Version` is **int32** — Unix seconds, not a millisecond timestamp.
- ⚠ `Rank` is an **ERank enum string**; `"Gold1"` reused because it is the one value this project has
  measured the client to accept (S121). A wrong enum sinks the whole struct.
- ⚠ `Entitlement` is an `FPrimaryAssetId` and is **omitted**. Omitting is always safe; an
  unresolvable id is the missions `InternalName` failure.

---

## 4. ★★★★★ The result — five arms, one live client, no relaunch

Readouts: the ubergraph local via RPM, and the badge's own
`WBP_MainMenu_Badge_C.Visibility` (ESlateVisibility: **1 = Collapsed**, **4 = SelfHitTestInvisible**,
i.e. rendered), with the three sibling nav buttons as a spatial control.

| arm | `RewardsToClaim` | `Version` | bool | has-run | CAREER badge | Hunters/Store/Armory |
|---|---|---|---|---|---|---|
| A baseline | unserved (`{}` catch-all) | — | False | 61 | — | — |
| **B** | non-empty | 1786847998 | **True** | **62** | **4 = RENDERED** | all 1 = Collapsed |
| B′ | `{}` | 0 | True | 62 | 4 | all 1 | ← **no reversal** |
| **C** | empty | 1786848659 | **False** | **61** | **1 = Collapsed** | all 1 |
| **D** | **non-empty** | **1** | **False** | **61** | **1 = Collapsed** | all 1 |
| B-repeat | non-empty | 1786848930 | **True** | **62** | **4 = RENDERED** | all 1 |

### Two clean single-variable pairs

- **B vs C** — only the reward map differs (both documents valid, version advancing); outcome
  inverts ⇒ **`RewardsToClaim` drives the badge. [M]**
- **B vs D** — only `Version` differs (identical non-empty reward map); outcome inverts ⇒
  **`FPlayerRank` is behind a MONOTONIC VERSION GATE. [M]**

### The controls that make it hold up

- ★ The has-run counter moved **61 → 62 → 61 → 61 → 62** in lockstep with that one boolean —
  exactly one local changing non-default state. Hard to obtain by accident.
- ★ Only the **live** instance ever moved; the CDO and the second (non-live) instance read False in
  every arm. A built-in negative control.
- ★ Three sibling badges of the identical class stayed `Collapsed` in every arm.
- ★ Reversible and repeatable in both directions.
- [M] Canaries zero throughout: `LogJson … Unable to import` 0, `Deserialization failure` 0,
  `Invalid response received` 0, `Fatal` 0.

⇒ This also upgrades the `[S]` endpoint↔struct join to strongly corroborated: the boolean could not
have moved unless our document deserialized into `FPlayerRank` and reached `UMMRManager`.

---

## 5. ⚠⚠ Arm B′ — the instructive failure, and why `AGS_PLAYER_RANK=0` is not a control

Serving `{}` did **not** turn the badge back off. The tempting write-up is "the badge latches" or
"the widget is stale". Both would have been wrong.

`{}` changes the document **and** the version at once (it parses to `Version: 0`), so it cannot
separate "stale version rejected" from "empty document discarded". **It is uninterpretable, not
negative.** Arm D settles it: a valid, non-empty document at `Version: 1` is *also* ignored.

⇒ **Read a null on this endpoint as "possibly version-rejected" until you have checked that Version
advanced.** The shipped handler uses `int32(time.Now().Unix())`, which self-advances, so the failure
mode is designed out rather than left to be remembered — the discipline CLAUDE.md asks for after the
same class of bug bit the client-config and regions eTags twice in one session.

★ Generalisable: **when a revert knob changes more than one thing, it is not a control.** The revert
that returns to a *catch-all* is especially dangerous, because it silently changes every field at
once. Build the controlled negative (`AGS_PLAYER_RANK_EMPTY=1`) alongside the feature.

---

## 6. ⚠ Instrument defects found and fixed

### `bpframe_readout.py` picks the wrong instance — FOURTH member of a known family

Three live objects share `WBP_UI_MainMenu_NormalMainMenu_C`: the CDO and **two** both named
`MainMenu_NormalV2`. The shipped tool stops at the first non-`Default__` match, whose frame is
entirely default (**HAS-RUN = 0** non-default locals of 219) — so it reported `False` for a graph
that **had never run**, on a menu live for 74 minutes, and the answer looked measured. The real
widget is the third object (HAS-RUN = 61).

⚠ Both live-looking instances share the same **name**, so name matching cannot separate them either.
**Only the has-run control can.**

⇒ Joins `obj_by_class.py` (substring), `cheat_reach_probe.py` (endswith) and `class_props.py`
(class-of-class). The shared defect is *take the first match*; the shared fix is *enumerate and show
your work*. **New: `tools/re/bpframe_all.py`** prints every instance with its own has-run control.
A warning banner now points there from `bpframe_readout.py`.

### `obj_props_dump.py` is blind to scalars — and offers a decoy

It prints only Object/Array properties, so `WidgetSwitcher.ActiveWidgetIndex` and `Visibility` are
invisible. Worse, what it *does* show includes a plausible-looking one: the CAREER badge reads
`ActiveSequencePlayers = Num=2`, which looks like "animations running, therefore visible".
[M] The three **collapsed** sibling badges read 2, 2 and 1. **It does not discriminate.**
Read alone it would have been recorded as confirmation; the sibling controls killed it in one call.

⇒ **New: `tools/re/obj_scalars.py`**, the companion half — every reflected int/bool/byte/enum/
float/name/string property of any live object.

### ⚠ `Start-Process -ArgumentList` does not quote paths containing spaces

Restarting `ags` with an array `-ArgumentList` truncated `-log "G:\git\Supervive Revival Project\…"`
at the first space. ags printed `capture log: G:\git\Supervive` and wrote there — **`capture.log`
went completely silent while the backend was fully functional**, and a stray `G:\git\Supervive` file
was created. `-certs` was mangled the same way and survived only because the relative fallback
happened to resolve against the correct working directory.

★ **What saved it was a second, independent instrument**: `Loki.log`'s `LogClientConfig` receipts
showed the client fetching every 30 s with the correct eTag. Trusting `capture.log` alone would have
produced "the client died on the ags restart." **Always have a client-side and a server-side view.**

⚠ Note this also contradicts CLAUDE.md's "`ags` truncates `docs/capture.log` on restart" — in this
session it **appended**. Back it up regardless; the point is that the recorded behaviour is not
reliable either way.

---

## 7. What this opens

- ★ **A new endpoint fell out of serving this one**: `POST /party/parties/{p}/refreshRanks` appears
  in the resync and is **absent from all 56 routes observed before this handler existed**. Still
  unserved. S121's "serving a surface reveals more surface" continues to hold.
- ⚠ **This is NOT a login-only fetch.** [M] Restarting `ags` alone drops and re-establishes the
  client's WebSockets, and the resulting resync refetches this endpoint within ~40 s. All five arms
  rode on that, with no relaunch. (My own first draft asserted it "probably needs a relaunch", by
  analogy with `/player-stats/players/{id}` — reasoning by similarity where a measurement was
  available. Corrected.)
- **Still unserved with real UI behind it:** `GET /referral/player/{id}` and `/points`.

### ⚠ RETRACTED WITHIN THE SESSION: "`QueueRankRating` is untested"

This document originally said all five arms rode on `RewardsToClaim` and that the `QueueRankRating`
half was unverified, with `tutorialNew` "very likely" the wrong key. **An operator screenshot
falsified that immediately.** [M] The RANKED page renders **`GOLD I`** and **`1,850 RP`** — our
served `Rank: "Gold1"` and `Rating: 1850` — and `tutorialNew` resolves to the display label
**BASIC TRAINING**. Both halves of `FPlayerRank` render; the queue key was right.

★ The caveat was written from "I did not test it", which is correct, and then editorialised into
"it is likely wrong", which was not measured. **Record untested as untested; do not attach a
prediction to it and let the prediction get remembered as the finding.**

---

## 9. ★★★★★ The RANKED queue dropdown — `IsRanked` is the filter [M]

**The question that produced this:** the dropdown beside `SEASON 2` showed only BASIC TRAINING, and
looked like a season selector with no seasons in it.

**It is not a season selector.** [M] From the asset: its class is
`WBP_UI_Leaderboard_ComboBox_Queues_C` and `WBP_UI_RankedScreen`'s own symbols are `QueueSelector`,
`UpdateSelectedQueue`, `InitQueueButtons`. It reads `CallFunc_GetQueueInfo_ReturnValue`, i.e. our
`GET /party/matchmaking/info`. `SEASON 2` is a **separate static element** (`SeasonHeader`) that sits
next to it. ⇒ **Read the widget class before accepting a screen-position reading of what a control
does.** Two adjacent controls, two unrelated data sources.

**Why it listed one of four.** We advertise four queues (`tutorialNew`, `training`, `practice`,
`bots`) — CAREER→STATS renders all four — but `buildQueueDetails` hardcoded `IsRanked: false` on
every one, and the combobox carries a `ShowOnlyRankedQueues` flag. Filtered, the list is empty and
the control falls back to the currently-selected queue.

**PRE-REGISTERED, then CONFIRMED [M].** Flew `AGS_RANKED_QUEUES="tutorialNew,training,practice"` —
**`bots` deliberately excluded as the control** — and predicted before looking: TRAINING MODE and
PRACTICE RANGE join BASIC TRAINING, and CO-OP VS. AI stays absent.

    observed: BASIC TRAINING · TRAINING MODE · PRACTICE RANGE      (CO-OP VS. AI absent)

Three present, one absent, exactly as written down. ⇒ **`IsRanked` is the filter.** Canaries 0,
eTag moved `…2f8ca395f53f` → `…2694efceeca2`, no relaunch.
★ The excluded queue is what makes this a measurement rather than a coincidence: "mark them all and
see them all" is consistent with the flag doing nothing.

### ⚠ Seasons are a dead end, and a already-recorded one

`SeasonHeader` is driven by `K2Node_ClassDynamicCast_AsLoki_Data_Asset_Season`. [M] A search of the
69k-asset catalog finds seasonal **textures**, `DT_SeasonalBattlepassRichText` and
`LT_ArmoryEquipment_Season2`, but **no `LokiDataAsset_Season` instance is packed** — the same missing
asset CLAUDE.md already records as blocking the seasonal battlepass. There is no backend lever
because the cast has nothing to land on. **Do not chase a season list from the server.**

### ⚠ And a latent stale-eTag bug fixed next door

`matchmakingETag` was the hardcoded constant `"revival-queues-v1"` while this body just became
env-dependent — the fourth instance of the exact failure this project keeps shipping (client-config
and regions in S121 an hour apart; `FPlayerRank.Version` in §5 above). Now content-hashed:
`revival-queues-v1-<sha256[:6]>`. ⚠ **When you make a payload env- or state-dependent, its eTag
stops being a constant in the same edit — not in a follow-up.**

⚠ **BLAST RADIUS, unretired:** this array also feeds the PLAY screen's activity picker, and
`IsRanked` may gate matchmaking behaviour rather than only a label. `AGS_RANKED_QUEUES` therefore
defaults **empty** (byte-identical to pre-S122) and is opt-in.
★ **A live lead:** `queueIDs` was trimmed to four by an **S60 diagnostic**. Followed up in §10.

---

## 10. ★★★★★ The S60 queue trim is RETIRED — and the workaround was hiding the real defect

**Asked:** "is the queue trim obsolete now?" **Answer: yes, but removing it alone was not enough**,
and the reason is the most reusable thing in this document.

### The trim's stated mechanism does not exist [M]

    "CanControlQueue loops over the current queues calling GetLevelGameFeatureUnlocked; with the
     served account level = 0, any level-gated queue fails that loop -> every activity click errors
     'Unable to modify activity'."

From the shipped bytecode (`bpdump_CanControlQueue.txt`, statements 181-185):
`GetLevelGameFeatureUnlocked` is called **exactly once**, with a **hardcoded**
`PrimaryAssetId{GameFeature, "Ranked"}`, behind `EX_PopExecutionFlowIfNot(Not(bIsRankedEligible))`,
and only to format the "you need level N" Text. **There is no loop and no per-queue feature lookup.**

⚠ **And the other half of the premise was mine and also false.** I wrote that the trim's precondition
was gone because "S120 serves `AccountPass.Level = 10`". [M] The live server serves **Level 0**.
S120 *measured* that serving 10 removed the mastery lock; it never became the default (it comes from
persisted per-player state). ⇒ **Read a remembered measurement as a measurement, not as a default.
Check the wire.**

### THREE separate causes wore one symptom

| symptom | cause | fix |
|---|---|---|
| only 4 tiles | the S60 trim | full 10 restored; `UPartyModel.Queues` **4 → 10** [M] |
| selection snapped back to BASIC TRAINING | **`POST setTargetQueues` had no handler** | implemented |
| ARENA `LEVEL 13 🔒` | `AccountPass.Level = 0` | identified, two levers, neither pulled |
| BASIC TRAINING pre-selected | onboarding: `Get_Number_of_Games_Played = 0` | not a bug |

### ★★★★★ THE WORKAROUND WAS HIDING THE DEFECT THAT MADE IT LOOK NECESSARY

`POST /party/parties/{p}/setTargetQueues {"queueIds":["deathmatch"]}` fell to the `/` catch-all, so
the next `/party` poll re-served the old `targetQueueId` and the selection reverted — the observed
grey/un-grey snap-back. **Under the trim this was invisible: with one selectable activity there was
nothing to switch to.** So S60 saw "activities don't work with the full list", trimmed the list, and
the trim removed the *evidence* rather than the cause.

⇒ ★ **When a workaround is in place, the bug it hides cannot be observed — which makes the
workaround look correct forever. Removing it is how you find out.** Operator-confirmed after the fix:
*"it will select that correctly with the border showing, and it keeps whatever i last selected."*

### ⚠⚠ THE SWEEP METHOD'S BLIND SPOT, named by its own miss

§1's sweep reported **"56 client routes, 8 unserved"** — and `setTargetQueues` was **not among them**,
because nobody clicked an activity tile during that 74-minute capture. A capture-diff enumerates the
endpoints the client *happened to exercise*, not the ones it *can call*.
⇒ **A passive capture-diff is a LOWER BOUND on unserved surface, never a map.** Drive the UI through
the interactions you care about, then re-run the diff.

### ★★★★★ A THIRD CATEGORY OF FEATURE-TOGGLE KEY: dynamically constructed

Tracing the ARENA lock found a toggle key family that **no static census could have found**
(`bpdump_IsQueueIDPremadeOrOverQueueLevel.txt`, statements 6-11):

    [6]  Concat_StrStr("queue.restrictions.", QueueID)   -> FeatureKey
    [7]  Temp_string_Variable = "Level"                  -> ConfigKey
    [9]  GetFeatureToggle(key, out bHasToggle, bEnabled, out FeatureToggle)
    [10] Map_Find(FeatureToggle.Config, "Level", out Value)
    [11] Conv_StringToInt(Value)  -> [12] SelectInt(parsed, fallback)

⇒ **`featureToggles["queue.restrictions.<queueId>"].Config["Level"] = "<int>"`** sets a queue's
required level from the backend. ⚠ **[S] — measured from bytecode, NOT flown.**
⚠ `FFeatureToggle.Config` is `TMap<FString,FString>`, whose `Map_Find` is case-**sensitive**, so
`"Level"` must be exact. The lowercase `level` seen nearby is the format-arg name in ST_Parties'
`"Requires Hunter's Journey level {level}"` — a different role, not a case ambiguity.
⚠⚠ **S121 declared the toggle vocabulary closed "with no remainder" at 50 declarative + 10 bytecode
keys. It is not closed.** Keys built at runtime by string concatenation are invisible to both
censuses, and there may be other parameterized families. **The vocabulary is open again.**

### Unrelated but now measured: the BASIC TRAINING pre-selection is onboarding, not a stuck queue

[M] live on `Comp_MainMenu_Onboarding` (has-run 59): `IsMatchHistoryLoaded = True`,
`Get_Number_of_Games_Played = **0**`, `Should_Launch_Tutorial_Match_bPlayMatch = **True**`. The
client recommends the first tutorial module because we report zero games played — correct behaviour,
not a defect. ★ The proof it is not the queue selection: on opening the page the client POSTs
`{"queueIds":["default"]}` (= BREACH) while the UI highlights BASIC TRAINING. Two different things.
Exiting onboarding needs a non-empty `FMatchHistory.Matches`, which FK-17 deliberately avoided
because `FMatchHistoryEntry` is 15 fields and a wrong-typed matched key sinks the document.

## 8. Knobs

    AGS_PLAYER_RANK=0          fall through to the {} catch-all (pre-S122 behaviour, no rebuild).
                               ⚠ NOT a controlled negative — see §5.
    AGS_PLAYER_RANK_EMPTY=1    valid struct, advancing version, EMPTY reward map. The real control.
    AGS_PLAYER_RANK_VERSION=N  pin Version instead of the clock. Isolates the version gate.
