package interactive

// FMatchHistory.Matches — the synthetic match-history row, and the FK-21 test (S123, 2026-08-15).
//
// STATUS: ★★★★★ SOLVED END TO END, FEED **AND** RENDER, SCREENSHOT-CONFIRMED (2026-08-15).
// CAREER -> HISTORY draws our synthetic match: `VICTORY · Basic Training · 1/16 · 18:00`, the hero
// portrait, an ALLY row, and the full expanded stat panel. Backend-only — no shim, no injection, no
// `.text` write. Default is OFF and OFF is byte-identical to the pre-S123 payload (`"Matches": []`).
//
// ⇒ **FK-21 IS ANSWERED FOR ITS THIRD PANEL.** Its belief — "Career -> History shows an authentic
// empty" — is FALSE in the same way Stats (S121) and Ranked (S122) were: the panel was empty
// because we served it empty, and it renders the moment it is fed. All three of FK-21's panels
// have now been shown to be broken-by-omission rather than authentically empty, which is exactly
// what FK-21 predicted and what the register entry should record.
//
// ---------------------------------------------------------------------------------------------
// ★★★★★ THE RESULT — THREE ARMS, ONE LIVE CLIENT (up 3h08m), NO RELAUNCH, NO INJECTION
// ---------------------------------------------------------------------------------------------
// Readout: tools/re/matchhistory_readout.py against the live UMatchHistoryManager.
//
//	arm            Version      Matches.Num  TeamInfo.Placement  StartingRank    canaries
//	A  off         1786853586   0            —                   —               0/0/0/0
//	B  minimal     1786854166   1            0 (unserved)        0 = Unranked    0/0/0/0
//	C  full        1786854383   1            1 (SERVED)          12 = Gold1      0/0/0/0
//
// ★ ARM B — every served field read back VERBATIM out of the client's own parsed struct:
//   ID 'revival-match-0001' · QueueID 'tutorialNew' · IsRanked 0 · GameVersion '1.0.0' ·
//   NumTeams 16 · NumParticipants 64 · CharacterLevel 12 · StartingRating 1850.
//   The fields minimal does NOT serve sat at their defaults, which is the built-in negative
//   control: it is what distinguishes "our document landed" from "something else wrote here".
//
// ★★ ARM B vs C IS A CLEAN SINGLE-VARIABLE PAIR — only the five risky fields differ, and the two
// observable ones BOTH moved while every other field stayed identical. Because
// FJsonObjectConverter rejects the WHOLE document on one wrong-typed matched key, the document
// surviving with Num=1 means all five were accepted:
//   - `StartingRank: "Gold1"` -> byte 12 [M]. The ERank identity read live off UEnum::Names is
//     confirmed, and the enum-STRING form is accepted (the S118 ELokiActivityState failure mode
//     does not fire here).
//   - `TeamInfo` (nested struct w/ a nested array of structs) -> Placement 1 [M].
//   - `HeroAssetID: "Hero:reshealer"` (FPrimaryAssetId), `PersonalStats` (24 fields) and
//     `Teammates[]` accepted [I — implied by the document surviving whole, not read back field by
//     field; the readout does not print them].
//
// ⇒ ★★★★★ FK-21's HISTORY THIRD IS ANSWERED AT THE FEED LAYER: the empty was OURS. It was never a
// broken deserialization — even at BASELINE the manager held our player id with the gate open, and
// the array was empty only because we served it empty.
//
// ★★★★ AND THE RENDER HALF THEN CONFIRMED IT, FIELD BY FIELD (screenshot):
//	`VICTORY`                      <- TeamInfo.Placement 1
//	`1/16`                         <- Placement 1 of NumTeams 16  ⇒ ★★ **1-INDEXED**
//	`Basic Training`               <- QueueID "tutorialNew" through Queue_ID_to_Name
//	`Aug 15, 2026, 10:26:21 PM`    <- MatchStart 03:26:21Z converted UTC->LOCAL
//	`(18:00)`                      <- MatchEnd - MatchStart
//	hero portrait                  <- HeroAssetID "Hero:reshealer" RESOLVED (directly observed)
//	`ALLY  Reviver#6612`           <- TeamInfo.Teammates[0], PlayerID resolved to a display name
//	7 / 11 / 5 / 9 · 38 minions    <- Kills/Knocks/Revives/Assists/CreepKills
//	gold 1,200 / 2,400 / 900       <- GoldFromTreasure / **GoldFromMonsters** / GoldFromEnemies
//	HEALING TOTAL 8,400            <- DERIVED, HealingGiven 5,100 + HealingReceived 3,300
//
// ⚠⚠ **`TeamInfo.Placement` IS 1-INDEXED, AND THAT IS THE OPPOSITE OF ITS SIBLING.** S121 measured
// `FPlayerHeroStats.Placements` on /player-stats/players/{id} as **ZERO**-indexed (key 0 == 1st,
// confirmed by pre-registered prediction). Two placement fields on two endpoints of the same
// backend, opposite conventions. **Do not carry either convention across.** This was only
// discriminating because the flight served Placement 1 against NumTeams 16 — 1-of-1 would have
// rendered identically under both.
// ⚠ Two labels do NOT match their field names: `MINIONS KILLED` <- `CreepKills`, `GOLD FROM
// MINIONS` <- `GoldFromMonsters`. Read the label-to-field mapping, never assume it.
//
// ⚠ METHOD NOTE — before the screen was opened, the RPM readout showed exactly ONE live
// `WBP_UI_MatchHistoryEntry_C` with `Visibility = 4`, on a session where `MatchHistoryScreen` had
// **0** activations. That object was the widget-tree TEMPLATE and its Visibility a design-time
// value; reading it as "a row rendered" would have been the archetype trap (a fifth member of the
// class-lookup blind-spot family). The activation count is what caught it.
//
// ⚠ The onboarding readout was ATTEMPTED and is UNINTERPRETABLE, not negative:
// `CallFunc_Get_Number_of_Games_Played_ReturnValue` reads 0 on the live instance (HAS-RUN 59), but
// it is a per-execution ubergraph scratch slot whose value is ALSO the default, so "re-evaluated
// and got 0" and "holds a value from a run predating our document" cannot be separated.
//
// ⚠⚠ THE User-Agent TRAP FIRED TWICE MORE IN THIS ONE SITTING, AND ONE VARIANT IS NEW.
// (1) Verification curls land in capture.log reading exactly like client traffic — defused by
// giving them a deliberately absurd UA (`fk21-verify-NOT-THE-GAME`).
// (2) ★ NEW WRINKLE: **the grep WINDOW is part of the instrument.** `grep -B2 -A3 match-history`
// paired a request with a NEIGHBOURING request's User-Agent and read as `supervive-loadout-shim`,
// i.e. "the game never refetched". Widening to `-A 12` showed the true pairing:
// `Loki/UE5-CL-0`. **Pair each request with its OWN header block; never trust a narrow window.**
//
// ---------------------------------------------------------------------------------------------
// WHY THIS EXISTS — FK-21, and the two-thirds of it that already fell
// ---------------------------------------------------------------------------------------------
//
// FK-21 (docs/ignorance-map-s101.md:1387) challenges the belief that "Career -> Stats / Ranked /
// History show authentic empties". Its argument is that this account is NOT new — Saved\ImageCaches
// holds 56 JPGs dated Nov 2024 - Aug 2025, and UserSettings.ini records HasPlayedTutorial=True,
// HasSeenRankedPopup=True, HasSeenReturningPlayerModal=True — so "empty" was never authentic, and
// **a broken deserialization is observationally identical to an authentic empty.**
//
// Two of its three panels have since been answered, and in BOTH cases the empty was NOT authentic —
// it was broken-by-omission, and serving the document lit the panel up:
//
//	Career -> Stats   S121  GET /player-stats/players/{id}   renders MATCHES 12 / KILLS 40 / ...
//	Career -> Ranked  S122  GET /mmr/player-ratings/{id}/rank  renders GOLD I / 1,850 RP
//
// **History is the untested third**, and it was left untested DELIBERATELY: interactive.go's
// handleMatchHistory serves `Matches: []` because the news-banner gate it was built for needs only
// `Version`, and FMatchHistoryEntry is a 15-field struct where every matched key is a chance to
// wrong-type something and have FJsonObjectConverter reject the WHOLE document. That was the right
// call THEN (it kept the gate probe single-variable). This file is the follow-up it asked for.
//
// ---------------------------------------------------------------------------------------------
// ★★★ THE MODEL [M] — READ LIVE OUT OF THE RUNNING CLIENT, NOT FROM THE USMAP
// ---------------------------------------------------------------------------------------------
//
// `tools/re/struct_layout.py <pid> <base> MatchHistoryEntry ...` against the live process
// (read-only RPM). Offsets are `Offset_Internal`, sizes are `ElementSize`:
//
//	FMatchHistoryEntry                              FLokiPlayerMatchStats  (0x94, 38 fields)
//	  +0x000 FString   ID                             +0x00 int32  Kills
//	  +0x010 FDateTime MatchStart                      +0x04 int32  CurrentKillStreak
//	  +0x018 FDateTime MatchEnd                        +0x08 int32  MaxKillStreak
//	  +0x020 FString   QueueID                         +0x0C int32  Deaths
//	  +0x030 bool      IsRanked                        +0x10 int32  Assists
//	  +0x038 FString   GameVersion                     +0x14 int32  Knocks
//	  +0x048 int32     NumTeams                        ...
//	  +0x04C int32     NumParticipants                 +0x54 float  DamageDone
//	  +0x050 FPrimaryAssetId HeroAssetID               +0x58 float  HeroDamageDone
//	  +0x060 FMatchHistoryTeamInfo TeamInfo            +0x7C float  HealingGiven
//	  +0x078 FLokiPlayerMatchStats PersonalStats       +0x88 float  TimeSpentAlive
//	  +0x10C int32     CharacterLevel                  +0x8C float  TimeSpentKnocked
//	  +0x110 TArray<FArmoryReward> ArmoryRewardsEarned +0x90 float  TimeSpentDead
//	  +0x120 ERank     StartingRank
//	  +0x124 int32     StartingRating
//
//	FMatchHistoryTeamInfo   int32 Placement · float SurvivalDuration
//	                        TArray<FMatchHistoryTeammateInfo> Teammates
//	FMatchHistoryTeammateInfo  FString PlayerID · FPrimaryAssetId HeroAssetID
//	FArmoryReward           FPrimaryAssetId AssetId · int32 Quantity · bool Extracted
//	                        · bool Boosted · float BoostFactor
//
// ⚠⚠ THE USMAP CANNOT ANSWER THE TWO QUESTIONS THAT MATTER HERE, AND WOULD HAVE LIED CONFIDENTLY.
// FK-14 (docs/fk14-usmap-settled.md) measured that the extractor reads a property's inner/enum
// INLINE at FField+0x80 — past the end of the object — so it captures whatever FField the allocator
// happened to place next. That defect covers exactly `Matches`' ARRAY INNER and `StartingRank`'s
// ENUM. Both were therefore read live at the FK-14-corrected offsets instead
// (FArrayProperty::Inner *(+0x78), FEnumProperty::Enum *(+0x78)).
//
// ★ `StartingRank` is **ERank** [M] — enum object named live, with its 29-entry value table read
// out of UEnum::Names. `Gold1` is index 12, i.e. a REAL member, which matters because "Gold1" is
// the one ERank string this project has MEASURED the client to accept (S121, /mmr/leaderboard).
// A wrong enum string is the S118 `ELokiActivityState` failure and sinks the entire document.
//
// ---------------------------------------------------------------------------------------------
// ★★★★★ THE FREE CONTROL THIS ENDPOINT SHIPS WITH — USE IT, DO NOT SKIP IT
// ---------------------------------------------------------------------------------------------
//
// The lobby NEWS BANNER is gated on `IsMatchHistoryLoaded` == `[MatchHistoryManager+0x68] >= -1`,
// and `+0x68` IS this document's `Version` stored inline on the manager (interactive.go's
// handleMatchHistory documents the derivation; -2 is the never-loaded sentinel).
//
// ⇒ If FJsonObjectConverter rejects this document because one of the 15 keys is wrong-typed,
// `Version` is never written, the sentinel survives, gate 1 closes and **the news banner
// disappears**. The banner is therefore an always-on, zero-cost, binary canary for
// "did this document deserialize?" — and it is a canary that answers even when the Career UI
// renders nothing, which is precisely the ambiguity FK-21 is about.
//
// ⚠⚠ BUT THE BANNER IS A CONSEQUENCE, NOT THE MEASUREMENT. The decisive instrument is
// `tools/re/matchhistory_readout.py`, which reads the PARSED struct on the live manager:
// `Version` at +0x68 and `Matches.Num` at +0x70. That distinguishes all four outcomes that a
// screenshot alone cannot:
//
//	Version advanced, Matches.Num == 1  -> parsed AND the entry survived; any blank panel is a
//	                                       RENDER question, not a feed question
//	Version advanced, Matches.Num == 0  -> the entry was dropped element-wise (the missions
//	                                       `MakeMissionModel` failure shape)
//	Version still -2                    -> whole document rejected; grep LogJson for the property
//	Version advanced, banner gone       -> contradiction; suspect the readout, not the game
//
// This is the regions lesson applied before the fact, not after: FK-5's latency chain failed
// SILENTLY at six nested layers for a year because "parsed fine, populated nothing" logs nothing,
// and `LogJson` / `Deserialization failure` / `Invalid response received` are all blind to it.
// **On a nested struct, read the parsed struct. Do not trust silence.**
//
// ---------------------------------------------------------------------------------------------
// HOW TO FLY IT — NO RELAUNCH, AND NO ags RESTART EITHER
// ---------------------------------------------------------------------------------------------
//
// `GET /match-history/players/{id}` is a connect-time fetch (one occurrence per session in the
// live capture), but it is refetchable on demand:
//
//	lobby.NotifyResource(playerID, "/match-history/players/"+playerID, MatchHistoryVersion(playerID), "fk21")
//
// [M] push.go:414-418 measured exactly this frame producing the GET **491 ms later**, with the
// messenger connect count UNCHANGED — no reconnect, no teardown, one resource refetched.
//
// ⚠⚠ CORRECTION TO push.go:451-453, WHICH IS NOW STALE AND WILL MISLEAD YOU. It says "resources
// served as empty catch-alls carry no version, so their cache stays 0 and any positive value works
// — that is why the /match-history probe succeeded with Version 7." `/match-history` STOPPED being
// a catch-all when handleMatchHistory was written: it now carries `MatchHistoryVersion`, seeded
// from wall-clock seconds (~1.79e9). A push of Version 7 today is the documented TOO-LOW case and
// is **silently ignored** — indistinguishable from "the client doesn't handle this resource".
// Pass `MatchHistoryVersion(id)`, which is exported for precisely this reason.
//
// ⚠ And the payload tag below is what makes that version MOVE when the shape changes. Serving a
// new document under a non-advancing version is the same silent-staleness family as FPlayerRank's
// gate, the client-config eTag, the regions eTag and the matchmaking eTag — four instances in this
// project, of which the last two shipped in a single session. Wiring the mode INTO the tag means
// it cannot be forgotten here.
//
// ---------------------------------------------------------------------------------------------
// KNOBS
//   AGS_MATCH_HISTORY=off      (default) `Matches: []`. Byte-identical to pre-S123.
//                              ⚠ This is the BASELINE, and unlike AGS_PLAYER_RANK=0 it IS a
//                              controlled negative: the document stays valid and the version keeps
//                              advancing, so only the array contents vary (arm B' of S122 is the
//                              cautionary tale — `{}` varies document AND version at once).
//   AGS_MATCH_HISTORY=minimal  one row, SCALARS AND STRINGS ONLY. No nested struct, no array, no
//                              enum, no FPrimaryAssetId — i.e. nothing that can be wrong-typed
//                              beyond int/float/bool/FString/FDateTime, and nothing that can name
//                              an unresolvable asset id.
//   AGS_MATCH_HISTORY=full     one row, every field including HeroAssetID, TeamInfo, PersonalStats
//                              and StartingRank.
//   AGS_MATCH_HISTORY_COUNT=N  rows to serve (default 1). N>1 tests list behaviour, ordering and
//                              whether the panel paginates.
//   AGS_MATCH_HISTORY_HERO=x   PrimaryAssetName for HeroAssetID (default `reshealer`, the hero
//                              S120 measured resolving as `Hero:reshealer`). `full` only.
//
// ⚠ FLY `minimal` FIRST. If `full` is flown first and the panel stays blank, the result cannot
// distinguish "History does not render" from "one of the five risky fields sank the document" —
// and this endpoint's failure is silent. minimal -> full is the single-variable ladder.
//
// ---------------------------------------------------------------------------------------------
// ★★★★ BLAST RADIUS — `Matches.Num()` IS ALSO THE ONBOARDING COMPONENT'S "GAMES PLAYED"
// ---------------------------------------------------------------------------------------------
//
// This surface is NOT confined to Career -> History. [M] from the shipped bytecode
// (tools/extractor/out/bpdump_Get Number of Games Played.txt,
//  Comp_MainMenu_Onboarding_C::"Get Number of Games Played", 11 statements, fully decoded):
//
//	cv = GetConsoleVariableIntValue("Cheat.Onboarding.MatchHistoryCount")   [stmt 0]
//	if (cv >= 0) return cv                                                  [stmt 1-4]
//	return GetMatchHistoryManager()->GetMatchHistory().Matches.Num()        [stmt 5-8]
//
// — i.e. THE EXACT ARRAY THIS FILE POPULATES is the onboarding component's games-played count.
// `Comp_MainMenu_Onboarding` also owns `Should Show Returning Player Modal`, and its
// `On Match History Updated` handler jumps straight into its ubergraph (offset 4687), so this
// document is a live input to the onboarding flow, not just to a stats panel.
//
// ⇒ TWO CONSEQUENCES, BOTH USEFUL:
//   1. ★ A SECOND, INDEPENDENT READOUT. Onboarding state changes on a DIFFERENT subsystem from the
//      Career panel, so it can confirm the array landed even if History renders nothing. Two
//      readouts on one change is exactly what turns a null into a localised fault.
//   2. ⚠ AN UNINTENDED EFFECT TO WATCH. Serving N rows makes the client believe this account has
//      played N games, which may suppress or trigger onboarding prompts / the returning-player
//      modal. AGS_MATCH_HISTORY_COUNT controls it; COUNT=1 keeps the perturbation to one game.
//      ⚠ Note FK-21's own premise here: UserSettings.ini ALREADY records
//      HasSeenReturningPlayerModal=True, so that modal's state is not virgin and a non-appearance
//      proves nothing.
//
// ★★ AND IT HANDS US A CONTROL THAT NEEDS NO BACKEND AT ALL. `Cheat.Onboarding.MatchHistoryCount`
// is a cvar, and FK-13 established cvars as a SHIM-FREE channel settable from `[ConsoleVariables]`
// in the USER Engine.ini — the same file and mechanism as FK-11's `[Core.Log]`, with no injection
// and no `.text` write. Setting it moves the downstream count WITHOUT touching our array, which
// isolates "onboarding reads this count" from "our document landed".
// ⚠ It may be inert: the name is `Cheat.*`, and `DISABLE_CHEAT_CVARS` is a hard
// `(UE_BUILD_SHIPPING || ...)` #define with no Target.cs escape. CLAUDE.md records which of the 44
// known `loki.*` cvars carry `ECVF_Cheat` as NOT ENUMERATED — so an inert result here is
// uninterpretable unless that flag is checked first. Do not read a null from it as a negative.
//
// ---------------------------------------------------------------------------------------------
// PRE-REGISTERED PREDICTIONS (written before the flight, so the result can falsify them)
//   1. `minimal` deserializes: Version advances, Matches.Num == 1, news banner unchanged.
//   2. Career -> History renders ONE row rather than "no matches".
//   3. `full` renders the hero portrait for AGS_MATCH_HISTORY_HERO and placement text.
//   4. TeamInfo.Placement is served as 1 against NumTeams 16. If the UI prints "#1" the field is
//      1-indexed; "#2" means 0-indexed. ★ The values are deliberately non-degenerate so this is
//      DISCRIMINATING — `Placements` on /player-stats/players/{id} turned out to be ZERO-indexed
//      (S121, confirmed by prediction), so the sibling field's convention is a real open question
//      and not a safe assumption.
//   ⚠ Prediction 2 failing while 1 holds is NOT a null result — it localises the fault to the
//   render half, which is exactly the split FK-21 says is currently unmeasurable.

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// matchHistoryEpoch freezes the row timestamps at process start.
//
// WHY NOT time.Now() PER REQUEST: the payload tag (and therefore the served Version) is keyed on
// the MODE, not on the clock — deliberately, because a time-varying tag would bump the version on
// every request and manufacture the unbounded-refetch shape push.go documents. With a per-request
// clock, two fetches at the same Version would return different documents. Freezing at start keeps
// the document stable for the lifetime of the process, which is the property the version gate
// assumes.
var matchHistoryEpoch = time.Now().UTC()

// matchHistoryMode returns "", "minimal" or "full". Unset/0/off/false all mean off.
func matchHistoryMode() string {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("AGS_MATCH_HISTORY"))) {
	case "minimal", "min", "1":
		return "minimal"
	case "full", "2":
		return "full"
	default:
		return ""
	}
}

// matchHistoryPayloadTag feeds progressionVersionFor's change detector, so that switching modes
// advances the served Version. See the stale-version warning in the header.
func matchHistoryPayloadTag() string {
	m := matchHistoryMode()
	if m == "" {
		return "mh1-empty" // ⚠ the pre-S123 literal — preserved so OFF is byte-identical
	}
	return fmt.Sprintf("mh1-%s-%d-%s", m, matchHistoryCount(), matchHistoryHero())
}

func matchHistoryCount() int {
	if v := os.Getenv("AGS_MATCH_HISTORY_COUNT"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n <= 50 {
			return n
		}
	}
	return 1
}

func matchHistoryHero() string {
	if v := strings.TrimSpace(os.Getenv("AGS_MATCH_HISTORY_HERO")); v != "" {
		return v
	}
	// `Hero:reshealer` is the form S120 MEASURED the client resolving for FHeroMasteryProgress.HeroId
	// (it served `Hero:` and `HeroMastery:` forms simultaneously and the UI drew the `Hero:` one).
	// Reuse a measured-good id rather than mint a fresh one — an unresolvable FPrimaryAssetId is the
	// missions `InternalName` failure, which drops the element SILENTLY.
	return "reshealer"
}

// matchHistoryMatches builds FMatchHistory.Matches. Empty (never nil) when the knob is off.
func matchHistoryMatches(playerID string) []any {
	mode := matchHistoryMode()
	if mode == "" {
		return []any{}
	}
	out := make([]any, 0, matchHistoryCount())
	for i := 0; i < matchHistoryCount(); i++ {
		// Newest first, one hour apart. Ordering is itself a question — if the panel sorts by
		// MatchStart the rows appear in this order; if it trusts array index they appear reversed.
		start := matchHistoryEpoch.Add(-time.Duration(i+1) * time.Hour)
		end := start.Add(18 * time.Minute)

		e := map[string]any{
			"ID": fmt.Sprintf("revival-match-%04d", i+1),
			// FDateTime imports from an ISO-8601 string. UTC with a trailing Z, which is what
			// FDateTime::ParseIso8601 emits and accepts.
			"MatchStart": start.Format("2006-01-02T15:04:05Z"),
			"MatchEnd":   end.Format("2006-01-02T15:04:05Z"),
			// The only queue this backend advertises, and the one S121 measured the client
			// resolving to the label BASIC TRAINING on the stats page — so a rendered row has a
			// real chance of carrying a real label rather than a blank.
			"QueueID":  "tutorialNew",
			"IsRanked": false,
			// ⚠ [S] Display-only as far as we know. If History turns out to FILTER on this, an
			// unrecognised build string would hide the row and read exactly like "History does not
			// render" — so if minimal produces Matches.Num==1 and still shows nothing, clearing
			// this field is the first thing to vary.
			"GameVersion": "1.0.0",
			// Non-degenerate on purpose: 1-of-16 makes a rendered placement DISCRIMINATE 0- from
			// 1-indexing (prediction 4). 1-of-1 could not.
			"NumTeams":        16,
			"NumParticipants": 64,
			"CharacterLevel":  12,
			"StartingRating":  1850,
		}

		if mode == "full" {
			hero := "Hero:" + matchHistoryHero()
			e["HeroAssetID"] = hero
			// ERank [M] — enum identity and value table read live; "Gold1" is index 12 and is the
			// one ERank string measured accepted by this client (S121).
			e["StartingRank"] = "Gold1"
			e["TeamInfo"] = map[string]any{
				"Placement":        1,
				"SurvivalDuration": 1080.0,
				"Teammates": []any{
					map[string]any{"PlayerID": playerID, "HeroAssetID": hero},
				},
			}
			// All 38 fields are int32 or float [M]; a representative, self-consistent subset.
			// Unknown keys are ignored by FJsonObjectConverter and absent keys default to zero, so
			// a subset is safe — the risk here is wrong TYPES, and every type below was measured.
			e["PersonalStats"] = map[string]any{
				"Kills": 7, "CurrentKillStreak": 2, "MaxKillStreak": 4, "Deaths": 3,
				"Assists": 9, "Knocks": 11, "MaxKnockStreak": 3, "MaxMultiKnock": 2,
				"Knocked": 4, "Revives": 5, "Revived": 2, "CreepKills": 38,
				"GoldFromTreasure": 1200, "GoldFromMonsters": 2400, "GoldFromEnemies": 900,
				"DamageDone": 21400.0, "HeroDamageDone": 15200.0,
				"DamageTaken": 19800.0, "HeroDamageTaken": 12600.0,
				// ★★★★★ THE DAMAGE TILES READ THE `Effective*` FIELDS, NOT THE RAW ONES — [M],
				// CONFIRMED 5/5 BY A DISCRIMINATING FLIGHT (2026-08-15, screenshot):
				//	TOTAL DAMAGE DEALT   18,000 <- EffectiveDamageDone      (raw DamageDone 21,400)
				//	DAMAGE TO HUNTERS    13,100 <- HeroEffectiveDamageDone  (raw 15,200)
				//	TOTAL DAMAGE TAKEN   16,700 <- EffectiveDamageTaken     (raw 19,800)
				//	DAMAGE FROM HUNTERS  11,300 <- HeroEffectiveDamageTaken (raw 12,600)
				//	SHIELDED DAMAGE       2,600 <- ShieldMitigatedDamage
				// ⇒ the four raw Damage* fields are NOT read by this panel at all. [S] They may
				// still drive the end-of-game screen; untested. `ArmorMitigatedDamage` is served
				// and appears nowhere on this panel.
				// First `full` flight served ONLY the four raw Damage* fields above and every damage
				// tile rendered 0 — TOTAL DAMAGE DEALT, DAMAGE TO HUNTERS, TOTAL DAMAGE TAKEN,
				// SHIELDED DAMAGE, DAMAGE FROM HUNTERS — while HEALING GIVEN/RECEIVED (also floats,
				// same struct) rendered correctly at 5,100/3,300. That asymmetry is the whole clue:
				// healing has no `Effective` variant, so it is the one stat whose raw field IS what
				// the UI reads.
				// ⚠ VALUES ARE DELIBERATELY DISTINCT FROM THE RAW ONES so the tiles DISCRIMINATE:
				// 18,000 vs 21,400 etc. If a tile shows 18,000 it reads Effective; 21,400 means raw
				// and the hypothesis is wrong. Equal values would have proven nothing.
				"EffectiveDamageDone": 18000.0, "HeroEffectiveDamageDone": 13100.0,
				"EffectiveDamageTaken": 16700.0, "HeroEffectiveDamageTaken": 11300.0,
				"ShieldMitigatedDamage": 2600.0, "ArmorMitigatedDamage": 3100.0,
				"HealingGiven": 5100.0, "HealingReceived": 3300.0,
				"TimeSpentAlive": 1080.0, "TimeSpentKnocked": 42.0, "TimeSpentDead": 60.0,
			}
			// ⚠ ArmoryRewardsEarned stays EMPTY: FArmoryReward.AssetId is an FPrimaryAssetId for a
			// cosmetic, and this project has no measured-good cosmetic id in that namespace. An
			// empty array is always safe; a guessed id is the missions failure mode. Add it only
			// once a resolvable id is in hand.
			e["ArmoryRewardsEarned"] = []any{}
		}

		out = append(out, e)
	}
	return out
}
