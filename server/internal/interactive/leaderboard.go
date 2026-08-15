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
