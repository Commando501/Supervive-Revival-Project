# S121 — LEADERBOARDS response schema (offline derivation)

Date 2026-08-15. **Offline only** — no launch, no injection, no live process touched.
Every claim labelled **[M]** measured / **[I]** inferred / **[S]** speculative.

---

## 0. Positive control — the method, validated before use

Per `docs/method-rules.md` and the S120 precedent, the derivation method was first run
**blind** against four structs this repo already has right, and the output compared to the
committed ground truth.

**Method under test:** cross-read
(a) `tools/asdump/out/binds_members.csv` — the Angelscript bindings table (names + types), and
(b) the usmap `tools/extractor/mappings.usmap` parsed with `tools/asdump/usmap_lite.py`
    (names, order, super-links, scalar types — the FK-14-trustworthy subset).

| struct | method output | ground truth | verdict |
|---|---|---|---|
| `FPlayerProgression` | 8 props: `ID` Str, `Version` Int, `Matches` Map<Str,FPlayerProgressionMatchXP>, `MissionInfo` FMissionInfo, `AccountPass` FProgressionTrackLevel, `HeroMastery` Array<FHeroMasteryProgress>, `LoginReward` Array<FLoginReward>, `EventProgression` Array<FEventProgression> | `CLAUDE.md` S120 **[M]** schema (UHT + `binds_members.csv` + disasm of `GetHeroMastery` `base+0x5841D70`): same 8, same order | ✅ **exact** |
| `FHeroMasteryProgress` | super `FProgressionTrackLevel`; own `HeroId` FPrimaryAssetId; base `Level` Int, `XP` Int, `Cleared` Bool, `UnclaimedRewards` Map<Int,FHeroMasteryRewardClaimData> | S120: SizeOf 0x70, `Level@0x04, XP@0x08, Cleared@0x0C, UnclaimedRewards@0x10, HeroId@0x60` | ✅ **exact** (member set + super-link) |
| `FMissionInfo` | 4: `MissionData` Array<FMissionProgress>, `Pools` Array<FMissionPool>, `Completions` Map<FPrimaryAssetId,Int>, `MissionClaimData` Array<FMissionClaimData> | `server/internal/interactive/missions.go` served shape | ✅ **exact** |
| `FMatchHistory` | 3: `ID` Str, **`Version` Int64**, `Matches` Array<FMatchHistoryEntry> | `CLAUDE.md` FK-17 / `interactive.go:502` — `Version int64` | ✅ **exact, incl. the int64-vs-int32 discrimination** |

**Control result: 4/4 exact, 0 misses, 0 false fields.** The int32/int64 split between
`FPlayerProgression.Version` (Int) and `FMatchHistory.Version` (Int64) is reproduced correctly,
which is the sharpest single discriminator available. **The method is validated.** [M]

**Two caveats the control also surfaced, which govern reading the tables below:**
1. `binds_members.csv` lists a **derived** struct's OWN members BEFORE its inherited ones
   (`FHeroMasteryProgress` = HeroId, Level, XP, …), so its index order is **not memory order**
   for inherited structs. Irrelevant to JSON (name-keyed), relevant if you read offsets. [M]
2. Per FK-14 the usmap's **container inner types and enum underlying types are ~70 % wrong**.
   Where the two instruments agree on an inner type below, treat `binds_members.csv` as the
   source and the usmap as non-evidence, not as corroboration. [M]

---

## 1. Ground truth from the wire

`docs/capture.log`, filtered on `User-Agent: Loki/UE5-CL-0` (the game — the CLAUDE.md
User-Agent trap check was run; none of these are our own tooling). [M]

```
#17416 16:31:02  GET /player-stats/leaderboard?queueId=tutorialNew&period=daily&statCode=wins&heroId=Hero:All&start=1&end=25   -> 200
#17829 16:31:22  GET /player-stats/leaderboard?queueId=tutorialNew&period=weekly&statCode=wins&heroId=Hero:All&start=1&end=25  -> 200
#17853 16:31:23  GET /mmr/leaderboard?start=1&end=50&queueId=tutorialNew&region=                                              -> 200
#17416 …         GET /player-stats/players/9b9d2c887e2524f918e383a895f2f1c2                                                   -> 200
```

⇒ **`period` observed values: `daily`, `weekly`** — lowercase. [M]
⇒ `/player-stats/leaderboard` uses `end=25`; `/mmr/leaderboard` uses `end=50`. [M]
⇒ The RANKED side-tab fires `/mmr/leaderboard` (different endpoint, different struct). [I]
⇒ FRIENDS was never clicked in this capture; a `/mmr/leaderboard/friends` literal exists
   (`.rdata 0x8b45848`) so FRIENDS is **[I]** a separate endpoint, not a `period` value.

### URL builders located in `dumps/merged2.dump.exe` (ImageBase `0x7FF6AF000000`, file-offset == RVA) [M]

UTF-16 `.rdata` literals (`.rdata` is complete in every image, so presence/absence is safe here):

| RVA | literal |
|---|---|
| `0x8b4cda0` | `/player-stats/leaderboard?queueId=` |
| `0x8b4cd80` | `&period=` |
| `0x8b4cd68` | `&statCode=` |
| `0x8b4cd50` | `&heroId=` |
| `0x8b4cd40` | `&start=` |
| `0x8b4cd30` | `&end=` |
| `0x8b4cd00` | `/player-stats/players/` |
| `0x8b4cc30` | `Failed to fetch player stats: status [%d] error [%s]` |
| `0x8b45880` | `/mmr/leaderboard?start=%d&end=%d&queueId=%s&region=%s` |
| `0x8b45848` | `/mmr/leaderboard/friends` |
| `0x8b45910` | `/mmr/player/` |

rip-relative `lea` xrefs in `.text`: `0x5842674` → the leaderboard URL literal (and
`0x58426ab` → `&statCode=`), `0x58458b2` → `/player-stats/players/`, `0x57b0fb0` → the
`/mmr/leaderboard` format string. [M]

**Note on the literal pool:** a full UTF-16 sweep of `0x8b4c400–0x8b4d100` (the surrounding
`.rdata` run, which also holds the party / loadout / personalization / progression TU literals)
contains exactly **one** player-stats diagnostic string — the HTTP-level
`Failed to fetch player stats…` above. There is **no** leaderboard-specific validation or
envelope-key literal in that run. [M] That is weak evidence for a top-level (un-enveloped)
response; it is not decisive, because literals for a different TU can live elsewhere.

---

## 2. `GET /player-stats/leaderboard` — the response struct

Two independent instruments, **in exact agreement** on names, count, order and scalar types.

### 2.1 Envelope: `FLokiPlayerStatsLeaderboard` (`/Script/Loki.LokiPlayerStatsLeaderboard`, 8 props)

Header: `Loki/Source/Loki/Services/PlayerStats/PlayerStatsModel.h`
(`tools/asdump/out/binds_headers.csv:9235`). [M]

| # | UPROPERTY | UE type | JSON type to send | required? | conf |
|---|---|---|---|---|---|
| 0 | `Period` | `FString` | string | optional — **not** compared | [M] |
| 1 | `StatCode` | `FString` | string | ★ **REQUIRED — must echo** `statCode` | [M] |
| 2 | `HeroName` | `FName` | string | ★ **REQUIRED — must echo the BARE name** (`All`, not `Hero:All`) | [M] |
| 3 | `QueueID` | `FString` | string | ★ **REQUIRED — must echo** `queueId` | [M] |
| 4 | `Entries` | `TArray<FLokiPlayerStatsLeaderboardEntry>` | **array of objects** | **REQUIRED for rows** | [M] |
| 5 | `Start` | `int64` | number | optional — not compared | [M] |
| 6 | `End` | `int64` | number | optional — not compared | [M] |
| 7 | `ExpirationTimeSeconds` | `int32` | number | drives `RESET IN` | [M] |

### ★★★★★ 2.1a THE ECHO-MATCH GATE — this is the whole trick

`WBP_UI_LeaderboardScreen_C::Current Leaderboard Is Stale` (bpdump of
`Loki/Content/Loki/UI/Widgets/FrontEnd/MainMenu/Leaderboard/WBP_UI_LeaderboardScreen.uasset`)
computes: [M]

```
stale =  HeroName != PrimaryAssetIDFromString(heroCombo.SelectedItemKey).PrimaryAssetName
      || StatCode != statCombo.SelectedItemKey
      || QueueID  != queueCombo.SelectedItemKey
      || (UtcNow - fetchedAt) > Timespan(0,0,0,60,0)          // 60 s TTL
```

⇒ **A response that does not echo `StatCode`, `QueueID` and `HeroName` back exactly is treated
as stale and discarded**, and it looks *identical* to "no effect". This is the same silent-drop
class as the mission `InternalName` registry and the `FParty.Version` gate.

⚠ **`HeroName` is the BARE `FPrimaryAssetId::PrimaryAssetName`, NOT the wire form.** The request
carries `heroId=Hero:All`; the comparison is against `PrimaryAssetName` = **`All`**. Serving
`"Hero:All"` here fails the compare. FName matching is case-insensitive, so `All` / `all` both
work. [M]
⚠ `Period`, `Start`, `End` are **not** in the comparison. [M]

★ **This is corroborated on the wire:** `docs/capture.log` shows the identical daily query
fetched at `16:31:02.075` and again at `16:31:03.159`, and again at `16:31:24.213` /
`16:31:25.588` — repeat fetches of a query we answered with `{}`, i.e. with empty
`StatCode`/`QueueID`/`HeroName`, which can never satisfy the compare. [M]

### 2.2 Row: `FLokiPlayerStatsLeaderboardEntry` (5 props) [M]

| # | UPROPERTY | UE type | JSON type to send | notes | conf |
|---|---|---|---|---|---|
| 0 | `PlayerID` | `FString` | string | PLAYER column, via `GetPlatformPlayerManager()->GetPlayer(PlayerID)->DisplayNameAndTag()`; gated on `!PlayerID.IsEmpty()`. An **unresolved id still renders a row** (placeholder text + async re-fill through `OnChangeDisplayName`) | [M] |
| 1 | `Rank` | `int32` | number | RANK column, `Format("{rank}", Entry.Rank)` — printed verbatim, **no filter, no skip** | [M] |
| 2 | `Value` | `float` | number | SCORE column, rendered as **`Conv_IntToText(FCeil(Value))`** — the float is **ceiled**, so `42.3` displays `43` | [M] |
| 3 | `HeroName` | `FName` | string | `FindHeroAssetByInternalName(HeroName)` → gates the hero-name label's visibility | [M] |
| 4 | `HeroCounts` | `TMap<FName,int32>` | **JSON object** `{"ghost":3}` | **DOES drive UI** — see below | [M] |

★ **`HeroCounts` is not dead weight.** When the HUNTER filter is the "all" sentinel (i.e.
`Hero Name Override == FName("all")`), the row widget does `Map_Keys(HeroCounts)` and adds
**one 48×48 hero portrait per key** — the *values are never read*. Otherwise it draws a single
portrait from the row's `HeroName`. [M] ⇒ On the observed `heroId=Hero:All` query, supplying
`HeroCounts` is what gives each row its hero portraits; omitting it simply draws none.

**Row ordering:** `Update Leaderboard` clears the grid and assigns grid Row = **array index**,
so **array order is display order** — `Rank` is a label, not a sort key. [M]

**Empty state:** `Update Leaderboard` branches on **`Entries.Num() > 0`**; the else-arm
instantiates `WBP_UI_Leaderboard_NoEntries_C`, which is the observed
*"No one has claimed a spot on this leaderboard...yet. Be the first!"*. [M] ⇒ **a single
well-formed entry is sufficient to leave the empty state.**

⚠ `HeroCounts` is a `TMap`. A `TMap` sent as a JSON **array** is the exact failure that
sinks the whole struct (the S120 `UnclaimedRewards` precedent in `CLAUDE.md`). Omit it, or
send `{}`. [M-by-precedent]

★ **`HeroCounts` being a `TMap` is confirmed by a THIRD, independent instrument — the UHT
name blob itself.** `.rdata` ASCII at `0x8ad8410` = `HeroCounts`, immediately followed at
`0x8ad8420` by **`HeroCounts_Key`**, then `0x8ad8430` = `LokiPlayerStatsLeaderboardEntry`
(and `0x8ad88e0` = `ExpirationTimeSeconds`, `0x8ad89d8` = `LokiPlayerStatsLeaderboard`). UHT
emits a `<Name>_Key` property **only** for an `FMapProperty`. [M] This matters because FK-14
established that the usmap's container-inner types are ~70 % wrong, so `binds_members.csv`
was the only trustworthy source until now — the UHT oracle makes it two.

### 2.2a The response is parsed TOP-LEVEL — no envelope [M]

Settled by disassembly (`DISASM.md`). The URL builder is `0x58425f0` (verb `GET`); the response
callback is `0x5809760`, an instantiation of Loki's generic `Query<T>` template:

```
058099ea  call [rax+0x58]   ; GetResponseCode — accepts 200..299 ONLY
05809a08..3d                ; zero-init OutStruct, exactly 0x60 bytes
05809a44  call [rax+0x60]   ; GetContentAsString -> rax = &FString(raw body)
05809a4f  mov  rcx,rax      ;   <<< JsonString = THE RAW BODY, unmodified
05809a52  lea  rdx,[rbp-0x20]
05809a59  call 0x57e9220    ; JsonObjectStringToUStruct<FLokiPlayerStatsLeaderboard>
```

**Zero instructions between `GetContentAsString` and the converter** ⇒ the JSON root object maps
directly onto the struct's properties. [M]

★ **Positive control for that negative** (what makes it a result rather than an absence): a
detector run over **all 152** `JsonObjectToUStruct` call sites in the image, looking for a
rip-relative `lea` of a `.rdata` wide string in the parse→convert window, fires on **exactly 1
of 152** — `FAccelByteModelsPartyNotif` at `0x4b03095`, `lea rdx,[0x783c540] W"payload"` →
`TryGetObjectField` → sub-object → converter. It reports **0** for all four Loki structs.
⇒ the detector *can* see an envelope; these routes do not have one. [M]

All 14 cited addresses were verified `page_decrypted = True`, so this rests on read code, not on
an undecrypted gap.

### 2.2b Two hard preconditions on the HTTP response itself [M]

1. **Status must be 200–299.** `0x58099ea`: `lea ecx,[rax-0xc8]; cmp ecx,0x63; ja <bail>`.
2. **A second fetch while one is already in flight is SILENTLY DROPPED.** `0x58423ea`:
   `cmp byte [rcx+0x59],0 / jne return`; the flag is set at `0x584240c` and cleared at
   `0x5838c8c` / `0x583c978`. Not one-shot, but a hung or slow response suppresses the next
   REFRESH press with no log line. Keep the handler fast.

★ **Free instrument on this route** — the generic `Query<T>` logs at **Warning**, so they print
with no verbosity change: `Query.h:194` `"Could not connect"`, `Query.h:204` `"Bad status(%d)"`
(suppressed for 404/304), and **`Query.h:212` `"Deserialization failure"`**.
⇒ `Deserialization failure` in `Loki.log` is an unambiguous readout that the body arrived and
was rejected. Check it before anything else.

### 2.3 Key spellings and the `FJsonObjectConverter` validity model

- Property lookup is **case-insensitive** (UE `TMap<FString,…>` hashes with `Strihash` and
  `FString::operator==` is `Stricmp`), so `PlayerID` / `playerId` / `playerid` all match. **[I]**
  ⚠ Deliberately NOT upgraded to [M]. The one in-repo case-mismatch that demonstrably works —
  `handleProgressionTracks` serving lowercase `"data"`/`"paging"`/`"previous"`/`"next"` against
  UPROPERTYs `Data`/`Paging`/`Previous`/`Next` (`server/internal/menu/menu.go:617`) — is on the
  **AccelByte SDK** path, and that SDK ships its own converter that lowercases the first letter
  by design. It is therefore **not** evidence about Loki's own `FJsonObjectConverter` path.
  Every Loki-native route we serve today (`/progression/players/{id}` etc.) uses exact
  UPROPERTY casing, so the project has **no controlled positive** for case-folding on this
  path. ⇒ **Use exact UPROPERTY casing; do not rely on case-insensitivity.**
- **Unknown keys are ignored silently**; a **matched key with the wrong type rejects the
  WHOLE struct** and looks identical to "no effect". This is the standing project model
  (`server/internal/menu/menu.go` header, and the S120 `HeroMastery` blast-radius note). [M]
- ⇒ **A wrong type is strictly worse than a missing field.** Send only fields you are sure of.
- **Free instrument:** `LogJson` is pinned to Verbose in this user's `Engine.ini` and names the
  failing property verbatim (`Unable to import JSON value into property X`,
  `Unable to import Array element N`). Grep it before inferring anything from a null. [M]

**Recommended key spelling = the exact UPROPERTY name** (`Period`, `StatCode`, `HeroName`,
`QueueID`, `Entries`, `Start`, `End`, `ExpirationTimeSeconds`, `PlayerID`, `Rank`, `Value`,
`HeroCounts`). Case-insensitivity means camelCase would also work, but exact-name costs
nothing and removes a variable.

### 2.4 There is no manager-level cache, and therefore no manager-level gate

`UPlayerStatsManager : UPlatformManager` has exactly **3** reflected members —
`OnPlayerStatsUpdated` (multicast delegate), `PlayerStatsService` (object), and
**`PlayerStats` (`FPlayerStats`)**. `UMMRManager : UPlatformManager` has **4** —
`OnPlayerUpdated`, `MMRService`, `ClientConfigManager`, **`Player` (`FPlayerRank`)**. [M]

**Neither manager holds a leaderboard member.** The leaderboard result is therefore not
adopted into manager state at all — it is handed straight to the `OnSuccess` callback
(`FOnPlayerStatsLeaderboardFetch` / `FOnLeaderboardFetch`, both defaulted parameters on the
`GetLeaderboard` signatures in `binds_members.csv`) and consumed by the caller. **[I]**

⇒ This materially lowers the risk that bit this project on `FParty`, `FMatchHistory` and
`FPlayerProgression`: **there is no adopted copy to compare against, so there is no
monotonic-`Version` or staleness gate at the manager layer.** Any echo-matching or dedupe
would have to live in the requesting widget's own Blueprint. [I]

★ **That prediction was made before the widget bytecode was read, and it is CONFIRMED** — the
gate exists and it is exactly where this argument said it had to be:
`WBP_UI_LeaderboardScreen_C::Current Leaderboard Is Stale` (§2.1a). Recording it because a
correct pre-registered prediction is the cheap way to grade the method, and this project's
own history is full of the opposite.

### 2.4a ⚠ RECONCILIATION — "no validation" and "there IS an echo-match" are BOTH true

These two measurements look contradictory and are not. They are at **different layers**, and
conflating them would produce exactly the kind of false wall this project keeps recording.

| layer | what was measured | verdict |
|---|---|---|
| **service** (`Query<T>` callback `0x5809760`) | between `test bl,bl` and the subscriber broadcast at `0x5809b91` there is **nothing** — no `Entries.Num()` test, no range check, no echo compare, no `Version` gate. Success path just locks, walks the subscriber array, invokes each with `rdx = &OutStruct`, unlocks. [M] | **no validation** |
| **widget** (`WBP_UI_LeaderboardScreen_C`) | `Current Leaderboard Is Stale` compares `HeroName` / `StatCode` / `QueueID` against the live combo-box selections, plus a 60 s TTL. [M] | **echo-match REQUIRED** |

⇒ **The struct is always ingested; the WIDGET is what discards it.** So the practical rule is
the widget's: **echo `StatCode`, `QueueID` and `HeroName` (bare) or nothing renders.**
⇒ It also means a failed echo is *invisible* to `Query.h:212 "Deserialization failure"` — that
log fires only on a parse failure, and a non-echoing response parses perfectly. **Do not read a
silent `Loki.log` as "the response was accepted and the page is just broken."**

⚠ Scope limit on the service-layer negative, stated honestly: subscriber-side validation could
not be enumerated statically — subscribers are runtime-bound heap lambdas with no vtable slot.
Coverage: of 74 `Query.h:212` records image-wide, 61 have decrypted call sites; all three
endpoints of interest are decrypted and were read in full.
⇒ It also means the fetch is **fire-and-forget per request**, which is consistent with the
capture showing a fresh GET on every tab switch and REFRESH press rather than a single
adopt-once fetch. [M on the capture, [I] on the causal link]

---

### 2.5 Offsets and `sizeof` — UHT oracle, calibration PASSED [M]

Decoded from the UE5.4 `UECodeGen_Private::FStructParams` tables. ⚠ **In this build those tables
live in `.data`, not `.rdata`, and pack `+0x28 u16 NumProperties, +0x2a u16 SizeOf,
+0x2c u16 AlignOf`** — the stock `int32/uint32` reading does not decode them at all.

**Calibration before use** (same discipline as §0): `FPlayerProgression` → SizeOf **0x178** with
all 8 known offsets exact; `FHeroMasteryProgress` → **0x70**, `HeroId@0x60`, and its
`Level@0x04 / XP@0x08 / UnclaimedRewards@0x10` correctly attributed to the super
`FProgressionTrackLevel`. ✅ **Reproduces the known ground truth exactly.**

| `FLokiPlayerStatsLeaderboard` — SizeOf **0x60** | | `FLokiPlayerStatsLeaderboardEntry` — SizeOf **0x70** | |
|---|---|---|---|
| `Period` | `0x00` FString | `PlayerID` | `0x00` FString |
| `StatCode` | `0x10` FString | `Rank` | `0x10` i32 |
| `HeroName` | `0x20` FName | `Value` | `0x14` float |
| `QueueID` | `0x28` FString | `HeroName` | `0x18` FName |
| `Entries` | `0x38` TArray | `HeroCounts` | `0x20` TMap<FName,i32> |
| `Start` | `0x48` i64 | | |
| `End` | `0x50` i64 | | |
| `ExpirationTimeSeconds` | `0x58` i32 | | |

★ **Both cross-confirmed by CODE, not just by the tables** — the callback zero-inits exactly
`0x60` bytes (`0x5809a08..3d`), and the `Entries` destructor loop strides exactly `0x70`, freeing
an FString at `+0x00` and a TMap at `+0x20`. Two independent instruments agreeing. [M]

Others, same method: `FLeaderboard` **0x68** (`Start@0x00, End@0x04, QueueID@0x08, Role@0x18,
Entries@0x28, SelfEntry@0x38`) · `FLeaderboardEntry` **0x30** (`PlayerID@0x00, Rank@0x10 u8 enum,
Rating@0x14, Placement@0x18, Percentile@0x1c, AvatarID@0x20`) · `FPlayerStats` **0x68**
(`ID@0x00, Version@0x10, StatsByQueue@0x18`) · `FPlayerQueueStats` **0x60** ·
`FPlayerHeroStats` **0xa8**.

⚠ Two decoder caveats, neither affecting the structs above: **bool** properties report a bogus
`Offset` of 1, and container **inner** params (`PropertyFlags == 0`) precede the real property
with a meaningless offset. No target struct here has a bool.

⚠ These offsets are **not needed to write the handler** — `FJsonObjectConverter` is name-keyed
reflection. They are here for completeness and as a cross-check.

---

## 3. Vocabularies

### 3.1 `queueId` — **no shipped list; it is OUR backend feed** [M]

The QUEUE combo is built from `PartyManager->GetPartyModel()->GetQueueInfo()`: loop `Queues[]`,
keep if `IsRanked || !ShowOnlyRankedQueues` (that bool is unset on this instance, so **all** are
kept), drop the one equal to `GetBotQueueID()`, `AddOption(Queues[i].ID)`, then default-select
the **first survivor**. [M]
⇒ **The dropdown is exactly what `/party/matchmaking/info` serves**, minus the bot queue.
Labels come from `BPFL_Matchmaking::"Queue ID to Name"` →
`TextFromStringTable(ST_Parties, "queue.{id}[-ranked].name")` [M]:
`tutorialNew → Basic Training`, `training → Training Mode`, `practice → Practice Range`,
`bots → Co-op vs. AI`, `default → Breach`, `deathmatch → Arena`, `dropin → Warm-Up`, plus
`tournament`, `domination`, `prismabank`, ranked variants and CN-only entries.
⇒ `tutorialNew` shows as "BASIC TRAINING" because it is the first entry **we** serve.


`server/internal/interactive/interactive.go:1174-1188`:

> `queueIDs` is the set of matchmaking queue ids we advertise to the client. The full known
> set (from `WBP_ActivityPickerScreen.InitializeQueues`' string constants) is:
> `default deathmatch practice dropin customgame bots tutorialNew training armorydeathmath tournament`

and we currently serve a **DIAGNOSTIC TRIM (S60)** of just
`{"tutorialNew", "training", "practice", "bots"}`.

⇒ `tutorialNew` = "BASIC TRAINING" is the first entry of the list **we** serve. **[I]** the
LEADERBOARDS queue dropdown is fed from the same `/party/matchmaking/info` feed, in which case
widening `queueIDs` widens the dropdown. Worth confirming live.

### 3.2 `period` — **CLOSED, exactly two values** [M]

The page is `WBP_Leaderboard_Screens`, a switcher over **4** children:
`LeaderboardDaily` + `LeaderboardWeekly` (both `WBP_UI_LeaderboardScreen_C`) and
`RankedScreen` (`HasRegionSelector=True`) + `RankedFriends` (`OnlyFriends=True`), both
`WBP_UI_RankedLeaderboardScreen_C`. [M]

- CDO `Default__WBP_UI_LeaderboardScreen_C` → `Period` (StrProperty) = **`daily`**; the
  `LeaderboardWeekly` instance overrides `Period` = **`weekly`**. [M]
- ⇒ **`period ∈ {daily, weekly}` and nothing else.** The FRIENDS and RANKED tabs are a
  *different widget class* hitting *different endpoints* — `GetMMRManager()->GetFriendLeaderboard(...)`
  → `/mmr/leaderboard/friends`, and `GetMMRManager()->GetLeaderboard(1, 50, Queue, Region, ...)`
  → `/mmr/leaderboard`. [M] This confirms the earlier [I] and closes it.

### 3.3 `heroId` — [M]

`WBP_UI_ComboBox_Heroes` builds itself as `AddOption("hero:all")` — **lowercase in the shipped
bytecode** — followed by `AddOption(Conv_PrimaryAssetIdToString(id))` for each hero from
`Get Heroes Asset List Sorted`, i.e. `Hero:<InternalName>`. It `SelectOption("hero:all")` when
empty. [M] The wire shows `Hero:All` — [I] FName re-interning of the case-insensitive key.
⇒ **Match `heroId` case-insensitively on the backend**, and echo `HeroName` as the bare
`PrimaryAssetName` (§2.1a).
`CLAUDE.md` S120 establishes **[M]** `InternalName == Hero.PrimaryAssetName` for all 25 heroes.

### 3.4 `statCode` — **CLOSED, exactly four values** [M]

The STAT combo builds itself via `GetKeysFromStringTable` → `AddOption(key)` → `SelectOption("wins")`.
String table id confirmed in the raw uasset (3 hits):
`…/Leaderboard/ST_Leaderboard_Stats`. Full contents: [M]

| `statCode` | UI label |
|---|---|
| `kills` | Kills (Single Game) |
| `wins` | **Total Wins** (the default) |
| `damage` | Damage (Single Game) |
| `healing` | Healing (Single Game) |

⚠ Note three of the four are **single-game maxima**, not totals — so `Value` is a per-match
best, not a career sum. Relevant if you later compute these from match results.
⚠ Earlier speculation that `FPlayerHeroStats`' 22 fields were the `statCode` namespace is
**wrong** — `wins` is not among them. Discard it; the string table is the vocabulary.

### 3.5 `region` (ranked screen only) — [M]
`ST_Leaderboard_Regions`: `ALL`, `NA`, `EU`, `SA`, `APNE`, `friends`. The ranked screen
defaults to `SelectOption("default")` for queue and `SelectOption("ALL")` for region — which is
why the observed `/mmr/leaderboard` call carries `&region=` (empty maps to ALL). [M]
⚠ `friends` is a **region** key here, not a period.

---

## 4. Concrete response — paste-ready

For the observed query
`?queueId=tutorialNew&period=daily&statCode=wins&heroId=Hero:All&start=1&end=25`:

```json
{
  "Period": "daily",
  "StatCode": "wins",
  "HeroName": "All",
  "QueueID": "tutorialNew",
  "Start": 1,
  "End": 25,
  "ExpirationTimeSeconds": 3600,
  "Entries": [
    { "PlayerID": "9b9d2c887e2524f918e383a895f2f1c2", "Rank": 1, "Value": 42,
      "HeroName": "ghost", "HeroCounts": { "ghost": 7, "brall": 2 } },
    { "PlayerID": "00000000000000000000000000000002", "Rank": 2, "Value": 37,
      "HeroName": "brall", "HeroCounts": { "brall": 5 } },
    { "PlayerID": "00000000000000000000000000000003", "Rank": 3, "Value": 31,
      "HeroName": "jin",   "HeroCounts": { "jin": 4 } }
  ]
}
```

**The three load-bearing choices:**
- `StatCode`, `QueueID` and `HeroName` are **echoed** from the request, with `HeroName` as the
  bare `All` (not `Hero:All`). Without this the client marks the result stale and drops it
  (§2.1a). **This is the single most likely cause of a "no effect" result.**
- `HeroCounts` is a JSON **object**, never an array. Its keys are hero `InternalName`s and drive
  one portrait each; values are unread. Safe to omit entirely if you don't want portraits.
- `Value` is sent as a plain number; the UI `FCeil`s it, so send integers to avoid surprise.

Go sketch (`server/internal/interactive/` — register alongside the other routes there, which
take precedence over `cmd/ags`'s `"/"` catch-all):

```go
type LBEntry struct {
    PlayerID   string         `json:"PlayerID"`
    Rank       int            `json:"Rank"`
    Value      float64        `json:"Value"`
    HeroName   string         `json:"HeroName"`
    HeroCounts map[string]int `json:"HeroCounts,omitempty"` // TMap -> object, never an array
}
type LB struct {
    Period                string    `json:"Period"`
    StatCode              string    `json:"StatCode"`   // echo q.statCode
    HeroName              string    `json:"HeroName"`   // echo PrimaryAssetName of q.heroId
    QueueID               string    `json:"QueueID"`    // echo q.queueId
    Entries               []LBEntry `json:"Entries"`
    Start                 int64     `json:"Start"`
    End                   int64     `json:"End"`
    ExpirationTimeSeconds int       `json:"ExpirationTimeSeconds"`
}

// heroId arrives as "Hero:All" / "Hero:ghost"; echo only the part after ':'.
func primaryAssetName(s string) string {
    if i := strings.IndexByte(s, ':'); i >= 0 { return s[i+1:] }
    return s
}
```

---

## 5. `GET /mmr/leaderboard` (RANKED tab)

Deserializes **top-level** into **`FLeaderboard`** (`/Script/Loki.Leaderboard`,
`Loki/Source/Loki/Services/MMR/MMRService.h`). `Query<T>` handlers `0x5783420` / `0x57839a0`
(the `/friends` variant), deserializer `0x5760940`, same `mov rcx,rax` straight off
`GetContentAsString` — **no envelope**. [M]
⚠ The endpoint↔struct join itself is **[I]**, not [M]: it rests on uniqueness (one deserialize
site for this struct image-wide) plus exact field/query-param correspondence, because the
`TFunction` binding from URL builder to callback is a heap lambda with no vtable slot and could
not be followed statically. The member list is **[M]**.

| # | UPROPERTY | UE type | JSON |
|---|---|---|---|
| 0 | `Start` | `int32` | number |
| 1 | `End` | `int32` | number |
| 2 | `QueueID` | `FString` | string |
| 3 | `Role` | `FString` | string |
| 4 | `Entries` | `TArray<FLeaderboardEntry>` | array of objects |
| 5 | `SelfEntry` | `FLeaderboardEntry` | **object** (not array) |

`FLeaderboardEntry` (6): `PlayerID` FString · `Rank` **`ERank` enum** · `Rating` int32 ·
`Placement` int32 · `Percentile` float · `AvatarID` `FPrimaryAssetId`. [M]

⚠ **`Rank` is an enum, not a number-you-choose.** Send the entry NAME as a string. `ERank`
values, in order (usmap enum value tables are in the FK-14 *trustworthy* set): `Unranked,
Bronze4, Bronze3, Bronze2, Bronze1, Silver4…Silver1, Gold4…Gold1, Platinum4…Platinum1,
Diamond4…Diamond1, Master4…Master1, GrandMaster, Legend, Count`. [M]
A bad enum string is exactly the S118 `ELokiActivityState` failure and `LogJson` will quote
it back verbatim. `AvatarID` is an `FPrimaryAssetId` — send `"Avatar:<name>"` form or omit.

```json
{ "Start":1, "End":50, "QueueID":"tutorialNew", "Role":"",
  "Entries":[ {"PlayerID":"9b9d…","Rank":"Gold1","Rating":1850,"Placement":1,"Percentile":0.99} ],
  "SelfEntry":{"PlayerID":"9b9d…","Rank":"Gold1","Rating":1850,"Placement":1,"Percentile":0.99} }
```

`POST/GET /mmr/leaderboard/friends` **[I]** takes a `FFriendLeaderboardRequest`
`{QueueID FString, PlayerID FString, Players TArray<FString>}` [M] and presumably returns the
same `FLeaderboard`.

---

## 6. `GET /player-stats/players/{id}`

Deserializes **top-level** into **`FPlayerStats`** (`/Script/Loki.PlayerStats`). `Query<T>`
handler `0x581eb00`, deserializer `0x57ea620`, same shape — **no envelope**, and its success
path `0x581ec71` is byte-for-byte the same lock/broadcast/unlock as the leaderboard's, i.e.
**no validation**. [M] Endpoint↔struct join **[I]** on the same uniqueness argument as §5;
members **[M]**.
★ Calibration note: `FPlayerProgression`'s handler (`0x57ea020`) has the identical shape, and
that route is one this project has already measured as top-level — so the reading of this
family is anchored to a known-good case.

```
FPlayerStats      : ID FString, Version int32, StatsByQueue TMap<FString, FPlayerQueueStats>
FPlayerQueueStats : ID FString, StatsByHero  TMap<FString, FPlayerHeroStats>
FPlayerHeroStats  : 22 int32s + Placements TMap<int32,int32>   (list in §3.4)
```

⚠ **Both maps are `TMap` → JSON OBJECTS.** `StatsByQueue` is keyed by queue id,
`StatsByHero` by hero name, `Placements` by placement number as a **string key**
(`{"1": 4, "2": 9}`) — an int-keyed `TMap` needs int-parsable string keys, exactly like the
S120 `UnclaimedRewards` shape. [M-by-precedent]
⚠ `Version` here is **int32** (contrast `FMatchHistory.Version` int64). [M]
**[S]** whether this route has a monotonic `Version` gate like `FParty`/`FMatchHistory` do —
serve a bumping `Version` as cheap insurance.

```json
{ "ID":"9b9d…", "Version":1,
  "StatsByQueue": { "tutorialNew": { "ID":"tutorialNew",
    "StatsByHero": { "ghost": { "GamesPlayed":12, "Kills":40, "Knocks":55, "Placements":{"1":3,"2":5} } } } } }
```

---

## 7. What must be measured live

Most of the original live-check list was **settled offline** by the widget bytecode. What is
left is short. `LogJson` (pinned Verbose) + `docs/capture.log` are the readouts.

1. **Serve §4 verbatim, press REFRESH, screenshot.** Expect three rows, RANK 1/2/3,
   SCORE 42/37/31, hero portraits from `HeroCounts`.
   Two independent readouts if it stays empty:
   - **`Query.h:212 "Deserialization failure"` in `Loki.log`** — fires at **Warning**, no
     verbosity change needed. Present ⇒ the body was rejected by the converter.
   - **`LogJson`** (already pinned Verbose) names the offending property verbatim. The two
     I would most want checked are **`Unable to import JSON value into property Entries`** and
     **`… property HeroCounts`** — `Entries` is the only container in the envelope and
     `HeroCounts` is the only `TMap`, and those are the two fields whose type can sink the
     whole document. If `LogJson` names `HeroCounts`, drop that field and re-fly; everything
     else still renders, just without portraits.
   - ⚠ **Both silent + still empty ⇒ suspect the echo, not the parse** (§2.4a).
2. **`/mmr/leaderboard` (RANKED tab).** The `ERank` enum string is the risk; `LogJson` quotes a
   bad enum value back verbatim (the S118 `ELokiActivityState` pattern). Fly `"Gold1"` first.
3. **Does widening `queueIDs`** (`interactive.go:1187`) widen the QUEUE dropdown? Predicted
   **yes** — the combo is built straight off `GetQueueInfo()` [M]. Cheap, and a clean
   single-variable test of that claim.

⚠ **Rebuild the widget before reading anything off it.** `CLAUDE.md` (S120) **[M]**: pushing
data to an already-open page changes nothing on screen — two surfaces were mis-diagnosed as
broken feeds for exactly this. Here you have a first-class rebuild: the **REFRESH** button, or
switch DAILY↔WEEKLY and back. Note the client also has its **own 60 s TTL** (§2.1a), so a
result can appear up to a minute late without anything being wrong.

---

## 8. Open / not established

Everything the task asked for is now settled offline. What remains:

- **Subscriber-side validation cannot be enumerated statically** — subscribers are runtime-bound
  heap lambdas with no vtable slot. The service layer is clean [M] and the widget layer is fully
  read [M], so the gap is narrow, but it is real.
- **The endpoint↔struct join is [I], not [M]**, for all three routes: the `TFunction` binding
  from URL builder to response callback is a heap lambda. The join rests on (a) exactly one
  deserialize site per struct image-wide and (b) exact field/query-param correspondence. Strong,
  but not the same grade as the struct layouts.
- Whether `/player-stats/players/{id}` carries a monotonic `Version` gate like `FParty` and
  `FMatchHistory` do. **[S]** — serve a bumping `Version` as free insurance.
- Whether widening `queueIDs` widens the dropdown — predicted **yes** [I from M bytecode].
- ⚠ **`Loki.log` silence is NOT evidence of acceptance** on this surface (see §2.4a). A
  non-echoing response parses perfectly and is then discarded by the widget with no log line.
