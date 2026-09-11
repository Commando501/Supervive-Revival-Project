# S121 — LEADERBOARDS: dropdown vocabularies + entry field bindings (shipped assets only)

Method: `tools/extractor` (CUE4Parse) `bpdump` / `dump` / `rawfile` / `namesall` against the shipped
paks, plus a UTF-16 scan of `dumps/merged2.dump.exe`. No game launch, no injection, no RPM.
Every claim tagged **[M]** measured / **[I]** inferred / **[S]** speculative.

Asset root: `Loki/Content/Loki/UI/Widgets/FrontEnd/MainMenu/Leaderboard/` (18 assets, all enumerated).

---

## 0. The page is FOUR widgets, not one — and only two hit `/player-stats/leaderboard`

**[M]** `WBP_Leaderboard_Screens` (`bpdump … @props`) holds a `NotifyingWidgetSwitcher` with exactly
four children, driven by `WBP_UI_NavBar_TertiaryV2.ButtonData` (4 entries):

| tab | child widget name | class | per-instance override |
|---|---|---|---|
| DAILY | `LeaderboardDaily` | `WBP_UI_LeaderboardScreen_C` | *(none — CDO `Period = "daily"`)* |
| WEEKLY | `LeaderboardWeekly` | `WBP_UI_LeaderboardScreen_C` | **`Period (StrProperty) = weekly`** |
| RANKED | `RankedScreen` | `WBP_UI_RankedLeaderboardScreen_C` | `HasRegionSelector = True` |
| FRIENDS | `RankedFriends` | `WBP_UI_RankedLeaderboardScreen_C` | `OnlyFriends = True` |

**[M]** `Default__WBP_UI_LeaderboardScreen_C` → `Period (StrProperty) = daily`.

⇒ **[M] `period` has exactly TWO values in the shipped client: `daily` and `weekly`.**
**FRIENDS and RANKED are NOT `period` values** — they are a different widget class calling a
different manager.

---

## Q1 — the four vocabularies

### 1a. STAT dropdown → `statCode`  — **COMPLETE, 4 values**

**[M]** `WBP_UI_Leaderboard_ComboBox_Stats::ExecuteUbergraph` populates itself with
`GetKeysFromStringTable(<TableId>)` → loop → `AddOption(key)`, then `SelectOption("wins")`
(literal `EX_StringConst Value: wins`, twice: once for the option, once for the
`OnOptionSelected` broadcast).

**[M]** The table id is `/Game/Loki/UI/Widgets/FrontEnd/MainMenu/Leaderboard/ST_Leaderboard_Stats`
— it appears 3× as an inline `EX_TextConst` string-table id in the raw uasset
(`tools/extractor/out/raw/…/WBP_UI_Leaderboard_ComboBox_Stats.uasset`, offsets 3922 / 4379 / 5367)
and in the package's dependency path list at offset 2725.

**[M]** `ST_Leaderboard_Stats.KeysToEntries` (full table, 4 keys):

| `statCode` | UI label |
|---|---|
| `kills`   | `Kills (Single Game)` |
| `wins`    | `Total Wins` ← observed default |
| `damage`  | `Damage (Single Game)` |
| `healing` | `Healing (Single Game)` |

Key order above is the serialized order. **[M]** The combo's option order is `GetKeysFromStringTable`
order, i.e. the same table order.

### 1b. QUEUE dropdown → `queueId` — **BACKEND-DRIVEN; the LABELS are shipped**

**[M]** `WBP_UI_Leaderboard_ComboBox_Queues::ExecuteUbergraph` does NOT read a shipped list. It does:

```
GetPartyManager(self) -> GetPartyModel() -> GetQueueInfo()      // FLokiQueueInfo
for i in Queues:
    if (Queues[i].IsRanked || !ShowOnlyRankedQueues):
        if (Queues[i].ID != GetBotQueueID()):   AddOption(Queues[i].ID)
SelectOption(Queues[0-surviving].ID)            // default = first surviving entry's .ID
```
plus `ClearOptions()` + rebuild on the party model's `OnQueueInfoUpdated` delegate.

⇒ **[M] the queue vocabulary is whatever OUR backend serves in `QueueInfo.Queues[].ID`.**
We already serve `tutorialNew, training, practice, bots` (`server/internal/interactive/interactive.go:1187`).
`ShowOnlyRankedQueues` is a per-instance bool; **[M]** it is **not** set on the leaderboard screen's
instance (absent from `bpdump_WBP_UI_LeaderboardScreen_PROPS.txt`), so every served queue shows.
**[M]** The `Options` array on the leaderboard-screen instance is explicitly EMPTY (the
`default`/`deathmatch` pair visible on the two combo CDOs is an inherited
`WBP_UI_Common_ComboBox` default, present identically on the unrelated Region combo → not data).

**[M]** Label = `BPFL_Matchmaking::"Queue ID to Name"(id, bIsRanked, …)` →
`TextFromStringTable(ST_Parties, "queue." + id + (bRanked ? "-ranked" : "") + ".name")`, guarded by
`IsRegisteredTableEntry`; on a miss it falls back to `Format("queue.{id}.name"/"…description")`.
Raw literals confirmed in the uasset: `queue.default.name`, `queue.{id}.name`,
`queue.{id}.description`, `/Game/…/Party/ST_Parties`.

**[M]** `ST_Parties` label table (relevant rows; 63 keys total, `queue.*` shown):
`tutorialNew → Basic Training` · `training → Training Mode` · `practice → Practice Range` ·
`bots → Co-op vs. AI` · `default → Breach` · `duos → Duos` · `solo → Solos` · `trios → Trios` ·
`deathmatch → Arena` · `dropin → Warm-Up` · `customgame/customgames → Custom Game` ·
`tournament → Tournament` · `domination → Domination` · `prismabank → Prisma Party` ·
`rotating → Rotating` · `event → Event` · `dupes → Clone Squads` · `gstar → GSTAR - Duos` ·
`solodm → Solo Deathmatch` · `brdm → BR Deathmatch` · `local`/`test`/`practiceTest`/`temp1..3` ·
`tutorial-local`/`training-local` · ranked variants `default-ranked → Ranked Breach`,
`duos-ranked → Ranked Duos`, `deathmatch-ranked → Arena`, `tournament-ranked → Tournament` ·
CN-only: `goldhunter_ne`, `realgoldcup_ne`, `solo-bots`, `chinavskorea`, `holiday`, `armorydeathmath`.
⇒ **`tutorialNew` + `Basic Training` is exactly the observed pair.**

### 1c. HUNTER dropdown → `heroId` — **sentinel confirmed, and it is lowercase in the asset**

**[M]** `WBP_UI_ComboBox_Heroes::ExecuteUbergraph`
(`Loki/Content/Loki/UI/Widgets/FrontEnd/MainMenu/Shared/HeroComboBox/`):
```
AddOption("hero:all")                                  // EX_StringConst, literally lowercase
for id in BPFL_LokiAssets::"Get Heroes Asset List Sorted"(true):
    AddOption(Conv_PrimaryAssetIdToString(id))         // -> "Hero:<InternalName>"
if SelectedItemKey.IsEmpty(): SelectOption("hero:all")
```
`bEnableAllHunters (BoolProperty) = True` on the CDO **[M]**.

**[M]** the wire form is `Hero:All` while the asset literal is `hero:all`.
**[I]** mechanism: the widget stores the FString key; the screen converts with
`PrimaryAssetIDFromString(key)` and the FName-typed `Type`/`Name` re-serialize with the
case of the FName already interned (`Hero`, `All`). **⇒ treat `heroId` matching as
CASE-INSENSITIVE and accept both spellings.** Specific hero form is `Hero:<name>` where
`<name>` is the hero's `PrimaryAssetName` (== `InternalName`, per CLAUDE.md's S120 finding).

### 1d. `period` — clean scope statement

**[M]** Only two `period` strings exist as data: the CDO default `daily` and the
`LeaderboardWeekly` instance override `weekly`. **[M]** A UTF-16 scan of `.rdata` around the
query-param literals (`0x8b4cd00`–`0x8b4d000` in `dumps/merged2.dump.exe`) shows the URL is built
purely from format fragments — `/player-stats/leaderboard?queueId=` (`0x8b4cda0`), `&period=`
(`0x8b4cd80`), `&statCode=` (`0x8b4cd68`), `&heroId=` (`0x8b4cd50`), `&start=` (`0x8b4cd40`),
`&end=` (`0x8b4cd30`) — with **no adjacent period enum or value literals**. Sibling literal
`/player-stats/players/` at `0x8b4cd00`, error format
`Failed to fetch player stats: status [%d] error [%s]` at `0x8b4cc30`.
**Negative, scoped: I found no third `period` value anywhere in the 18 leaderboard assets, in
`ST_Leaderboard_*`, or in that `.rdata` neighbourhood.**

### 1e. The other two tabs use the MMR endpoints (settles the parent's question)

**[M]** `WBP_UI_RankedLeaderboardScreen::ExecuteUbergraph`:
* `OnlyFriends` → `GetMMRManager(self)->GetFriendLeaderboard(SelectedQueue, OnSuccess, OnError)`
* else → `GetMMRManager(self)->GetLeaderboard(Start=1, End=50, SelectedQueue, SelectedRegion, OnSuccess, OnError)`
* defaults: `SelectOption("default")` for queue, `SelectOption("ALL")` for region.

**[M]** matching `.rdata` literals in `dumps/merged2.dump.exe`:
`/mmr/leaderboard/friends` @ `0x8b45848` · `/mmr/leaderboard?start=%d&end=%d&queueId=%s&region=%s`
@ `0x8b45880` · `/mmr/player-ratings/` @ `0x8b3f078` · `/mmr/player/` @ `0x8b45910` ·
struct name `FriendLeaderboardRequest` @ `0x8aae528` · error strings
`No friends present when getting leaderboard manager` / `No social manager when getting leaderboard manager`.

**[M]** REGION vocabulary = `ST_Leaderboard_Regions.KeysToEntries`:
`ALL → All Regions` · `NA → North America` · `EU → Europe` · `SA → South America` ·
`APNE → Asia Pacific` · `friends → Friends`.
⚠ **[M]** `friends` is a key in the REGION table, not in the stat table and not a `period`.

---

## Q2 — what the UI actually binds off the response

### 2a. `Update Leaderboard(Leaderboard: FLokiPlayerStatsLeaderboard)` — the empty-state gate

**[M]** (`bpdump WBP_UI_LeaderboardScreen "Update Leaderboard"`):
1. `LeaderboardRankings.ClearChildren()`
2. **`if Leaderboard.Entries.Num() > 0`** → `for i in Entries: Create Leaderboard Row(i, Entries[i])`
3. **else** → creates `WBP_UI_Leaderboard_NoEntries_C`, `AddChildToGrid(row 0, col 0)`,
   `SetColumnSpan(3)`, padding 16. Its text (raw uasset) is:
   `No one has claimed a spot on this leaderboard...yet. Be the first!`
4. `Reset Time = FromUnixTimestamp( roundUpToMinute( UtcNow + MakeTimespan(0,0,0, Leaderboard.ExpirationTimeSeconds, 0) ) )`
   — literally `t - (t % 60) + 60` on the unix seconds. **⇒ `ExpirationTimeSeconds` IS the
   `RESET IN` countdown source [M].** Tooltip = the absolute local time
   (`AsTimeZoneDateTime`, or `FormatChinese24HDateTime` on the CN publisher branch).

**[M] There is NO `Rank > 0` filter and no per-row skip of any kind.** Every element of `Entries`
becomes a row, in array order (grid Row = array index — **the array order is the display order,
`Rank` is only text**).

### 2b. `Create Leaderboard Row(Index, Entry)` — the 3 columns

**[M]** three widgets are created and added to `LeaderboardRankings` at `Row = Index`:

| col | widget | binding |
|---:|---|---|
| 0 | `WBP_UI_LeaderboardEntry_Text_C` | `Text = Format("{rank}", rank = Conv_IntToInt64(**Entry.Rank**))`; `Rank` int prop = `Entry.Rank` |
| 1 | `WBP_UI_LeaderboardEntry_Text_C` | `Text = Conv_IntToText( **FCeil(Entry.Value)** )`; `Rank` int prop = `Entry.Rank` |
| 2 | `WBP_UI_LeaderboardEntry_PlayerName_C` | `SetStructurePropertyByName("Leaderboard Ranking", **Entry**)` and `SetNamePropertyByName("Hero Name Override", PrimaryAssetIDFromString(HeroCombo.SelectedItemKey).PrimaryAssetName)` |

⚠ **[M] SCORE is `FCeil(Value)`** — `Value` is a float but is rendered as a ceiled integer with
grouping (`Conv_IntToText(…, 1, 324)`). Serve `12` not `12.4` unless you want `13`.
⚠ **[M] the header row `LeaderboardRankingsTitle` is col0 `RANK`, col1 `SCORE`, col2 `PLAYER`** —
matches.

### 2c. `WBP_UI_LeaderboardEntry_PlayerName` — PlayerID resolve, HeroName, HeroCounts

**[M]** `Set Player Display Name`:
```
model = GetPlatformPlayerManager()->GetPlayer(**Leaderboard Ranking.PlayerID**)
name  = model->DisplayNameAndTag()
PlayerNameText->"Set Text"( name.IsEmpty() ? <TextConst placeholder> : name , **Entry.Rank** )
```
and the ubergraph then **binds `OnChangeDisplayName` to that model's name-changed delegate** and
re-runs on fire.
**[I]** ⇒ `PlayerID` is resolved ASYNCHRONOUSLY through `ULokiPlatformPlayerManager`, exactly the
shape that produces the project's already-measured
`GET /iam/v4/public/namespaces/supervive/users/{id}` resolve (CLAUDE.md S118 recorded that same
resolve firing +276 ms after a pushed `requestFriendsNotif` with a fabricated id).
**Not measured here:** the actual HTTP verb/route `GetPlatformPlayerManager` issues — that is a
native manager, invisible to `bpdump`. **[S]** it may also use a bulk/basic user-info route.
⚠ **Practical consequence: a row with an unresolvable `PlayerID` still renders — it just shows the
placeholder text. So the PLAYER column is not a hard dependency for getting rows on screen.**
⚠ **[M]** The ubergraph gates the whole display-name path on `!Leaderboard Ranking.PlayerID.IsEmpty()`
— **an empty `PlayerID` skips the name lookup entirely.**

**[M] `Entry.HeroName`** is passed to `BPFL_LokiAssets::FindHeroAssetByInternalName(HeroName)`;
`IsValidPrimaryAssetId` on the result drives `WBP_UI_LeaderboardEntry_HeroName`'s
`SetVisibility` (design-time text is the placeholder `(???)`).

**[M] `Entry.HeroCounts` DOES drive UI.** The ubergraph branches on
`Hero Name Override != FName("all")` (literal `EX_NameConst Value: all`):
* override **≠ all** (a specific hunter picked) → `Overlay_HeroPortrait.ClearChildren()` then ONE
  `Add Hero Portrait(<selected>)`;
* override **== all** → `Map_Keys(**Leaderboard Ranking.HeroCounts**)` → **one
  `Add Hero Portrait(key)` per key**, each a `WBP_UI_LeaderboardEntry_HeroPortrait_C` (48×48) with
  `SetNamePropertyByName("Hero Name", key)`, fanned out with a 50 px right-padding stagger.
  **[I]** the `EX_SwitchValue` case terms are not printed by the dumper, so which of
  `Hero Name Override` / `Entry.HeroName` feeds the single-portrait branch is inferred from the
  branch condition, not read.
⇒ **`HeroCounts` keys must be hero `InternalName`s (FName); the VALUES (`int32`) are not read by
this widget** — only `Map_Keys` is called. **[M]**

### 2d. The staleness gate — echo your request back or the page re-fetches forever

**[M]** `Current Leaderboard Is Stale` returns
```
(PrimaryAssetIDFromString(HeroCombo.SelectedItemKey).PrimaryAssetName != Leaderboard.**HeroName**)
 OR (Leaderboard.**StatCode**  != StatCombo.SelectedItemKey)
 OR (Leaderboard.**QueueID**   != QueueCombo.SelectedItemKey)
 OR (UtcNow - LeaderboardLastUpdated > MakeTimespan(0,0,0,60,0))
```
⚠ **BACKEND REQUIREMENT [M]: the response MUST echo `QueueID`, `StatCode` and `HeroName` exactly as
requested** (`HeroName` = the FName `All`, not `Hero:All`), or the screen treats every result as
stale. Note `Period` and `Start`/`End` are NOT compared. The 60 s term means a re-open after 60 s
always refetches — that is normal, not a bug.

### 2e. Request construction and the refresh button

**[M]** `WBP_UI_LeaderboardScreen::ExecuteUbergraph`:
`GetPlayerStatsManager(self)->GetLeaderboard(QueueCombo.SelectedItemKey, **Period**,
StatCombo.SelectedItemKey, PrimaryAssetIDFromString(HeroCombo.SelectedItemKey),
**Start = MakeLiteralInt(1)**, **End = MakeLiteralInt(25)**, OnSuccess="On Leaderboard",
OnError="On Leaderboard Error")` — matches the observed `start=1&end=25` exactly.
The call is gated on `!QueueKey.IsEmpty() && !StatKey.IsEmpty() && !HeroKey.IsEmpty() &&
IsValidPrimaryAssetId(heroId)`; it also broadcasts `On Filters Updated(hero, stat, queue)`.

**[M]** `Update Timer` (on `Tick`): `WidgetSwitcher_ResetState.SetActiveWidgetIndex(
SelectInt(0, 1, ResetTime > UtcNow))` — index 0 = the `00:00:00` countdown, index 1 = the
`REFRESH` button. Countdown text is `{HH}:{MM}:{SS}` with `HH = Days*24 + Hours`, 2-digit padded.
⇒ **[I] serving `ExpirationTimeSeconds = 0` makes the page show REFRESH instead of a countdown.**

### 2f. Self-entry

**[M]** The daily/weekly screen has **no** self-entry / "jump to me" behaviour — there is no such
widget, function or property on `WBP_UI_LeaderboardScreen`.
**[M]** The RANKED/FRIENDS screen does: `JumpToSelfBtn`, `BP_IsItemVisible`,
`BP_ScrollItemIntoView`, plus a `CommonListView EntriesList` whose `EntryWidgetClass` is
`WBP_UI_RankedLeaderboardEntry_C` and whose item objects are `WBP_UI_LeaderboardEntryObject_C`
(`Entry` struct + `OnNameChanged`/`OnPlayerNameChanged`). Its columns are `RANK / PLAYER / RANK POINTS`.
⇒ `WBP_UI_LeaderboardEntryObject` is **ranked-only**; the daily/weekly path builds grid children
directly and never uses it. **[M]**

---

## Files produced (all under this directory)

`leaderboard_names.txt` (namesall over the 18 assets), `LBSCR_*.txt` (LeaderboardScreen functions),
`PN_*.txt` (PlayerName entry functions), `RANKED_*.txt`, `HEROES_Ubergraph.txt`,
`QUEUES_GetDisplayTextForSelectedOption.txt`, `BPFL_QueueIDToName.txt`,
`bpdump_*_PROPS.txt`.
Side effect of running the extractor (its output dir is hard-coded): new
`bpdump_*.txt` / `ST_Leaderboard_*_uasset.json` / `ST_Parties_uasset.json` / `raw/…` files under
`tools/extractor/out/`. None are `DA_Mission*`, so `gen_missions_catalog.py` is unaffected.
