package interactive

import "testing"

// TestPassLadderMatchesClient guards the XP table against a bad regeneration. These three values
// were observed in the LIVE client's own Progress Notif (requiredXP at tiers 0/12/34) — if a future
// dump reorders or rescales the ladder, the server would silently level players at the wrong pace
// while the client drew a different requirement.
func TestPassLadderMatchesClient(t *testing.T) {
	for _, c := range []struct{ tier, want int }{{0, 2000}, {12, 22000}, {34, 41000}} {
		if got := huntersJourneyXP[c.tier]; got != c.want {
			t.Fatalf("ladder[%d] = %d, want %d (client-observed requiredXP)", c.tier, got, c.want)
		}
	}
	if len(huntersJourneyXP) != 85 {
		t.Fatalf("ladder has %d tiers, want 85 (asset LevelRewards count)", len(huntersJourneyXP))
	}
}

// TestAdvancePassCarryOver covers the core levelling rule: XP is progress toward the NEXT tier and
// leftover carries over, so a single large grant can cross several tiers.
func TestAdvancePassCarryOver(t *testing.T) {
	// Exactly one tier's worth lands on tier 1 with nothing left over.
	got, up := advancePass(AccountPassProgress{}, 2000)
	if got.Level != 1 || got.XP != 0 || up != 1 {
		t.Fatalf("exact tier: got level=%d xp=%d up=%d, want 1/0/1", got.Level, got.XP, up)
	}

	// One short of the requirement does NOT advance.
	got, up = advancePass(AccountPassProgress{}, 1999)
	if got.Level != 0 || got.XP != 1999 || up != 0 {
		t.Fatalf("under tier: got level=%d xp=%d up=%d, want 0/1999/0", got.Level, got.XP, up)
	}

	// Crossing several tiers at once: 2000+2500+3000 = 7500 clears tiers 0,1,2 exactly;
	// the extra 500 must carry toward tier 3.
	got, up = advancePass(AccountPassProgress{}, 8000)
	if got.Level != 3 || got.XP != 500 || up != 3 {
		t.Fatalf("multi-tier: got level=%d xp=%d up=%d, want 3/500/3", got.Level, got.XP, up)
	}

	// Existing XP is included in the roll-up (partial progress + a grant tips the tier).
	got, up = advancePass(AccountPassProgress{Level: 12, XP: 21000}, 1000)
	if got.Level != 13 || got.XP != 0 || up != 1 {
		t.Fatalf("from partial: got level=%d xp=%d up=%d, want 13/0/1", got.Level, got.XP, up)
	}
}

// TestAdvancePassNonMonotonic pins the behaviour the ladder's shape demands. The table DIPS
// (tier 19 costs 29000, tier 20 only 25000), so levelling must subtract tier by tier — any
// closed-form/cumulative shortcut would compute the wrong tier here.
func TestAdvancePassNonMonotonic(t *testing.T) {
	if huntersJourneyXP[19] <= huntersJourneyXP[20] {
		t.Fatalf("precondition lost: ladder no longer dips at 19->20 (%d -> %d)",
			huntersJourneyXP[19], huntersJourneyXP[20])
	}
	// Sitting at tier 19, granting exactly tier 19 + tier 20 must land on 21 with nothing over.
	want := huntersJourneyXP[19] + huntersJourneyXP[20]
	got, up := advancePass(AccountPassProgress{Level: 19}, want)
	if got.Level != 21 || got.XP != 0 || up != 2 {
		t.Fatalf("dip: got level=%d xp=%d up=%d, want 21/0/2", got.Level, got.XP, up)
	}
}

// TestAdvancePassCapsAtMaxTier: a huge grant parks at the top tier, clears the bar, and marks the
// track complete rather than running off the end of the ladder.
func TestAdvancePassCapsAtMaxTier(t *testing.T) {
	got, _ := advancePass(AccountPassProgress{}, 1<<30)
	if got.Level != MaxPassTier {
		t.Fatalf("cap: level=%d, want %d", got.Level, MaxPassTier)
	}
	if got.XP != 0 || !got.Cleared {
		t.Fatalf("cap: xp=%d cleared=%v, want 0/true", got.XP, got.Cleared)
	}
	// Already-capped stays capped and does not go backwards.
	again, up := advancePass(got, 50000)
	if again.Level != MaxPassTier || up != 0 {
		t.Fatalf("post-cap: level=%d up=%d, want %d/0", again.Level, up, MaxPassTier)
	}
}

// TestAdvancePassIgnoresNonPositive: a match worth nothing must not perturb stored progress.
func TestAdvancePassIgnoresNonPositive(t *testing.T) {
	start := AccountPassProgress{Level: 4, XP: 123}
	for _, gain := range []int{0, -500} {
		if got, up := advancePass(start, gain); got != start || up != 0 {
			t.Fatalf("gain %d changed progress: %+v (up=%d)", gain, got, up)
		}
	}
}

// TestPassXPForRules covers the award table and the explicit passthrough.
func TestPassXPForRules(t *testing.T) {
	// Base only.
	if got, _ := passXPFor(matchResult{}); got != 1000 {
		t.Fatalf("empty match: %d, want 1000 (base)", got)
	}
	// 1st-place win with 8 knocks + 2 assists:
	// 1000 base + 1500 win + 500 top3 + 8*50 + 2*25 = 3450.
	total, breakdown := passXPFor(matchResult{Win: true, Placement: 1, Knocks: 8, Assists: 2})
	if total != 3450 {
		t.Fatalf("tournament win: %d, want 3450 (breakdown %v)", total, breakdown)
	}
	if breakdown["knocks"] != 400 || breakdown["win"] != 1500 {
		t.Fatalf("breakdown wrong: %v", breakdown)
	}
	// Explicit grant stacks on top of the rules.
	if got, b := passXPFor(matchResult{PassXP: 250}); got != 1250 || b["explicit"] != 250 {
		t.Fatalf("explicit: %d (%v), want 1250 with explicit=250", got, b)
	}
}

// TestMatchResultGrantsPassXP is the end-to-end path: the same POST that advances missions also
// advances the account pass, credited to the single player on file WITHOUT the client naming an id.
func TestMatchResultGrantsPassXP(t *testing.T) {
	s, mux := newTestService()
	const player = "player-1"
	// Give the player some state so exactly one real account exists to infer.
	s.store.update(player, func(st *playerState) { st.SelectedHeroAssetId = "Hero:beebo" })

	// 1st-place win, 8 knocks, 2 assists = 3450 XP -> clears tier 0 (2000) and tier 1 (2500)?
	// 3450 covers tier 0 (2000) with 1450 left, which is short of tier 1 (2500) -> level 1, xp 1450.
	doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"gameMode":"tournament"}`)

	got := s.AccountPass(player)
	if got.Level != 1 || got.XP != 1450 {
		t.Fatalf("after match: level=%d xp=%d, want 1/1450", got.Level, got.XP)
	}

	// A second identical match accumulates on top (1450 + 3450 = 4900; tier 1 costs 2500 ->
	// level 2 with 2400 carried, which is short of tier 2's 3000).
	doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"gameMode":"tournament"}`)
	got = s.AccountPass(player)
	if got.Level != 2 || got.XP != 2400 {
		t.Fatalf("after 2nd match: level=%d xp=%d, want 2/2400", got.Level, got.XP)
	}
}

// TestMatchResultPassSkippedWhenAmbiguous: with no player (or several) and no explicit playerId we
// must not guess an account — but the MISSION side of the match still has to apply.
func TestMatchResultPassSkippedWhenAmbiguous(t *testing.T) {
	s, mux := newTestService()

	// No players on file at all. Key is the CATALOG composite (S120) — the bare objective name was
	// the old empty-manifest fallback, which is no longer taken because the catalog is never empty.
	res := doJSON(t, mux, "POST", "/revival/missions/match-result", `{"win":true}`)
	if o := objectivesOf(t, res); o["ArmoryDaily_PlayAGame/PlayAGame"] != 1 {
		t.Fatalf("missions should still apply with no player: %v", o)
	}

	// Two players, no explicit id -> ambiguous, so nobody is credited.
	s.store.update("p1", func(st *playerState) { st.SelectedHeroAssetId = "Hero:beebo" })
	s.store.update("p2", func(st *playerState) { st.SelectedHeroAssetId = "Hero:ronin" })
	doJSON(t, mux, "POST", "/revival/missions/match-result", `{"win":true}`)
	if p := s.AccountPass("p1"); p.Level != 0 || p.XP != 0 {
		t.Fatalf("ambiguous match credited p1: %+v", p)
	}
	if p := s.AccountPass("p2"); p.Level != 0 || p.XP != 0 {
		t.Fatalf("ambiguous match credited p2: %+v", p)
	}

	// An explicit playerId resolves the ambiguity.
	doJSON(t, mux, "POST", "/revival/missions/match-result", `{"win":true,"playerId":"p2"}`)
	if p := s.AccountPass("p2"); p.XP == 0 && p.Level == 0 {
		t.Fatalf("explicit playerId was not credited: %+v", p)
	}
	if p := s.AccountPass("p1"); p.Level != 0 || p.XP != 0 {
		t.Fatalf("explicit playerId leaked to p1: %+v", p)
	}
}
