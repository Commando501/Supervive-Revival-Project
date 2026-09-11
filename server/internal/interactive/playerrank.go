package interactive

// GET /mmr/player-ratings/{id}/rank — the player's OWN rank, and the CAREER badge (S122, 2026-08-15).
//
// STATUS: SHIPPED AND CONFIRMED LIVE. Backend-only — no shim, no injection, no `.text` write.
// The CAREER nav-button notification badge is driven end to end from this handler, measured in
// BOTH directions with the version gate isolated (see the arm table below).
//
// HOW THIS SURFACE WAS FOUND — the method is the reusable part.
// S121 established that a feature toggle is a probe for hidden BACKEND surface, by flipping keys
// one at a time and watching what the client newly requested. S122 inverted that: parse the WHOLE
// conversation the client has ALREADY had with us and diff it against the mux's registered routes.
// That enumerates every endpoint the client wants and we do not answer, in one pass, offline, for
// free — no launches, no toggles, no guessing which key to try next.
//
// [M] Over one 74-minute live session: 56 distinct client routes, of which **8 were unserved** and
// silently absorbed by main.go's "/" catch-all (200 {}). Three of the eight are client->server
// UPLOADS with no surface behind them (party latencies, game-telemetry events, and a Vivox voice
// token for a service that is externally dead — it answers "Access Token Service Unavailable").
// This is one of the ones with real UI behind it.
//
// ⚠⚠ FILTER capture.log BY User-Agent BEFORE COUNTING ANYTHING. In that same session **23,050 of
// 24,767** request records were NOT the game — 23,047 of them our own `supervive-loadout-shim`.
// Unfiltered, every number above would have been garbage. The game is `Loki/UE5-CL-0`. This is the
// documented trap that has now fired three times in this project's history.
//
// THE CONSUMER IS [M], NOT ASSUMED — a full-corpus census over the extracted assets:
//
//	`HasRankedRewardsToClaim`   -> 2 assets: WBP_UI_MainMenu_NormalMainMenu, WBP_ProfileScreen
//	`QueueRankRating` + friends -> 9 widget assets: WBP_UI_RankedScreen, WBP_UI_RankedProgress,
//	                               WBP_UI_RankedToggle, WBP_UI_RankedBadgeToggle,
//	                               WBP_UI_RankedScreenBadge, WBP_UI_RankedInfoPopup,
//	                               WBP_UI_ProgressionTracker_RankedV2, WBP_UI_ActivityTile_Base,
//	                               WBP_UI_EoG_RankMedal
//
// ⚠ State the unit: those are FILE counts, not occurrence counts. CLAUDE.md records a write-up that
// said "ClaimReward 24" without the unit and was off by 2.7x as a result.
//
// ★★★ AND THE MAIN MENU'S OWN BYTECODE SAYS EXACTLY WHAT THE BOOLEAN DRIVES
// (tools/extractor/out/bpdump_ExecuteUbergraph_WBP_UI_MainMenu_NormalMainMenu.txt, stmts 156-158):
//
//	[156] CallFunc_HasRankedRewardsToClaim_ReturnValue = GetMMRManager()->HasRankedRewardsToClaim()
//	[157] NavButtonFlyout_Career->ShowBadge(false, CallFunc_HasRankedRewardsToClaim_ReturnValue, …)
//	[158] NavButtonMain_Career  ->ShowBadge(false, CallFunc_HasRankedRewardsToClaim_ReturnValue, …)
//
// => ONE boolean, sourced only from this endpoint, drives the notification badge on BOTH CAREER nav
// buttons. That is a surface on the MAIN MENU — always built, observable with no navigation — and
// it is an ubergraph local, so it is directly readable by RPM.
//
// THE MODEL [M] — from the UHT oracle (tools/asdump/out/binds_members.csv), not guessed:
//
//	FPlayerRank       ID FString · Version int32
//	                  QueueRankRating TMap<FString, FQueueRankRating>
//	                  RewardsToClaim  TMap<FString, FRankedReward>
//	FQueueRankRating  Rating int32 · Rank ERank · Cost int32 · Updates TArray<FMatchRankedRating>
//	FRankedReward     ID FString · Entitlement FPrimaryAssetId
//
// ⚠ BOTH containers are `TMap` -> JSON **OBJECTS**, not arrays. Sending a TMap as an array is
// exactly the S120 `UnclaimedRewards` failure, which rejects the whole document.
// ⚠ `Version` is int32. handlePlayerStats documents this exact trap and then committed it two lines
// later by passing a millisecond timestamp; Unix SECONDS is int32-safe until 2038 and monotonic.
// ⚠ `Rank` is an **ERank enum string**. "Gold1" is the one value this project has MEASURED the
// client to accept (S121, /mmr/leaderboard). A wrong enum string is the S118 `ELokiActivityState`
// failure and sinks the entire struct — so reuse the known-good value rather than pick a fresh one.
// ⚠ `Entitlement` is an `FPrimaryAssetId` and is deliberately **OMITTED**. An unresolvable asset id
// is the missions `InternalName` failure mode; omitting a field is always safe, guessing an id is
// not. The badge needs only RewardsToClaim to be NON-EMPTY, so serving an id buys nothing here.
//
// ---------------------------------------------------------------------------------------------
// ★★★★★ THE RESULT — FOUR ARMS, ALL ON ONE LIVE CLIENT, NO RELAUNCH
// ---------------------------------------------------------------------------------------------
//
// Readouts: the ubergraph local via RPM (see the instance warning below) and the CAREER badge's
// own `WBP_MainMenu_Badge_C.Visibility` (ESlateVisibility: 1 = Collapsed, 4 = SelfHitTestInvisible,
// i.e. rendered), against the three sibling nav buttons as a spatial control.
//
//	arm  RewardsToClaim  Version      bool   has-run  CAREER badge   controls (Hunters/Store/Armory)
//	A    unserved ({})   —            False  61       —              —
//	B    non-empty       1786847998   TRUE   62       4 = RENDERED   all 1 = Collapsed
//	B'   {}              0            True   62       4              (NO reversal — see below)
//	C    empty           1786848659   False  61       1 = Collapsed  all 1 = Collapsed
//	D    NON-EMPTY       1            False  61       1 = Collapsed  all 1 = Collapsed
//
// ★ TWO CLEAN SINGLE-VARIABLE PAIRS:
//   - **B vs C** — only the reward map differs (both documents valid, version advancing) and the
//     outcome inverts => `RewardsToClaim` drives the badge. [M]
//   - **B vs D** — only `Version` differs (identical non-empty reward map) and the outcome inverts
//     => **this struct is behind a MONOTONIC VERSION GATE.** [M]
//
// ★ The has-run control moved 61 -> 62 -> 61 in lockstep with that single boolean — exactly one
// local changing non-default state. That internal consistency is hard to obtain by accident.
// ★ Only the LIVE instance ever moved; the CDO and the second (non-live) instance read False in
// every arm. A built-in negative control.
// [M] Canaries zero throughout: `LogJson ... Unable to import` 0, `Deserialization failure` 0,
// `Invalid response received` 0, `Fatal` 0.
//
// ⚠⚠ ARM B' IS THE INSTRUCTIVE FAILURE, AND IT IS WHY `AGS_PLAYER_RANK=0` IS NOT A CONTROL.
// Serving `{}` did NOT turn the badge back off. `{}` changes the document AND the version at once
// (it parses to Version 0), so it cannot separate "stale version rejected" from "empty document
// discarded" — it is uninterpretable, not negative. Arm D settles it: a valid, non-empty document
// at Version 1 is also ignored, so the gate is the version. **Read a null on this endpoint as
// "possibly version-rejected" until you have checked that Version advanced.**
// ⇒ The shipped code takes `int32(time.Now().Unix())`, which self-advances, so this failure mode
// is designed out rather than left to be remembered — the discipline CLAUDE.md asks for after the
// same class of bug bit client-config and regions eTags twice in one session.
//
// ⚠ CORRECTION TO THIS FILE'S OWN FIRST DRAFT: it said this is a login-time fetch that "probably
// needs a relaunch" to iterate on, by analogy with /player-stats/players/{id}. **That is FALSE and
// was measured false.** Restarting `ags` alone drops and re-establishes the client's WebSockets,
// and the resulting resync REFETCHES this endpoint within ~40 s — all four arms above were flown
// on ONE continuously-running client, with no relaunch and therefore no exposure to the ~2-in-5
// launch hazard. The analogy was reasoning by similarity where a measurement was available.
//
// ★ A NEW ENDPOINT FELL OUT OF SERVING THIS ONE: `POST /party/parties/{p}/refreshRanks` appears in
// the resync and is absent from all 56 routes observed before this handler existed. Still unserved
// (it lands on the catch-all). S121's "serving a surface reveals more surface" continues to hold.
//
// ⚠ OPEN — THE QUEUE KEY. `QueueRankRating` is keyed by queue id, and the only queue this backend
// advertises is `tutorialNew` (which is what the client itself sends to /mmr/leaderboard). A real
// ranked queue id is very likely something else, so the QueueRankRating half may find no entry even
// when the document is accepted — and it was NOT independently confirmed by these four arms, which
// all rode on RewardsToClaim. The RANKED screen/progress widgets are the surface that would test it.
//
// ⚠ [S] The endpoint<->struct join rests on name correspondence (/mmr/player-ratings/{id}/rank ->
// UMMRManager::GetPlayer(FPlayerRank&)) plus FPlayerRank being the only rank-shaped payload struct
// in the oracle. It is NOT disassembly-confirmed. It is however strongly corroborated: the boolean
// could not have moved unless our document deserialized into FPlayerRank and reached UMMRManager.
//
// ⚠⚠ READING THE BASELINE — `tools/re/bpframe_readout.py` PICKS THE WRONG INSTANCE FOR THIS CLASS.
// THREE live objects share it: the CDO and TWO both named `MainMenu_NormalV2`. The shipped tool
// stops at the first non-`Default__` match, and that one's frame is entirely default
// (HAS-RUN = 0 non-default locals of 219) — so it reports `False` for a graph that NEVER RAN, and
// the answer looks measured. The real widget is the THIRD object (HAS-RUN = 61/62). Both
// live-looking instances share the same NAME, so name matching cannot separate them either; only
// the has-run control can. This is a FOURTH member of the class-lookup blind-spot family CLAUDE.md
// records for obj_by_class.py (substring), cheat_reach_probe.py (endswith) and class_props.py
// (class-of-class). **Enumerate every instance and print the has-run control per instance.**
//
// ⚠ AND A DECOY WORTH KNOWING: on the badge widget, `ActiveSequencePlayers = Num=2` looks like
// "animations running, therefore visible" — but the three collapsed sibling badges read 2, 2 and 1.
// It does not discriminate. `Visibility` does. Sibling controls killed that reading immediately;
// read alone it would have been recorded as confirmation.
//
// KNOBS
//   AGS_PLAYER_RANK=0          fall through to the {} catch-all (pre-S122 behaviour, no rebuild).
//                              ⚠ NOT a controlled negative — see arm B'.
//   AGS_PLAYER_RANK_EMPTY=1    valid struct, advancing version, EMPTY reward map. THIS is the
//                              controlled negative (arm C).
//   AGS_PLAYER_RANK_VERSION=N  pin Version instead of using the clock. Isolates the version gate
//                              (arm D). Leave unset in normal operation.

import (
	"net/http"
	"os"
	"strconv"
	"time"

	"supervive-revival/server/internal/token"
)

func (s *Service) handlePlayerRank(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("AGS_PLAYER_RANK") == "0" {
		writeJSON(w, map[string]any{})
		return
	}
	id := r.PathValue("id")
	if id == "" {
		id = token.LocalPlayerID()
	}

	// One claimable ranked reward. The MAP KEY is the reward id; `Entitlement` is omitted (above).
	// Non-empty is the entire point — this is what drives the CAREER badge.
	rewards := map[string]any{
		"rr:season:1": map[string]any{"ID": "rr:season:1"},
	}
	// The controlled negative (arm C): hold the document valid and the version advancing, and vary
	// ONLY the reward map. Contrast AGS_PLAYER_RANK=0, which varies the whole document at once.
	if os.Getenv("AGS_PLAYER_RANK_EMPTY") == "1" {
		rewards = map[string]any{}
	}

	// Unix SECONDS: int32-safe until 2038, and self-advancing so a changed payload can never arrive
	// under a non-advancing version. Arm D measured that a low version is rejected outright, so this
	// is load-bearing, not insurance.
	version := int32(time.Now().Unix())
	if v := os.Getenv("AGS_PLAYER_RANK_VERSION"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			version = int32(n)
		}
	}

	writeJSON(w, map[string]any{
		"ID":      id,
		"Version": version,
		"QueueRankRating": map[string]any{
			// ⚠ `tutorialNew` is the only queue this backend advertises — see the open question above.
			"tutorialNew": map[string]any{
				// Deliberately CONSISTENT with handleMMRLeaderboard's SelfEntry (Gold1 / 1850) so
				// that if both surfaces render they must agree. A disagreement would itself be
				// informative; two arbitrary different values would not be.
				"Rating": 1850,
				"Rank":   "Gold1",
				"Cost":   30,
				// TArray<FMatchRankedRating>, left EMPTY: no match has ever been played in this
				// project, and fabricating per-match rating deltas would put invented history onto
				// a surface we have no way to verify.
				"Updates": []any{},
			},
		},
		"RewardsToClaim": rewards,
	})
}
