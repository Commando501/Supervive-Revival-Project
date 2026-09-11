# S121 — leaderboard / player-stats response deserialization (static, `dumps\merged2.dump.exe`)

Image: `merged2.dump.exe`, file offset == RVA, ImageBase `0x7FF6AF000000`. `.text` 54.90 % decrypted.
**Every address cited below was checked `page_decrypted=True`** (14/14). Scripts + raw dumps in this dir
(`img.py`, `xref.py`, `jconv.py`, `envdetect.py`, `uht.py`, `dis-*.txt`).

## Q1 — TOP-LEVEL. No envelope. No wrapper key. [M]

`/player-stats/leaderboard?queueId=` is built by **`0x58425f0`** (contains the `0x5842674` lea),
verb `"GET"` (`.rdata 0x79eaaf8`, built at `0x58428d2`), dispatched at `0x5842908 -> 0x57eebb0`.
Callbacks are passed in by its caller `0x58423d0`.

The response path is Loki's generic **`Query<T>`** template (`Query.h`), instantiated for
`FLokiPlayerStatsLeaderboard` at **`0x5809760`**:

```
058099ea  call [rax+0x58]        ; IHttpResponse::GetResponseCode
058099ef  lea  ecx,[rax-0xc8] / cmp ecx,0x63 / ja 0x5809c45   ; accept 200..299 only
05809a02  lea  rdx,[rbp+0x40]    ; temp FString
05809a08..05809a3d               ; zero-init OutStruct at [rbp-0x20], exactly 0x60 bytes
05809a44  call [rax+0x60]        ; IHttpResponse::GetContentAsString  -> rax = &FString(body)
05809a47  xor  r9d,r9d           ; SkipFlags = 0
05809a4a  mov  byte [rsp+0x20],sil ; bStrictMode = false
05809a4f  mov  rcx,rax           ; <<< JsonString = THE RAW BODY, untouched
05809a52  lea  rdx,[rbp-0x20]    ; OutStruct
05809a56  xor  r8d,r8d           ; CheckFlags = 0
05809a59  call 0x57e9220         ; JsonObjectStringToUStruct<FLokiPlayerStatsLeaderboard>
```

**Zero instructions between `GetContentAsString` and the converter.** No `GetObjectField`,
no `TryGetField`, no string literal, no sub-object.

`0x57e9220` is the stock engine template — identified by its own static log records, which name
the file and line verbatim: `0x8b4fde8` = *"JsonObjectStringToUStruct - Unable to parse json=[%s]"*
`JsonObjectConverter.h:282`, `0x8b4fe08` = *"…Unable to deserialize…"* `:287`. Body:
`0x1185580` (TJsonReaderFactory::Create) → `0x11695b0` (FJsonSerializer::Deserialize) →
`0x54d0fe0` (`FLokiPlayerStatsLeaderboard::StaticStruct`, singleton cell `.data 0xa030590`) →
`0x1f99e20` (`FJsonObjectConverter::JsonObjectToUStruct`) with **`rcx = lea [rsp+0x60]`, the
TSharedRef straight out of `Deserialize`.**

### Positive control — the method DOES find an envelope [M]
Generic detector (`envdetect.py`): over **152** `JsonObjectToUStruct` call sites, flag any rip-rel
`lea` to a printable `.rdata` wide string in the window between the JSON parse and the converter.
It fires on exactly **1 of 152**: `FAccelByteModelsPartyNotif`, fn `0x4b02c80` —
`0x4b03095 lea rdx,[0x783c540] W"payload"` → `0xfa11d0` (FString ctor) → `0x1178630`
(`FJsonObject::TryGetObjectField`) → sub-object → converter at `0x4b032d2`.
It reports **0 key literals** for all four Loki structs below.

## Q2 — both also TOP-LEVEL [M]

Same `Query<T>` shape, same three-arm error ladder.

| endpoint | URL builder | Query handler | deserializer | struct | shape |
|---|---|---|---|---|---|
| `/player-stats/leaderboard` | `0x58425f0` | `0x5809760` | `0x57e9220` | `FLokiPlayerStatsLeaderboard` | raw body, top-level |
| `/mmr/leaderboard` (+`/friends`) | `0x57b0f50` | `0x5783420`, `0x57839a0` | `0x5760940` | **`FLeaderboard`** | raw body, top-level |
| `/player-stats/players/{id}` | `0x5845880` | `0x581eb00` | `0x57ea620` | **`FPlayerStats`** | raw body, top-level |

MMR: `0x578371c call [rax+0x60]` → `0x5783726 mov rcx,rax` → `0x5783730 call 0x5760940`.
PlayerStats: `0x581eb59 call [rax+0x60]` → `0x581eb64 mov rcx,rax` → `0x581eb6e call 0x57ea620`.
Calibration: `FPlayerProgression` (`0x57ea020`, caller `0x5834130`) has the identical shape — and
that route is already MEASURED top-level by this project.

**Linkage caveat [I]:** `FLokiPlayerStatsLeaderboard` is deserialized in exactly one place image-wide
and `/player-stats/leaderboard` is the only such URL; the join is by uniqueness + exact field/query-param
correspondence, not by tracing the TFunction binding (the callbacks are heap lambdas, no vtable slot).

## Q3 — NO post-deserialization validation. [M]

Success path `0x5809b91` (leaderboard) and `0x581ec71` (player stats) are byte-identical in shape:
`inc [r14+0x14]` (reentrancy lock) → walk the subscriber array backwards (16-byte entries, `Num` at
`+8`) → `call [rax+0x60]` with **`rdx = &OutStruct`** → `dec [r14+0x14]` → compact if any returned false.

Between `test bl,bl` (converter result) and the broadcast there is **nothing**: no `Entries.Num()`
test, no `Start`/`End` range check, **no `QueueID`/`Period`/`StatCode` echo-match**, no `Version` gate
(`FLokiPlayerStatsLeaderboard` has no Version field; `FPlayerStats.Version@0x10` is never compared here).
The only gates are pre-deserialization: `bWasSuccessful`, then HTTP `200..299`.

Error ladder (all three log at Warning, so **`Query.h` lines are a free instrument**):
`Query.h:194` *"Could not connect. Query: %s: %s"* → code **-1**;
`Query.h:204` *"Bad status(%d) on Query…"* → code = status, **suppressed for 404 and 304**;
`Query.h:212` *"Deserialization failure on Query: %s: %s."* → code **-2**.

**One request-side gate worth knowing [M]:** `0x58423ea cmp byte [rcx+0x59],0 / jne <return>` and
`0x584240c mov byte [rcx+0x59],1` — an in-flight guard; a second fetch while one is outstanding is
silently dropped. It is cleared (`0x5838c8c`, `0x583c978`, same TU), so it is not one-shot.

**Coverage behind the negative:** 74 `Query.h:212` records exist; 61 have a `.text` lea site, so 13
`Query<T>` handlers live in undecrypted pages — but all three targets are decrypted and fully read.
Validation inside a *subscriber* (manager/UI) is out of scope of this pass: subscribers are
runtime-bound heap lambdas and cannot be statically enumerated.

## Q4 — offsets. CALIBRATION PASSED. [M]

`FStructParams` in this build lives in **`.data`** (~`0x9c4xxxx`), not `.rdata`, and packs
`+0x28 u16 NumProperties, +0x2a u16 SizeOf, +0x2c u16 AlignOf, +0x30 u32 StructFlags`
(the stock `int32 NumProperties / uint32 SizeOf` reading does **not** decode). Property records are
stock `FPropertyParamsBaseWithOffset` (`ArrayDim u16 @+0x30, Offset u16 @+0x32`).

**Calibration (mandated):** `FPlayerProgression` params `@0x9c421d0` → SizeOf **0x178** and
`ID@0x0, Version@0x10, Matches@0x18, MissionInfo@0x68, AccountPass@0xe8, HeroMastery@0x148,
LoginReward@0x158, EventProgression@0x168` — **all 8 exact, PASS**.
`FHeroMasteryProgress` `@0x9c42128` → SizeOf **0x70**, `HeroId@0x60` — **PASS**;
its `Level@0x04, XP@0x08, UnclaimedRewards@0x10` are correctly reported on the **super**
`FProgressionTrackLevel` (`@0x9c420f0`, SizeOf 0x60) — **PASS**.
⚠ **One caveat:** for `Bool` properties the `Offset` field reads `1` (`Cleared` reads 1, not 0xC) —
`FBoolPropertyParams` has extra members. **None of the structs below contains a bool.**
⚠ UHT emits container **inner** params (PropertyFlags == 0) *before* the real property, with a
meaningless Offset. Read the last, flags != 0 entry per name.

### `FLokiPlayerStatsLeaderboard` — params `@0x9c41600`, **SizeOf 0x60**, Align 8
| off | name | type |
|---|---|---|
| 0x00 | Period | FString |
| 0x10 | StatCode | FString |
| 0x20 | HeroName | FName |
| 0x28 | QueueID | FString |
| 0x38 | Entries | TArray\<FLokiPlayerStatsLeaderboardEntry\> |
| 0x48 | Start | int64 |
| 0x50 | End | int64 |
| 0x58 | ExpirationTimeSeconds | int32 |

### `FLokiPlayerStatsLeaderboardEntry` — params `@0x9c415c8`, **SizeOf 0x70**, Align 8
| off | name | type |
|---|---|---|
| 0x00 | PlayerID | FString |
| 0x10 | Rank | int32 |
| 0x14 | Value | float |
| 0x18 | HeroName | FName |
| 0x20 | HeroCounts | TMap\<FName,int32\> (0x50 B) |

Both close exactly, and both are **independently cross-confirmed by the code**: the callback
zero-inits exactly **0x60** bytes at `0x5809a08..0x5809a3d`, and the `Entries` destructor loop at
`0x5809c10` strides exactly **0x70** freeing an FString at elem+0x00 and a TMap at elem+0x20.

### bonus (same method, same calibration)
`FLeaderboard` `@0x9c377c8` SizeOf **0x68**: `Start@0x00 i32, End@0x04 i32, QueueID@0x08 FString,
Role@0x18 FString, Entries@0x28 TArray<FLeaderboardEntry>, SelfEntry@0x38 FLeaderboardEntry`.
`FLeaderboardEntry` `@0x9c37790` SizeOf **0x30**: `PlayerID@0x00 FString, Rank@0x10 enum(ERank, u8),
Rating@0x14 i32, Placement@0x18 i32, Percentile@0x1c float, AvatarID@0x20 FPrimaryAssetId`.
`FPlayerStats` `@0x9c41590` SizeOf **0x68**: `ID@0x00 FString, Version@0x10 i32,
StatsByQueue@0x18 TMap<FString,FPlayerQueueStats>`.
`FPlayerQueueStats` SizeOf **0x60**: `ID@0x00, StatsByHero@0x10 TMap<FString,FPlayerHeroStats>`.
`FPlayerHeroStats` SizeOf **0xa8**, 21 real props (`GamesPlayed@0x00`, `Placements@0x08
TMap<int32,int32>`, `TimePlayedSeconds@0x58`, `Kills@0x5c`, … see `uht-heroStats.txt`).
