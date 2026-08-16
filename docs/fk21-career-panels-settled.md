# FK-21 SETTLED — the CAREER panels were never "authentic empties"

**S123, 2026-08-15.** Backend-only. No shim, no injection, no `.text` write, no game relaunch.
Four arms flown against a single client that had been up **3h15m**.

> **One line:** Career → Stats, → Ranked and → History were each empty because **we served nothing**,
> and each renders the moment it is fed. The last of the three — History — is confirmed here.

---

## 0. The belief, and what was actually wrong with it

FK-21 challenged `docs/endpoints.md:84` (*"Career→History (empty = correct for new account)"*) and
`docs/coverage-audit-s101.md`'s LIVE list (*"CAREER stats/ranked/history (authentic empties)"*).

Its argument was that the account **is not new** — `Saved/ImageCaches` holds 56 JPGs dated
Nov 2024 – Aug 2025, and `UserSettings.ini` records `HasPlayedTutorial=True`,
`HasSeenRankedPopup=True`, `HasSeenReturningPlayerModal=True` — so "authentic empty" was inferred,
never measured, and a broken deserialization would look identical.

⚠ **Be precise about which half was wrong, because half of it was already answered.** S119 built
`handleMatchHistory` and, with it, a live discriminator: `MatchHistoryManager+0x68` reads back our
exact served `Version`, which proves the document parsed. So for History, *"broken deserialization"*
was **already excluded** before this session, and that finding stands — at baseline the manager held
our player id with the gate open.

**What was never shown, for any of the three panels, is that they are LIVE.** An empty panel fed by
a parsing document is still consistent with "this surface is dead". That is what this settles.

| panel | endpoint | settled | evidence |
|---|---|---|---|
| Career → Stats | `GET /player-stats/players/{id}` | S121 | MATCHES 12 · KILLS 40 · MAX DAMAGE 21,400 · TIME PLAYED 2h 20m |
| Career → Ranked | `GET /mmr/player-ratings/{id}/rank` | S122 | `GOLD I` · `1,850 RP` |
| **Career → History** | `GET /match-history/players/{id}` | **S123** | **this document** |

---

## 1. The model [M] — read live, not from the usmap

`tools/re/struct_layout.py <pid> <base> MatchHistoryEntry …` against the running client (read-only
RPM). Offsets are `Offset_Internal`.

```
FMatchHistoryEntry                                FLokiPlayerMatchStats (38 fields, 0x94)
  +0x000 FString   ID                               +0x00 int32 Kills          +0x54 float DamageDone
  +0x010 FDateTime MatchStart                       +0x0C int32 Deaths         +0x58 float HeroDamageDone
  +0x018 FDateTime MatchEnd                         +0x10 int32 Assists        +0x5C float DamageTaken
  +0x020 FString   QueueID                          +0x14 int32 Knocks         +0x60 float HeroDamageTaken
  +0x030 bool      IsRanked                         +0x2C int32 Revives        +0x64 float EffectiveDamageDone
  +0x038 FString   GameVersion                      +0x44 int32 CreepKills     +0x68 float HeroEffectiveDamageDone
  +0x048 int32     NumTeams                         +0x48 int32 GoldFromTreasure  +0x6C float EffectiveDamageTaken
  +0x04C int32     NumParticipants                  +0x4C int32 GoldFromMonsters  +0x70 float HeroEffectiveDamageTaken
  +0x050 FPrimaryAssetId       HeroAssetID          +0x50 int32 GoldFromEnemies   +0x74 float ArmorMitigatedDamage
  +0x060 FMatchHistoryTeamInfo TeamInfo             +0x7C float HealingGiven      +0x78 float ShieldMitigatedDamage
  +0x078 FLokiPlayerMatchStats PersonalStats        +0x84 float HealingReceived
  +0x10C int32     CharacterLevel
  +0x110 TArray<FArmoryReward> ArmoryRewardsEarned
  +0x120 ERank     StartingRank
  +0x124 int32     StartingRating

FMatchHistoryTeamInfo      int32 Placement · float SurvivalDuration · TArray<FMatchHistoryTeammateInfo> Teammates
FMatchHistoryTeammateInfo  FString PlayerID · FPrimaryAssetId HeroAssetID
FArmoryReward              FPrimaryAssetId AssetId · int32 Quantity · bool Extracted · bool Boosted · float BoostFactor
```

⚠⚠ **The usmap could not have answered the two questions that mattered.** FK-14 measured that the
extractor reads a property's inner/enum **inline at `FField+0x80`**, past the end of the object, so
it captures whatever `FField` the allocator placed next. That defect covers exactly `Matches`' array
inner and `StartingRank`'s enum. Both were read live at the FK-14-corrected offsets
(`FArrayProperty::Inner *(+0x78)`, `FEnumProperty::Enum *(+0x78)`), by
`scratchpad/enum_of_prop.py`.

★ **`StartingRank` is `ERank` [M]** — enum object named live, 29-entry value table read from
`UEnum::Names`. `Gold1` is index **12**, i.e. a real member, which matters because `"Gold1"` is the
one ERank string this project had already measured the client accepting (S121, `/mmr/leaderboard`).

---

## 2. The arms

Readout: **`tools/re/matchhistory_readout.py`** (new) — reads the parsed `FMatchHistory` off the
live `UMatchHistoryManager`: `ID` at `+0x58`, `Version` at `+0x68`, `Matches` at `+0x70`, and each
entry's fields. Read-only RPM.

| arm | `Version` | `Matches.Num` | `TeamInfo.Placement` | `StartingRank` | canaries |
|---|---|---|---|---|---|
| A — off (baseline) | 1786853586 | 0 | — | — | 0/0/0/0 |
| B — `minimal` | 1786854166 | **1** | 0 *(unserved)* | 0 = Unranked | 0/0/0/0 |
| C — `full` | 1786854383 | **1** | **1** *(served)* | **12 = Gold1** | 0/0/0/0 |
| D — `full` + `Effective*` | 1786854605 | **1** | 1 | 12 | 0/0/0/0 |

Canaries = `LogJson … Unable to import` / `Deserialization failure` / `Invalid response received` /
`Fatal`. All zero in every arm; the game stayed alive throughout.

**Arm B** read back every served field verbatim out of the client's own parsed struct —
`ID 'revival-match-0001'`, `QueueID 'tutorialNew'`, `IsRanked 0`, `GameVersion '1.0.0'`,
`NumTeams 16`, `NumParticipants 64`, `CharacterLevel 12`, `StartingRating 1850`.
★ The fields `minimal` does **not** serve sat at their defaults. That remainder is the built-in
negative control: it is what separates *"our document landed"* from *"something else wrote here"*.

**B vs C is a clean single-variable pair** — only the five risky fields differ; the two observable
ones both moved and nothing else changed. Since `FJsonObjectConverter` rejects the **whole** document
on one wrong-typed matched key, surviving with `Num=1` means all five were accepted: the `ERank`
enum-string form, the nested `TeamInfo` (itself containing an array of structs), and
`HeroAssetID` / `PersonalStats` / `Teammates`.

---

## 3. ★★★★★ The render half — screenshot-confirmed, field by field

```
VICTORY                       <- TeamInfo.Placement 1
Basic Training | 1/16         <- QueueID "tutorialNew" via Queue_ID_to_Name; Placement 1 of NumTeams 16
Aug 15, 2026, 10:26:21 PM     <- MatchStart 2026-08-16T03:26:21Z, converted UTC -> LOCAL
(18:00)                       <- MatchEnd - MatchStart
[hero portrait]               <- HeroAssetID "Hero:reshealer" RESOLVED
ALLY  Reviver#6612            <- TeamInfo.Teammates[0], PlayerID resolved to a display name
KILLS 7 · KNOCKS 11 · REVIVES 5 · ASSISTS 9 · MINIONS KILLED 38 · MAX KILL STREAK 4 · MAX KNOCK STREAK 3
GOLD FROM TREASURE 1,200 · GOLD FROM MINIONS 2,400 · GOLD FROM ENEMIES 900
HEALING GIVEN 5,100 · HEALING RECEIVED 3,300 · HEALING TOTAL 8,400 (DERIVED) · HEALING TO SELF 0
```

The consumer family is nine widgets, all shipped and extracted: `WBP_UI_MatchHistoryScreen` (a nav
tab inside `WBP_ProfileScreen`), `…Listing`, `…Entry`, `…Ally`, `…DetailedStats`,
`…DetailedStatIntegerEntry`, `…PreviewStat`, `…StatsHeader`, plus `WBP_ProfileScreen`.

---

## 4. ★★ Two findings that generalise beyond this row

### 4a. `TeamInfo.Placement` is 1-INDEXED — the opposite of its sibling

It rendered `1/16` from `Placement: 1`. Meanwhile S121 measured
`FPlayerHeroStats.Placements` on `/player-stats/players/{id}` as **ZERO**-indexed (key 0 == 1st
place), confirmed there by a pre-registered prediction.

⇒ **Two placement fields, one backend, opposite conventions. Do not carry either across.**

★ It was only discriminating because the flight served `Placement 1` against `NumTeams 16`. A
1-of-1 tutorial-shaped row renders identically under both conventions and would have proven nothing.
The non-degenerate values were chosen in advance for exactly this reason.

### 4b. The damage tiles read `Effective*`, never the raw `Damage*` — 5/5

First `full` flight served only the four raw `Damage*` fields, and **every damage tile rendered 0**,
while `HEALING GIVEN` / `RECEIVED` — same struct, same `float` type — rendered correctly.

★ **That asymmetry is the whole clue: healing is the one stat with no `Effective` variant**, so it
is the only one whose raw field is what the UI reads.

Re-flown with raw and effective **deliberately distinct**, so the tiles discriminate:

| tile | rendered | raw served | effective served | reads |
|---|---|---|---|---|
| TOTAL DAMAGE DEALT | 18,000 | `DamageDone` 21,400 | `EffectiveDamageDone` 18,000 | effective |
| DAMAGE TO HUNTERS | 13,100 | `HeroDamageDone` 15,200 | `HeroEffectiveDamageDone` 13,100 | effective |
| TOTAL DAMAGE TAKEN | 16,700 | `DamageTaken` 19,800 | `EffectiveDamageTaken` 16,700 | effective |
| DAMAGE FROM HUNTERS | 11,300 | `HeroDamageTaken` 12,600 | `HeroEffectiveDamageTaken` 11,300 | effective |
| SHIELDED DAMAGE | 2,600 | — | `ShieldMitigatedDamage` 2,600 | mitigated |

⇒ the four raw `Damage*` fields are **not read by this panel at all**. [S] They may still drive the
end-of-game screen; untested. `ArmorMitigatedDamage` is served and appears nowhere on this panel.

⚠ **Label ≠ field name, twice:** `MINIONS KILLED` ← `CreepKills`, `GOLD FROM MINIONS` ←
`GoldFromMonsters`. Read the mapping; do not assume it.

---

## 5. ⚠ Blast radius — this endpoint is not confined to Career → History

[M] `tools/extractor/out/bpdump_Get Number of Games Played.txt`
(`Comp_MainMenu_Onboarding_C`, 11 statements, fully decoded):

```
cv = GetConsoleVariableIntValue("Cheat.Onboarding.MatchHistoryCount")
if (cv >= 0) return cv
return GetMatchHistoryManager()->GetMatchHistory().Matches.Num()
```

`Matches.Num()` **is the onboarding component's games-played count**, and that component also owns
`Should Show Returning Player Modal`; its `On Match History Updated` handler jumps straight into the
component's ubergraph. ⇒ serving N rows makes the client believe the account has played N games.
`AGS_MATCH_HISTORY_COUNT` bounds it; the default of 1 keeps the perturbation minimal.

★ It also names a control that needs **no backend at all**: `Cheat.Onboarding.MatchHistoryCount` is
a cvar, and FK-13 established cvars as a shim-free channel settable from `[ConsoleVariables]` in the
user `Engine.ini`. ⚠ It may be inert — the name is `Cheat.*` and `DISABLE_CHEAT_CVARS` is a hard
`(UE_BUILD_SHIPPING || …)` `#define`; CLAUDE.md records which cvars carry `ECVF_Cheat` as **not
enumerated**, so a null from it would be uninterpretable until that is checked.

---

## 6. ⚠ Three instrument artifacts, all caught before publication

**(a) The archetype trap — a 5th member of the class-lookup blind-spot family.**
Before the screen was opened, RPM showed exactly **one** live `WBP_UI_MatchHistoryEntry_C` with
`Visibility = 4`, which reads as "a row is rendered". It was the widget-tree **template** carrying a
design-time value. What caught it: `MatchHistoryScreen` and `ProfileScreen` had **0** activations in
the entire session log. ⇒ **before reading a widget's state, prove its screen was ever built.**
Joins the family CLAUDE.md records for `obj_by_class.py` (substring), `cheat_reach_probe.py`
(endswith), `class_props.py` (class-of-class) and `bpframe_readout.py` (first match).

**(b) ★ NEW VARIANT — the grep WINDOW is part of the instrument.**
`grep -B2 -A3 match-history` over `capture.log` paired a request with a **neighbouring** request's
`User-Agent` and read as `supervive-loadout-shim` — i.e. *"the game never refetched"*. Widening to
`-A 12` gave the true pairing: `Loki/UE5-CL-0`. The documented User-Agent rule says *filter by UA*;
it does not say *pair each request with its OWN header block*, and a narrow window silently violates
that while looking like compliance.
★ Defusal worth reusing: verification curls were given the User-Agent
**`fk21-verify-NOT-THE-GAME`**, so our own traffic can never be mistaken for the client's.

**(c) The verifying command is an instrument too.** A `grep -o '\\|'` check reported zero escaped
pipes in a table row that has two, which briefly read as "the markdown is malformed"; and a
follow-up structural check hard-coded `pipes == 3`, which flagged the 3-column summary table as
broken. Both were the checker's fault, both caught in one step, nothing wrong was published.

**(d) One readout recorded as UNINTERPRETABLE rather than negative.** The onboarding
`CallFunc_Get_Number_of_Games_Played_ReturnValue` reads **0** on the live instance (HAS-RUN 59) —
but it is a per-execution ubergraph scratch slot **whose value is also the default**, so
"re-evaluated and got 0" and "holds a value from a run predating our document" cannot be separated.

---

## 7. How to reproduce

```powershell
# Knob is OFF by default and OFF is byte-identical to the pre-S123 payload.
$env:AGS_MATCH_HISTORY = 'minimal'     # then 'full'
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags
# restart ags; the client's resync refetches this endpoint within ~40 s — NO relaunch needed
python tools\re\matchhistory_readout.py <game-pid> <module-base-hex>
```

Then open **CAREER → HISTORY** in the client. ⚠ If the page is already open it must be **rebuilt**
(navigate away and back) — this project's standing rule for every feed-driven surface.

**Knobs** (`server/internal/interactive/matchhistory.go`):
`AGS_MATCH_HISTORY=off|minimal|full` · `AGS_MATCH_HISTORY_COUNT=N` · `AGS_MATCH_HISTORY_HERO=<name>`.

⚠ **Fly `minimal` before `full`.** If `full` goes first and the panel stays blank, the result cannot
distinguish "History does not render" from "one of the five risky fields sank the document" — and
this endpoint fails silently.

**Refetch without an ags restart:**
`lobby.NotifyResource(playerID, "/match-history/players/"+playerID, interactive.MatchHistoryVersion(playerID), "label")`.
⚠⚠ `push.go`'s note that *"any positive value works"* for this resource is **stale** — it was true
when `/match-history` was an empty catch-all, and it stopped being one when `handleMatchHistory` was
written. The document now carries a wall-clock-seeded `Version` (~1.79e9), so a push of `Version 7`
is the documented **too-low** case and is silently ignored.

---

## 8. Still open

- The four raw `Damage*` fields have no known consumer. [S] The end-of-game screen is the candidate.
- `ArmoryRewardsEarned` is served **empty**: `FArmoryReward.AssetId` is an `FPrimaryAssetId` for a
  cosmetic and no measured-good id in that namespace is in hand. Guessing one is the missions
  `InternalName` failure mode.
- `GameVersion` is served `"1.0.0"` and is assumed display-only. If History ever turns out to
  **filter** on it, an unrecognised build string would hide a row and look exactly like
  "History does not render".
- Whether `Cheat.Onboarding.MatchHistoryCount` is `ECVF_Cheat`-gated (see §5).
- Multi-row behaviour: ordering, pagination and whether the panel sorts by `MatchStart` or trusts
  array index. `AGS_MATCH_HISTORY_COUNT=N` tests it; only N=1 has been flown.
