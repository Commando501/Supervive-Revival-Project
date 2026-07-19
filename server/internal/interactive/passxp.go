package interactive

// Hunter's Journey (account pass) XP from match results — S83.
//
// The PASSES ladder renders from FPlayerProgression.AccountPass{Level,XP} which we serve on
// GET /progression/players/{id} (see handleGetProgression). Until now those values only moved
// when an operator edited them in the admin panel. This file grants them from actual match
// results, reusing the same POST /revival/missions/match-result the mission engine consumes,
// so one reported match advances missions AND the pass.
//
// WHY THE SERVER NEEDS THE XP LADDER
// The client does NOT level the pass up for us. It treats Level as a tier INDEX and XP as
// progress toward the NEXT tier, and it computes that tier's requirement itself from the packed
// asset (HuntersJourneyLevelProgression_C's CDO). So serving XP above the requirement just draws
// a full bar forever — the tier only advances when the SERVER raises Level. That means the server
// has to know the same ladder the client does, hence the table below.

// huntersJourneyXP[tier] is the XP required to complete that tier, i.e. exactly the requiredXP the
// client reports for a player sitting at that tier.
//
// PROVENANCE — dumped from the LIVE process, not guessed: the packed asset
// Default__HuntersJourney_C -> LevelClass (+0xB8) HuntersJourneyLevelProgression_C -> its CDO
// (+0x178) -> an int32 array at CDO+0x30 with the count (85) at CDO+0x38.
// VERIFIED against the client's own behaviour: Loki.log's Progress Notif reported requiredXP
// 2000 at tier 0, 22000 at tier 12 and 41000 at tier 34, and this table holds exactly those
// values at those indices.
// NOTE it is deliberately NOT monotonic (it dips at 20, 30, 40, 55...) — these are PER-TIER
// requirements, not a cumulative curve, so levelling must subtract tier by tier.
// TO REGENERATE (only needed if the game build changes):
//
//	python <scratchpad>/dump_xp_ladder.py   — prints this literal plus the self-check
var huntersJourneyXP = []int{
	2000, 2500, 3000, 4000, 10000, 9000, 12000, 13500, 14500, 16500,
	18500, 20500, 22000, 23000, 24000, 25000, 26000, 27000, 28000, 29000,
	25000, 27000, 29000, 31000, 33000, 35000, 37000, 39000, 41000, 43000,
	33000, 35000, 37000, 39000, 41000, 43000, 45000, 47000, 49000, 51000,
	41000, 43000, 45000, 47000, 49000, 51000, 53000, 55000, 57000, 59000,
	61000, 63000, 65000, 67000, 69000, 49000, 51000, 53000, 55000, 57000,
	49000, 51000, 53000, 55000, 57000, 49000, 51000, 53000, 55000, 57000,
	49000, 51000, 53000, 55000, 57000, 49000, 51000, 53000, 55000, 57000,
	49000, 51000, 53000, 55000, 57000,
}

// MaxPassTier is the highest tier index a player can reach. The asset carries 85 per-tier
// requirements (tiers 0..84) and the client builds 86 level view models, so tier 85 is the
// "finished the whole track" state — that is where we stop and set Cleared.
var MaxPassTier = len(huntersJourneyXP)

// passXPRules maps a match result to account-pass XP, in the same shape as missions.go's
// objectiveRules so both tables read alike and can be tuned side by side.
//
// These numbers are OURS, not the original game's — the real award table lived on the dead
// backend and is not recoverable from the client. They are tuned so an average match is worth
// roughly one early tier (2000) and clearly less than a late one (~50000), i.e. early tiers feel
// quick and later ones take real play. Adjust freely; nothing in the client depends on them.
var passXPRules = []struct {
	Name string // shown in the admin panel's breakdown
	XP   func(m matchResult) int
}{
	{"match played", func(m matchResult) int { return 1000 }},
	{"win", func(m matchResult) int { return int(b2f(m.Win)) * 1500 }},
	{"top 3", func(m matchResult) int { return int(b2f(m.Placement >= 1 && m.Placement <= 3)) * 500 }},
	{"knocks", func(m matchResult) int { return int(m.Knocks) * 50 }},
	{"assists", func(m matchResult) int { return int(m.Assists) * 25 }},
	{"team wipes", func(m matchResult) int { return int(m.TeamWipes) * 150 }},
	{"boss kills", func(m matchResult) int { return int(m.BossKills) * 100 }},
	{"bonfires captured", func(m matchResult) int { return int(m.BonfiresCaptured) * 75 }},
	{"vaults opened", func(m matchResult) int { return int(m.VaultsOpened) * 50 }},
	{"chests opened", func(m matchResult) int { return int(m.ChestsOpened) * 10 }},
	{"minion kills", func(m matchResult) int { return int(m.MinionKills) * 5 }},
}

// PassAward reports what one match granted the account pass.
type PassAward struct {
	// PlayerID is the account credited. Empty means nothing was credited (no player resolved) —
	// the mission side of the match still applies.
	PlayerID string `json:"playerId,omitempty"`
	// Breakdown is per-rule XP, for the admin panel and for explaining a grant.
	Breakdown map[string]int `json:"breakdown,omitempty"`
	XPGained  int            `json:"xpGained"`
	TiersUp   int            `json:"tiersUp"`
	// Before/After are the pass progress either side of this match.
	Before AccountPassProgress `json:"before"`
	After  AccountPassProgress `json:"after"`
}

// passXPFor totals the rule table for a match, returning the total and the per-rule breakdown.
func passXPFor(m matchResult) (int, map[string]int) {
	total := 0
	breakdown := map[string]int{}
	for _, r := range passXPRules {
		if v := r.XP(m); v != 0 {
			breakdown[r.Name] += v
			total += v
		}
	}
	if m.PassXP != 0 { // explicit override/passthrough, same spirit as matchResult.Objectives
		breakdown["explicit"] += m.PassXP
		total += m.PassXP
	}
	return total, breakdown
}

// advancePass adds XP and rolls the tier forward while each tier's requirement is met.
// Carry-over is preserved (leftover XP counts toward the next tier), which is why this loops
// instead of doing a single division: the ladder is non-monotonic, so there is no closed form.
func advancePass(p AccountPassProgress, gain int) (AccountPassProgress, int) {
	if gain <= 0 {
		return p, 0
	}
	p.XP += gain
	tiersUp := 0
	for p.Level < len(huntersJourneyXP) {
		need := huntersJourneyXP[p.Level]
		if need <= 0 || p.XP < need {
			break
		}
		p.XP -= need
		p.Level++
		tiersUp++
	}
	// Track finished: park at the top tier with no dangling progress bar.
	if p.Level >= MaxPassTier {
		p.Level = MaxPassTier
		p.XP = 0
		p.Cleared = true
	}
	return p, tiersUp
}

// passPlayerID decides which account a match credits.
//   - an explicit playerId wins. On the game-facing route handleMatchResult fills this in from the
//     caller's Bearer token, so the real gameplay path is always exact, never inferred;
//   - otherwise, if exactly ONE real player has state, credit them (convenience for the admin
//     panel's match simulator, which has no auth context).
//
// With zero or several players and no explicit id we return "" and skip the pass grant rather than
// guessing — crediting the wrong account would be silent and annoying to undo. This is not
// hypothetical: a single stale account left in state/interactive.json is enough to make the
// fallback ambiguous, which is exactly what happened the first time this ran live.
func (s *Service) passPlayerID(explicit string) string {
	if explicit != "" {
		return explicit
	}
	if ids := s.PlayerIDs(); len(ids) == 1 {
		return ids[0]
	}
	return ""
}

// applyPassXP grants a match's pass XP to the resolved player. Safe to call for every match:
// it no-ops (returning a zero award) when no player resolves or the match is worth nothing.
func (s *Service) applyPassXP(m matchResult) PassAward {
	id := s.passPlayerID(m.PlayerID)
	if id == "" {
		return PassAward{}
	}
	gain, breakdown := passXPFor(m)
	before := s.AccountPass(id)
	if gain <= 0 {
		return PassAward{PlayerID: id, Before: before, After: before}
	}
	after, tiersUp := advancePass(before, gain)
	after = s.SetAccountPass(id, after)
	return PassAward{
		PlayerID:  id,
		Breakdown: breakdown,
		XPGained:  gain,
		TiersUp:   tiersUp,
		Before:    before,
		After:     after,
	}
}
