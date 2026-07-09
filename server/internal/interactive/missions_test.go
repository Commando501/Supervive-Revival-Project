package interactive

import "testing"

// objectivesOf pulls the {"objectives": {...}} map out of a mission-progress response.
func objectivesOf(t *testing.T, m map[string]any) map[string]float64 {
	t.Helper()
	raw, ok := m["objectives"].(map[string]any)
	if !ok {
		t.Fatalf("response missing objectives object: %v", m)
	}
	out := map[string]float64{}
	for k, v := range raw {
		f, ok := v.(float64)
		if !ok {
			t.Fatalf("objective %q not a number: %T", k, v)
		}
		out[k] = f
	}
	return out
}

// TestMissionProgressRoundTrip covers the Option-2 read/apply loop the client-side
// shim depends on: empty by default, set writes absolute values, add increments, and
// each mutation round-trips on the GET the shim reads.
func TestMissionProgressRoundTrip(t *testing.T) {
	_, mux := newTestService()

	// Fresh player: no progress yet -> empty objectives (a "not started" baseline).
	if got := objectivesOf(t, doJSON(t, mux, "GET", "/revival/missions/progress", "")); len(got) != 0 {
		t.Fatalf("fresh progress not empty: %v", got)
	}

	// SET absolute values (the seed / reconcile shape).
	set := doJSON(t, mux, "POST", "/revival/missions/progress",
		`{"objectives":{"PlayAGame":5,"BR_Knocks_Assists":17}}`)
	if o := objectivesOf(t, set); o["PlayAGame"] != 5 || o["BR_Knocks_Assists"] != 17 {
		t.Fatalf("set did not persist: %v", o)
	}

	// ADD deltas (the match-end hook shape): existing key increments, missing key
	// starts at 0; an untouched key is preserved.
	add := doJSON(t, mux, "POST", "/revival/missions/progress/add",
		`{"objectives":{"PlayAGame":2,"a2winarenagames":1}}`)
	o := objectivesOf(t, add)
	if o["PlayAGame"] != 7 {
		t.Fatalf("add did not increment PlayAGame: got %v want 7", o["PlayAGame"])
	}
	if o["a2winarenagames"] != 1 {
		t.Fatalf("add did not create a2winarenagames: got %v want 1", o["a2winarenagames"])
	}
	if o["BR_Knocks_Assists"] != 17 {
		t.Fatalf("add clobbered untouched BR_Knocks_Assists: got %v want 17", o["BR_Knocks_Assists"])
	}

	// The GET the shim actually reads reflects the accumulated state.
	if o := objectivesOf(t, doJSON(t, mux, "GET", "/revival/missions/progress", "")); o["PlayAGame"] != 7 {
		t.Fatalf("GET did not reflect accumulated progress: %v", o)
	}
}

// TestMatchResultMapping covers Option 2c: a match summary advances the right objectives by the
// right amounts (mapped rules + explicit passthrough), and a second match accumulates.
func TestMatchResultMapping(t *testing.T) {
	_, mux := newTestService()

	// A tournament win: 8 knocks, 2 assists, 1st place, 3 chests, 40 minions.
	got := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"chestsOpened":3,"minionKills":40,"gameMode":"tournament"}`))
	checks := map[string]float64{
		"PlayAGame":         1,  // any game
		"a2winarenagames":   1,  // win (tournament)
		"BR_WinABR":         1,  // win (weekly)
		"BR_3Top4":          1,  // top 3
		"BR_Knocks_Assists": 10, // knocks+assists
		"BR_Knocks":         8,  // knocks (daily)
		"BR_Boxes":          3,  // chests
		"BR_Minions":        40, // minions
		"TopXWithFullArmory": 1, // top 6
	}
	for k, want := range checks {
		if got[k] != want {
			t.Fatalf("match-result objective %q = %v, want %v (full: %v)", k, got[k], want, got)
		}
	}
	// An unrelated objective must NOT be touched by a zero-stat rule.
	if _, ok := got["BR_Sunrises"]; ok {
		t.Fatalf("BR_Sunrises should be absent (no sunrises in the match): %v", got)
	}
	// A trios coop match with an explicit passthrough delta accumulates on top.
	got2 := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"gameMode":"trios","objectives":{"BR_Sunrises":2}}`))
	if got2["PlayAGame"] != 2 {
		t.Fatalf("second match did not accumulate PlayAGame: %v", got2["PlayAGame"])
	}
	if got2["Onboarding_PlayTriosMatch"] != 1 {
		t.Fatalf("trios game did not advance Onboarding_PlayTriosMatch: %v", got2)
	}
	if got2["BR_Sunrises"] != 2 {
		t.Fatalf("explicit passthrough delta not applied: %v", got2["BR_Sunrises"])
	}
}

// TestMatchResultManifestFanout covers per-mission granularity: with a manifest registered, a match's
// objective-name delta fans out to EACH mission that has the objective, keyed by "<mission>/<objective>",
// so missions sharing an objective name (PlayAGame on Tournament + a Daily) track independently.
func TestMatchResultManifestFanout(t *testing.T) {
	_, mux := newTestService()
	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"Tournament_PlayAGame","objective":"PlayAGame","max":5},
		{"mission":"ArmoryDaily_PlayAGame","objective":"PlayAGame","max":1},
		{"mission":"Tournament_KnocksAssists","objective":"BR_Knocks_Assists","max":50}
	]}`)

	got := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"gameMode":"tournament"}`))
	if got["Tournament_PlayAGame/PlayAGame"] != 1 {
		t.Fatalf("tournament play composite: %v", got)
	}
	if got["ArmoryDaily_PlayAGame/PlayAGame"] != 1 {
		t.Fatalf("daily play composite (independent): %v", got)
	}
	if got["Tournament_KnocksAssists/BR_Knocks_Assists"] != 10 {
		t.Fatalf("knocks+assists composite: %v", got)
	}
	// With a manifest registered, the bare objective name must NOT be a key (composite only).
	if _, ok := got["PlayAGame"]; ok {
		t.Fatalf("bare objective name leaked into composite store: %v", got)
	}
	// A second tournament game accumulates each composite independently.
	got2 := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result", `{"gameMode":"tournament"}`))
	if got2["Tournament_PlayAGame/PlayAGame"] != 2 || got2["ArmoryDaily_PlayAGame/PlayAGame"] != 2 {
		t.Fatalf("second game did not accumulate composites independently: %v", got2)
	}
}
