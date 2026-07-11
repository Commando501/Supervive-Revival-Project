package interactive

import (
	"encoding/json"
	"testing"
)

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

// reencode re-marshals a doJSON response and decodes it into a typed value (the response is a generic
// map; this pulls out the typed sub-structures without hand-walking any).
func reencode(t *testing.T, m map[string]any, out any) {
	t.Helper()
	b, err := json.Marshal(m)
	if err != nil {
		t.Fatalf("marshal response: %v", err)
	}
	if err := json.Unmarshal(b, out); err != nil {
		t.Fatalf("decode response into %T: %v", out, err)
	}
}

// TestManifestGetRoundTrip covers the new read-back of the (previously write-only) manifest, including
// the optional pool/xp enrichment.
func TestManifestGetRoundTrip(t *testing.T) {
	_, mux := newTestService()
	// Fresh: empty array (not null), so a reader never has to special-case nil.
	var empty struct {
		Entries []ManifestEntry `json:"entries"`
	}
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/manifest", ""), &empty)
	if empty.Entries == nil || len(empty.Entries) != 0 {
		t.Fatalf("fresh manifest GET should be empty non-nil, got %#v", empty.Entries)
	}

	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"DailyPlay","objective":"PlayAGame","max":1,"pool":"Dailies","xp":500},
		{"mission":"WeeklyKnocks","objective":"BR_Knocks","max":50,"pool":"Weeklies","xp":2500}
	]}`)

	var got struct {
		Entries []ManifestEntry `json:"entries"`
	}
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/manifest", ""), &got)
	if len(got.Entries) != 2 {
		t.Fatalf("manifest GET count: %v", got.Entries)
	}
	if got.Entries[0].Pool != "Dailies" || got.Entries[0].XP != 500 {
		t.Fatalf("manifest enrichment not round-tripped: %#v", got.Entries[0])
	}
}

type statusResp struct {
	Missions []MissionStatus `json:"missions"`
	Summary  struct {
		Total    int     `json:"total"`
		Complete int     `json:"complete"`
		XPEarned float64 `json:"xpEarned"`
	} `json:"summary"`
}

// TestMissionStatusCompletion covers the server-side completion computation: a mission is complete only
// when ALL its objectives reach their max, and XP earned sums only completed missions.
func TestMissionStatusCompletion(t *testing.T) {
	_, mux := newTestService()
	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"DailyPlay","objective":"PlayAGame","max":1,"pool":"Dailies","xp":500},
		{"mission":"WeeklyCombo","objective":"BR_Knocks","max":10,"pool":"Weeklies","xp":2500},
		{"mission":"WeeklyCombo","objective":"BR_WinABR","max":1,"pool":"Weeklies","xp":2500}
	]}`)

	// Nothing done yet -> zero complete.
	var s0 statusResp
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/status", ""), &s0)
	if s0.Summary.Total != 2 || s0.Summary.Complete != 0 || s0.Summary.XPEarned != 0 {
		t.Fatalf("fresh status summary: %+v", s0.Summary)
	}

	// Complete the single-objective daily; partially advance the two-objective weekly (only 1 of 2).
	doJSON(t, mux, "POST", "/revival/missions/progress", `{"objectives":{
		"DailyPlay/PlayAGame":1,
		"WeeklyCombo/BR_Knocks":10
	}}`)
	var s1 statusResp
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/status", ""), &s1)
	if s1.Summary.Complete != 1 || s1.Summary.XPEarned != 500 {
		t.Fatalf("after daily complete: %+v", s1.Summary)
	}
	byName := map[string]MissionStatus{}
	for _, m := range s1.Missions {
		byName[m.Mission] = m
	}
	if !byName["DailyPlay"].Complete {
		t.Fatalf("DailyPlay should be complete: %+v", byName["DailyPlay"])
	}
	if byName["WeeklyCombo"].Complete {
		t.Fatalf("WeeklyCombo should be INcomplete (only 1 of 2 objectives): %+v", byName["WeeklyCombo"])
	}

	// Finish the weekly's second objective -> both complete, XP sums both.
	doJSON(t, mux, "POST", "/revival/missions/progress", `{"objectives":{"WeeklyCombo/BR_WinABR":1}}`)
	var s2 statusResp
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/status", ""), &s2)
	if s2.Summary.Complete != 2 || s2.Summary.XPEarned != 3000 {
		t.Fatalf("after weekly complete: %+v", s2.Summary)
	}
}

// TestMissionRotation covers the daily/weekly reset: rotating a pool clears only that pool's composite
// progress and leaves other pools untouched.
func TestMissionRotation(t *testing.T) {
	_, mux := newTestService()
	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"DailyPlay","objective":"PlayAGame","max":1,"pool":"Dailies"},
		{"mission":"WeeklyKnocks","objective":"BR_Knocks","max":50,"pool":"Weeklies"}
	]}`)
	doJSON(t, mux, "POST", "/revival/missions/progress", `{"objectives":{
		"DailyPlay/PlayAGame":1,
		"WeeklyKnocks/BR_Knocks":30
	}}`)

	// Rotate the Dailies pool: its composite is cleared, the Weekly survives.
	var rot struct {
		Cleared []string `json:"cleared"`
	}
	reencode(t, doJSON(t, mux, "POST", "/revival/missions/rotate", `{"pool":"Dailies"}`), &rot)
	if len(rot.Cleared) != 1 || rot.Cleared[0] != "DailyPlay/PlayAGame" {
		t.Fatalf("rotate cleared wrong keys: %v", rot.Cleared)
	}
	after := objectivesOf(t, doJSON(t, mux, "GET", "/revival/missions/progress", ""))
	if _, ok := after["DailyPlay/PlayAGame"]; ok {
		t.Fatalf("daily composite should be cleared after rotation: %v", after)
	}
	if after["WeeklyKnocks/BR_Knocks"] != 30 {
		t.Fatalf("weekly composite should survive daily rotation: %v", after)
	}
}

// TestMissionCoverage covers the match-result coverage report: a mission is "full" when every objective
// has a rule, "partial" when some do, "none" when none do; unmapped objectives and unused rules are listed.
func TestMissionCoverage(t *testing.T) {
	_, mux := newTestService()
	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"DailyPlay","objective":"PlayAGame","max":1,"pool":"Dailies"},
		{"mission":"WeeklyCombo","objective":"BR_Knocks","max":10,"pool":"Weeklies"},
		{"mission":"WeeklyCombo","objective":"SomeHeroThing","max":5,"pool":"Weeklies"},
		{"mission":"HeroAbility","objective":"Alchemist_HealWithQ","max":100,"pool":"HunterMissions"}
	]}`)

	var rep CoverageReport
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/coverage", ""), &rep)

	if rep.Summary.MissionsTotal != 3 || rep.Summary.MissionsFullyTrackable != 1 ||
		rep.Summary.MissionsPartial != 1 || rep.Summary.MissionsUntrackable != 1 {
		t.Fatalf("mission coverage counts: %+v", rep.Summary)
	}
	if rep.Summary.ObjectivesTotal != 4 || rep.Summary.ObjectivesMapped != 2 || rep.Summary.ObjectivesUnmapped != 2 {
		t.Fatalf("objective coverage counts: %+v", rep.Summary)
	}
	// Per-mission classification.
	byName := map[string]MissionCoverage{}
	for _, m := range rep.Missions {
		byName[m.Mission] = m
	}
	if byName["DailyPlay"].Coverage != "full" {
		t.Fatalf("DailyPlay should be full: %+v", byName["DailyPlay"])
	}
	if byName["WeeklyCombo"].Coverage != "partial" {
		t.Fatalf("WeeklyCombo should be partial: %+v", byName["WeeklyCombo"])
	}
	if byName["HeroAbility"].Coverage != "none" {
		t.Fatalf("HeroAbility should be none: %+v", byName["HeroAbility"])
	}
	// Unmapped list is exactly the two unmapped objective names, sorted.
	if len(rep.UnmappedObjectives) != 2 || rep.UnmappedObjectives[0] != "Alchemist_HealWithQ" || rep.UnmappedObjectives[1] != "SomeHeroThing" {
		t.Fatalf("unmapped objectives: %v", rep.UnmappedObjectives)
	}
	// Unused rules exclude the two that matched, and include a known-present rule.
	used := map[string]bool{}
	for _, u := range rep.UnusedRules {
		used[u] = true
	}
	if used["PlayAGame"] || used["BR_Knocks"] {
		t.Fatalf("a matched rule leaked into unusedRules: %v", rep.UnusedRules)
	}
	if !used["a2winarenagames"] {
		t.Fatalf("an unused rule (a2winarenagames) should be listed: %v", rep.UnusedRules)
	}
	if rep.Summary.RulesUnused != len(rep.UnusedRules) || rep.Summary.RulesTotal < rep.Summary.RulesUnused {
		t.Fatalf("rules summary inconsistent: %+v (unused=%v)", rep.Summary, rep.UnusedRules)
	}
}
