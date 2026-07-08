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
