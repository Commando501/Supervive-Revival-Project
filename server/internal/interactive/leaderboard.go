package interactive

// Leaderboards — GET /player-stats/leaderboard (S121, 2026-08-15).
//
// HOW THIS SURFACE WAS FOUND, because the method generalises:
// The LEADERBOARDS page is gated by the declarative UI toggle `leaderboards`. This project served
// FeatureToggles with the wrong sub-key (`Config["default"]` instead of `Config["enabled"]`) from
// S73 until 5e40475, so the gate never opened and the page was never rendered — and therefore the
// client had NEVER been observed calling this endpoint. Flipping one toggle revealed it.
//
//   ⇒ ★ A FEATURE TOGGLE IS A PROBE FOR HIDDEN *BACKEND* SURFACE, NOT JUST HIDDEN UI.
//     Each remaining dark key may expose endpoints we have never seen. See
//     docs/s121-toggle-fix-confirmed.md §2.
//
// [M] The live client (User-Agent: Loki/UE5-CL-0) issues, and previously got 200 {} from a catch-all:
//
//     GET /player-stats/leaderboard?queueId=tutorialNew&period=daily&statCode=wins
//                                  &heroId=Hero:All&start=1&end=25
//
// Every parameter maps 1:1 onto a visible control (QUEUE / DAILY tab / STAT / HUNTER / paging), so
// the UI hands us the vocabulary for free — change a dropdown and re-read docs/capture.log.
//
// ⚠⚠ THE TRAP THAT WOULD HAVE COST A FLIGHT: THE RESPONSE MUST *ECHO* THE REQUEST.
// [M] WBP_UI_LeaderboardScreen_C::"Current Leaderboard Is Stale" computes
//        HeroName != heroId.PrimaryAssetName || StatCode != statKey || QueueID != queueKey
//        || age > 60s
// and a stale response is **parsed perfectly and then silently discarded**. So a schema-correct
// reply with the wrong echo looks EXACTLY like a parse failure. Note the asymmetry that makes this
// nasty: the request carries `heroId=Hero:All`, but the comparison is against
// `PrimaryAssetName`, i.e. the BARE name — we must echo `All`, never `Hero:All`.
// `Period`, `Start` and `End` are NOT compared.
//
// [M] Top-level, no envelope: the response callback (0x5809760) has ZERO instructions between
// GetContentAsString and JsonObjectStringToUStruct<FLokiPlayerStatsLeaderboard>. Control: an
// envelope detector over all 152 JsonObjectToUStruct sites fires on exactly 1 (AccelByte's
// "payload") and 0 for the four Loki structs.
//
// [M] Required for rows to draw: StatCode, QueueID, HeroName (all echoed) and a NON-EMPTY Entries —
// the else-arm of the length test is literally the "No one has claimed a spot on this
// leaderboard...yet" widget. Everything else is optional.
//
// Other measured behaviours worth knowing before debugging this:
//   - `Value` is FCeil'd before display.
//   - Row order is ARRAY INDEX, not Rank. Sort server-side; the client will not.
//   - An unresolved PlayerID still renders a row (so a fabricated id is fine for testing).
//   - ExpirationTimeSeconds drives the "RESET IN hh:mm:ss" countdown.
//   - A second fetch issued while one is in flight is silently dropped.
//
// Vocabulary [M]: statCode ∈ {kills, wins, damage, healing} (from ST_Leaderboard_Stats, complete);
// period ∈ {daily, weekly} for THIS endpoint — the FRIENDS and RANKED side tabs are a different
// widget that hits /mmr/leaderboard[/friends]. queueId is whatever we serve via GetQueueInfo().
//
// Knob: AGS_LEADERBOARD=0 restores the previous behaviour (fall through to the {} catch-all),
// without a rebuild.

import (
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"supervive-revival/server/internal/token"
)

// leaderboardEntry is one row: RANK · SCORE · PLAYER.
type leaderboardEntry struct {
	PlayerID   string         `json:"PlayerID"`
	Rank       int            `json:"Rank"`
	Value      float64        `json:"Value"`
	HeroName   string         `json:"HeroName"`
	HeroCounts map[string]int `json:"HeroCounts,omitempty"`
}

// handleLeaderboard answers GET /player-stats/leaderboard.
//
// The echo fields are taken from the REQUEST, never from a constant — that is the whole point of
// the staleness check above, and hardcoding them would silently break the moment a dropdown moves.
func (s *Service) handleLeaderboard(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("AGS_LEADERBOARD") == "0" {
		writeJSON(w, map[string]any{})
		return
	}

	q := r.URL.Query()
	statCode := q.Get("statCode")
	queueID := q.Get("queueId")
	period := q.Get("period")

	// ⚠ heroId arrives as a FPrimaryAssetId ("Hero:All", "Hero:ghost") but the client compares
	// against PrimaryAssetName — the part AFTER the colon. Echoing the full id fails the staleness
	// test and the whole response is dropped, with no log line to explain it.
	heroName := q.Get("heroId")
	if i := strings.LastIndex(heroName, ":"); i >= 0 {
		heroName = heroName[i+1:]
	}

	start := atoiOr(q.Get("start"), 1)
	end := atoiOr(q.Get("end"), 25)

	entries := s.leaderboardEntries(statCode, queueID, period, heroName, start, end)

	writeJSON(w, map[string]any{
		// --- echoed: these four decide whether the client KEEPS the response ---
		"StatCode": statCode,
		"QueueID":  queueID,
		"HeroName": heroName,
		"Period":   period,
		// --- informational ---
		"Start":                 start,
		"End":                   end,
		"ExpirationTimeSeconds": 3600,
		"Entries":               entries,
	})
}

// leaderboardEntries builds the rows. Today this is a placeholder set so the page can be verified
// end to end; the real source will be match results once they are recorded per-player.
//
// ⚠ Deliberately NOT empty: an empty Entries renders the "No one has claimed a spot" widget, which
// is indistinguishable from the pre-S121 {} response — i.e. it would make the flight
// uninterpretable. A non-empty set is what makes success and failure look different.
func (s *Service) leaderboardEntries(statCode, queueID, period, heroName string, start, end int) []leaderboardEntry {
	self := token.LocalPlayerID()

	rows := []leaderboardEntry{
		{PlayerID: self, Rank: 1, Value: 42, HeroName: "ghost",
			HeroCounts: map[string]int{"ghost": 7, "brall": 2}},
	}

	// Clamp to the requested window. The client does NOT re-sort, so emit in display order.
	if start < 1 {
		start = 1
	}
	if end < start {
		end = start
	}
	if start-1 >= len(rows) {
		return []leaderboardEntry{}
	}
	hi := end
	if hi > len(rows) {
		hi = len(rows)
	}
	return rows[start-1 : hi]
}

func atoiOr(s string, def int) int {
	if s == "" {
		return def
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		return def
	}
	return n
}

// envOrDefault returns env var v, or def when unset/empty. Used for the region knobs.
func envOrDefault(v, def string) string {
	if s := os.Getenv(v); s != "" {
		return s
	}
	return def
}

// ---------------------------------------------------------------------------------------------
// GET /mmr/leaderboard  — the RANKED side tab (S121)
// ---------------------------------------------------------------------------------------------
//
// A DIFFERENT endpoint and a DIFFERENT struct from /player-stats/leaderboard. The LEADERBOARDS
// screen's DAILY/WEEKLY tabs hit player-stats; the RANKED tab calls
// `GetMMRManager()->GetLeaderboard(1, 50, Queue, Region, …)` and FRIENDS calls
// /mmr/leaderboard/friends. [M] Note the paging differs too: 1..50 here vs 1..25 there.
//
// Deserializes TOP-LEVEL into FLeaderboard (/Script/Loki.Leaderboard, SizeOf 0x68) — no envelope,
// and the success path performs NO validation, so unlike the player-stats leaderboard there is
// **no staleness/echo check** to satisfy. [M]
//
//	FLeaderboard      Start int32 · End int32 · QueueID FString · Role FString
//	                  Entries TArray<FLeaderboardEntry> · SelfEntry FLeaderboardEntry (OBJECT)
//	FLeaderboardEntry PlayerID FString · Rank ERank · Rating int32 · Placement int32
//	                  Percentile float · AvatarID FPrimaryAssetId
//
// ⚠⚠ `Rank` IS AN ENUM, NOT A NUMBER. Send the entry NAME as a string. A bad enum string is the
// S118 `ELokiActivityState` failure exactly — `FJsonObjectConverter` rejects the WHOLE struct and
// `LogJson` quotes the bad value back. ERank in order: Unranked, Bronze4..Bronze1,
// Silver4..Silver1, Gold4..Gold1, Platinum4..Platinum1, Diamond4..Diamond1, Master4..Master1,
// GrandMaster, Legend, Count.
// ⚠ `AvatarID` is an FPrimaryAssetId; it is OMITTED here rather than guessed — an unresolvable id
// is the missions `InternalName` failure mode, and omitting a field is always safe.
//
// ⚠ The endpoint↔struct join is [I], not [M]: it rests on there being exactly one deserialize site
// for this struct image-wide plus exact field/query-param correspondence. The MEMBER LIST is [M]
// from the UHT oracle. If this renders nothing, suspect the join before the members.
//
// ★★ CONFIRMED LIVE (S121): the RANKED tab renders `#1. · Reviver#6612 · 1,850 RP` from the
// Placement / PlayerID / Rating below. Verified with User-Agent discipline — the request came
// from `Loki/UE5-CL-0`, not from our own probe — with 0 LogJson complaints and 0
// "Deserialization failure". That also validates the riskiest field: `Rank: "Gold1"` was accepted
// as an ERank enum string, and a wrong enum would have sunk the whole struct.
// ⚠ The UI shows QUEUE "BREACH" while the request carries `queueId=tutorialNew` — the dropdown
// renders a display NAME for the id. Do not "fix" the served queue id to match the label.
//
// Knob: AGS_MMR_LEADERBOARD=0 falls through to the {} catch-all.
func (s *Service) handleMMRLeaderboard(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("AGS_MMR_LEADERBOARD") == "0" {
		writeJSON(w, map[string]any{})
		return
	}
	q := r.URL.Query()
	start := atoiOr(q.Get("start"), 1)
	end := atoiOr(q.Get("end"), 50)
	self := token.LocalPlayerID()

	entry := func(id string, rank string, rating, placement int, pct float64) map[string]any {
		return map[string]any{
			"PlayerID":   id,
			"Rank":       rank, // ERank NAME — see the enum list above
			"Rating":     rating,
			"Placement":  placement,
			"Percentile": pct,
			// AvatarID deliberately omitted.
		}
	}
	me := entry(self, "Gold1", 1850, 1, 0.99)

	writeJSON(w, map[string]any{
		"Start":   start,
		"End":     end,
		"QueueID": q.Get("queueId"),
		// Region arrives as ?region= (empty == ALL). `Role` is the struct's own field and is not
		// the region — left empty rather than guessed at.
		"Role":      "",
		"Entries":   []any{me},
		"SelfEntry": me, // an OBJECT, not an array
	})
}

// ---------------------------------------------------------------------------------------------
// GET /player-stats/players/{id}  — per-player career stats (S121)
// ---------------------------------------------------------------------------------------------
//
// Top-level FPlayerStats (/Script/Loki.PlayerStats), no envelope, no validation. [M]
// ★ Calibration: FPlayerProgression's handler has a byte-identical shape and this project has
// already measured THAT route as top-level — so this reading is anchored to a known-good case.
//
//	FPlayerStats      ID FString · Version int32 · StatsByQueue TMap<FString,FPlayerQueueStats>
//	FPlayerQueueStats ID FString · StatsByHero  TMap<FString,FPlayerHeroStats>
//	FPlayerHeroStats  22 int32s + Placements TMap<int32,int32>     (SizeOf 0xa8, 24 props)
//
// ⚠ ALL THREE MAPS ARE `TMap` -> JSON **OBJECTS**, not arrays. `Placements` is int-keyed, so its
// JSON keys must be int-parsable strings ({"1":3,"2":5}) — the same shape as the S120
// `UnclaimedRewards` map, where sending an array was exactly the failure.
// ⚠ `Version` here is **int32**; contrast FMatchHistory.Version which is int64. Getting the width
// wrong on a matched key sinks the whole struct.
// [S] Whether this route has a monotonic Version gate like FParty/FMatchHistory is unknown, so a
// bumping value is served as cheap insurance rather than a constant.
//
// Knob: AGS_PLAYER_STATS=0 falls through to the {} catch-all.
func (s *Service) handlePlayerStats(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("AGS_PLAYER_STATS") == "0" {
		writeJSON(w, map[string]any{})
		return
	}
	id := r.PathValue("id")
	if id == "" {
		id = token.LocalPlayerID()
	}
	writeJSON(w, map[string]any{
		"ID": id,
		// ⚠⚠ MUST FIT IN int32. The first cut used s.store.partyVersion(), which is a MILLISECOND
		// timestamp (~1.79e12) and overflows int32 (max 2.147e9) by three orders of magnitude — a
		// matched key with the wrong width rejects the WHOLE struct, which is the failure the
		// comment above this function warns about, committed anyway two lines later. Caught by
		// eyeballing the served JSON before flighting it, not by any test.
		// Unix SECONDS is monotonic and int32-safe until 2038, which is the property we actually
		// want here ([S] insurance against a FParty/FMatchHistory-style monotonic gate).
		"Version": int32(time.Now().Unix()),
		"StatsByQueue": map[string]any{
			"tutorialNew": map[string]any{
				"ID": "tutorialNew",
				"StatsByHero": map[string]any{
					"ghost": heroStats(),
				},
			},
		},
	})
}

// heroStats returns one FPlayerHeroStats. Field names are [M] from the UHT FStructParams oracle
// (24 properties, SizeOf 0xa8) — not guessed, because a MATCHED key with the wrong type rejects
// the entire document while an unmatched key is silently ignored.
//
// ⚠ Placeholder values until match results are recorded per-player, same as the leaderboard rows.
// Non-zero on purpose: an all-zero stat block is indistinguishable from the {} we served before,
// which would make the flight uninterpretable.
func heroStats() map[string]any {
	return map[string]any{
		"GamesPlayed":       12,
		"TimePlayedSeconds": 8400,
		"Kills":             40,
		"MaxKills":          9,
		"MaxKillStreak":     4,
		"Knocks":            55,
		"MaxKnocks":         11,
		"Revives":           14,
		"MaxRevives":        3,
		"Revived":           9,
		"Resurrects":        2,
		"MaxResurrects":     1,
		"Resurrected":       5,
		"CreepKills":        310,
		"GoldEarned":        48200,
		"HeroDamageDealt":   129000,
		"MaxHeroDamageDealt": 21400,
		"HeroDamageTaken":    118000,
		"MaxHeroDamageTaken": 19800,
		"HealingGiven":       26400,
		"MaxHealingGiven":    5100,
		// int-keyed TMap -> JSON object with int-parsable STRING keys.
		//
		// ★★ `Placements` IS ZERO-INDEXED: key 0 == 1st place. [I], but strongly so — it is the
		// only reading that explains BOTH numbers the STATS page derives rather than echoes.
		// Serving {1:3, 2:5, 3:4} rendered `WINS 0` and `TOP 3 8`:
		//     1-indexed: WINS = P[1] = 3        (UI showed 0)  ✗
		//                TOP3 = P[1]+P[2]+P[3] = 12 (UI showed 8)  ✗   -- explains neither
		//     0-indexed: WINS = P[0] = absent = 0 (UI showed 0)  ✓
		//                TOP3 = P[0]+P[1]+P[2] = 0+3+5 = 8 (UI showed 8)  ✓ -- explains both
		// One rule, two independent matches, and the rival rule matches nothing.
		//
		// ★ PRE-REGISTERED PREDICTION for the next relaunch (this route is a LOGIN-TIME fetch, so
		// it cannot be tested without one): with the 0-indexed keys below, CAREER → STATS should
		// show **WINS 3** and **TOP 3 12**. If WINS stays 0, the hypothesis is wrong and the real
		// rule is something else — do not quietly re-explain it after the fact.
		"Placements": map[string]any{"0": 3, "1": 5, "2": 4},
	}
}
