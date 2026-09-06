package interactive

import (
	"encoding/json"
	"sort"
	"strings"
	"testing"
	"time"
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
//
// ⚠ The expected keys are REAL catalog missions and REAL data-asset objective names, not synthetic
// ones. That is the point: before S120 the rules were keyed by the shim manifest's names
// ("BR_Knocks", "a2winarenagames"), which the data assets do not use ("Knocks", "A2_WinArenaGames"),
// so a match advanced 2 of 102 objectives. A test built on synthetic names cannot see that class of
// bug — it has to name the same strings the shipped assets do.
func TestMatchResultMapping(t *testing.T) {
	_, mux := newTestService()

	// A tournament win: 8 knocks, 2 assists, 1st place, 3 chests, 40 minions.
	got := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"chestsOpened":3,"minionKills":40,"gameMode":"tournament"}`))
	checks := map[string]float64{
		"ArmoryDaily_PlayAGame/PlayAGame":                            1,  // any game
		"Tournament_PlayAGame_1/PlayAGame":                           1,  // ... and independently here
		"Tournament_WinGame_1/A2_WinArenaGames":                      1,  // win (tournament)
		"Armory_WeeklyWinGame/WinABR":                                1,  // win (weekly)
		"Tournament_Top3_1/Top3":                                     1,  // top 3
		"Tournament_KnocksAssists_1/Knocks_Assists":                  10, // knocks+assists
		"ArmoryDaily_GetKnocks/Knocks":                               8,  // knocks (daily)
		"Armory_WeeklyBoxes/Boxes":                                   3,  // chests
		"Armory_WeeklyMinions/KillMinions":                           40, // minions
		"Armory_WeeklyPurchaseEquipment/TopXWithFullArmoryInventory": 1,  // top 6
	}
	for k, want := range checks {
		if got[k] != want {
			t.Fatalf("match-result objective %q = %v, want %v (full: %v)", k, got[k], want, got)
		}
	}
	// An unrelated objective must NOT be touched by a zero-stat rule.
	if _, ok := got["ArmoryDaily_Sunrises/Sunrises"]; ok {
		t.Fatalf("Sunrises should be absent (no sunrises in the match): %v", got)
	}
	// A trios match with an explicit passthrough delta accumulates on top.
	got2 := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"gameMode":"trios","objectives":{"ArmoryDaily_Sunrises/Sunrises":2}}`))
	if got2["ArmoryDaily_PlayAGame/PlayAGame"] != 2 {
		t.Fatalf("second match did not accumulate PlayAGame: %v", got2["ArmoryDaily_PlayAGame/PlayAGame"])
	}
	if got2["PlayTriosMatch/PlayTrios"] != 1 {
		t.Fatalf("trios game did not advance the PlayTrios mission: %v", got2)
	}
	if got2["ArmoryDaily_Sunrises/Sunrises"] != 2 {
		t.Fatalf("explicit passthrough delta not applied: %v", got2["ArmoryDaily_Sunrises/Sunrises"])
	}
}

// TestMatchResultCatalogFanout covers per-mission granularity: a match's objective-name delta fans
// out to EACH catalog mission carrying that objective, keyed "<mission>/<objective>", so missions
// sharing an objective name track independently. PlayAGame is shared by ArmoryDaily_PlayAGame
// (max 1) and Tournament_PlayAGame_1 (max 5) in the shipped data.
//
// ⚠ Renamed from TestMatchResultManifestFanout: the fan-out source is the CATALOG now, not the shim
// manifest. The old test registered a manifest and asserted it drove the fan-out — behaviour that
// wrote keys missionInfo never reads (7 of 187 matched). See catalogManifest.
func TestMatchResultCatalogFanout(t *testing.T) {
	_, mux := newTestService()

	got := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":8,"assists":2,"gameMode":"tournament"}`))
	if got["Tournament_PlayAGame_1/PlayAGame"] != 1 {
		t.Fatalf("tournament play composite: %v", got)
	}
	if got["ArmoryDaily_PlayAGame/PlayAGame"] != 1 {
		t.Fatalf("daily play composite (independent): %v", got)
	}
	if got["Tournament_KnocksAssists_1/Knocks_Assists"] != 10 {
		t.Fatalf("knocks+assists composite: %v", got)
	}
	// The bare objective name must NOT be a key — only composites are readable by missionInfo.
	if _, ok := got["PlayAGame"]; ok {
		t.Fatalf("bare objective name leaked into composite store: %v", got)
	}
	// A registered shim manifest must NOT override the catalog: its names are a different
	// (and mostly wrong) name space, and letting it win is exactly the S120 defect.
	doJSON(t, mux, "POST", "/revival/missions/manifest", `{"entries":[
		{"mission":"Tournament_PlayAGame","objective":"PlayAGame","max":5}
	]}`)
	got2 := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result", `{"gameMode":"tournament"}`))
	if got2["Tournament_PlayAGame_1/PlayAGame"] != 2 || got2["ArmoryDaily_PlayAGame/PlayAGame"] != 2 {
		t.Fatalf("second game did not accumulate catalog composites independently: %v", got2)
	}
	if _, ok := got2["Tournament_PlayAGame/PlayAGame"]; ok {
		t.Fatalf("a registered manifest overrode the catalog and wrote an unservable key: %v", got2)
	}
}

// TestMatchResultKeysAreServable is the invariant that would have caught the S120 defect, and it is
// the reason this file is worth more than its individual assertions: EVERY key the match-result
// engine writes must be a key missionInfo actually serves and reads back. When the two disagree the
// progress is written, persisted, echoed by the API — and invisible in the game, which is precisely
// how it went unnoticed.
func TestMatchResultKeysAreServable(t *testing.T) {
	s, mux := newTestService()

	// A maximal match: every stat non-zero, so every rule with a stat fires at once.
	got := objectivesOf(t, doJSON(t, mux, "POST", "/revival/missions/match-result",
		`{"win":true,"placement":1,"knocks":5,"assists":5,"teamWipes":2,"minionKills":9,"bossKills":2,
		  "chestsOpened":4,"vaultsOpened":1,"bonfiresCaptured":3,"sunrises":1,"purchases":6,
		  "uniqueHeroes":2,"gameMode":"trios"}`))
	if len(got) == 0 {
		t.Fatal("a maximal match advanced nothing at all")
	}

	// Build the set of composite keys the served document can actually express.
	servable := map[string]bool{}
	mi, _ := s.missionInfo(time.Now().UTC())
	for _, md := range mi["MissionData"].([]any) {
		m := md.(map[string]any)
		name := strings.TrimPrefix(m["AssetId"].(string), "Mission:")
		for _, op := range m["ObjectiveProgress"].([]any) {
			servable[compositeKey(name, op.(map[string]any)["ObjectiveName"].(string))] = true
		}
	}

	// CONTROLS, so a pass here means something. The servable set must ACCEPT a key we know is
	// served and REJECT both shapes of key the pre-S120 code produced — a bare objective name
	// (the empty-manifest fallback) and a shim-manifest composite. Without these, `servable`
	// silently containing everything would make the assertion below vacuous.
	if !servable["ArmoryDaily_PlayAGame/PlayAGame"] {
		t.Fatal("control failed: a known-served composite key is not in the servable set")
	}
	if servable["PlayAGame"] {
		t.Fatal("control failed: a BARE objective name must not be servable")
	}
	if servable["Tournament_PlayAGame/PlayAGame"] {
		t.Fatal("control failed: a shim-manifest composite must not be servable " +
			"(the catalog calls that mission Tournament_PlayAGame_1)")
	}

	var unservable []string
	for k := range got {
		if !servable[k] {
			unservable = append(unservable, k)
		}
	}
	if len(unservable) > 0 {
		sort.Strings(unservable)
		t.Fatalf("match-result wrote %d key(s) missionInfo can never read (progress would be invisible):\n  %s",
			len(unservable), strings.Join(unservable, "\n  "))
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
// ⚠ Asserts INVARIANTS over the real embedded catalog, not exact counts against a synthetic
// manifest. The report now grades what we SERVE (the catalog), so a synthetic manifest no longer
// steers it — and exact totals would break on every legitimate catalog regeneration.
func TestMissionCoverage(t *testing.T) {
	_, mux := newTestService()

	var rep CoverageReport
	reencode(t, doJSON(t, mux, "GET", "/revival/missions/coverage", ""), &rep)

	if rep.Summary.MissionsTotal != len(missionCatalog) {
		t.Fatalf("coverage should grade the served catalog: MissionsTotal=%d, catalog=%d",
			rep.Summary.MissionsTotal, len(missionCatalog))
	}
	// Every mission must be classified into exactly one bucket.
	if got := rep.Summary.MissionsFullyTrackable + rep.Summary.MissionsPartial + rep.Summary.MissionsUntrackable; got != rep.Summary.MissionsTotal {
		t.Fatalf("buckets do not partition the missions: %+v", rep.Summary)
	}
	// The re-pointed rules must actually bite. Before S120 this was 2; a regression to a
	// near-miss name space would collapse it again, which is the whole point of the check.
	if rep.Summary.ObjectivesMapped < 15 {
		t.Fatalf("objective coverage collapsed to %d mapped — are the rules keyed by the "+
			"data-asset names or the shim's? %+v", rep.Summary.ObjectivesMapped, rep.Summary)
	}
	byName := map[string]MissionCoverage{}
	for _, m := range rep.Missions {
		byName[m.Mission] = m
	}
	// A generic daily is fully trackable from a plain match...
	if byName["ArmoryDaily_PlayAGame"].Coverage != "full" {
		t.Fatalf("ArmoryDaily_PlayAGame should be full: %+v", byName["ArmoryDaily_PlayAGame"])
	}
	if byName["Armory_WeeklyBoxes"].Coverage != "full" {
		t.Fatalf("Armory_WeeklyBoxes should be full: %+v", byName["Armory_WeeklyBoxes"])
	}
	// ...while a per-ability hero mission is not, and that is a property of the data (no match
	// stat expresses "heal allies with Cinnabar Cocktail"), not a missing rule.
	if byName["Alchemist_HealWithQ_1"].Coverage != "none" {
		t.Fatalf("a hero-mastery mission should be untrackable from a match summary: %+v",
			byName["Alchemist_HealWithQ_1"])
	}
	// The unmapped list must be dominated by the per-ability hero objectives, and must NOT contain
	// anything a match summary plainly expresses — a generic stat name showing up here means the
	// rules drifted off the data-asset name space again.
	unmapped := map[string]bool{}
	for _, u := range rep.UnmappedObjectives {
		unmapped[u] = true
	}
	for _, mustBeMapped := range []string{"PlayAGame", "Knocks", "WinABR", "Boxes", "KillMinions", "TeamWipes", "Top3"} {
		if unmapped[mustBeMapped] {
			t.Fatalf("%q is a plain match stat but has no rule — rules are off the data-asset "+
				"name space: %v", mustBeMapped, rep.UnmappedObjectives)
		}
	}
	if !unmapped["Alchemist_HealWithQ"] {
		t.Fatalf("a per-ability hero objective should be unmapped: %v", rep.UnmappedObjectives)
	}
	// Unused rules exclude the ones that matched, and DO include the retained shim-name aliases —
	// those are kept only for the -WithMissionsShim rollback path, so against the catalog they are
	// expected to be unused. That expectation is itself the tell that the two name spaces differ.
	used := map[string]bool{}
	for _, u := range rep.UnusedRules {
		used[u] = true
	}
	if used["PlayAGame"] || used["Knocks"] {
		t.Fatalf("a matched rule leaked into unusedRules: %v", rep.UnusedRules)
	}
	if !used["a2winarenagames"] || !used["BR_Knocks"] {
		t.Fatalf("the retained shim-name aliases should read as unused against the catalog: %v", rep.UnusedRules)
	}
	if rep.Summary.RulesUnused != len(rep.UnusedRules) || rep.Summary.RulesTotal < rep.Summary.RulesUnused {
		t.Fatalf("rules summary inconsistent: %+v (unused=%v)", rep.Summary, rep.UnusedRules)
	}
}
