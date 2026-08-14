package interactive

import (
	"fmt"
	"testing"
)

// These tests assert MEASURED facts about the Hero Mastery feed, not the implementation's own
// behaviour echoed back. The distinction matters here: CLAUDE.md records a case where the test
// that would have caught a wrong claim had itself ingested the wrong claim (the lobby
// vocabulary/push_test.go pair), so each assertion below is tied to something read out of the
// shipped assets or the binary.

// getProgression drives the real route so the test exercises route patterns and the real
// response assembly, not just the helper.
func getProgression(t *testing.T, id string) map[string]any {
	t.Helper()
	_, mux := newTestService()
	return doJSON(t, mux, "GET", "/progression/players/"+id, "")
}

// TestHeroMasteryIDsMatchShippedAssets guards the hero list against silent drift.
//
// MEASURED (tools/extractor/out/*Mastery_uasset.json, 2026-08-14): exactly 25
// LokiDataAsset_HeroMastery assets ship, and for all 25 InternalName == Hero.PrimaryAssetName.
// Those 25 names are the only valid FPrimaryAssetId name halves for this field.
func TestHeroMasteryIDsMatchShippedAssets(t *testing.T) {
	if got, want := len(heroMasteryIDs), 25; got != want {
		t.Errorf("heroMasteryIDs has %d entries, want %d (25 LokiDataAsset_HeroMastery assets ship)", got, want)
	}
	seen := map[string]bool{}
	for _, h := range heroMasteryIDs {
		if h == "" {
			t.Error("empty hero id in heroMasteryIDs")
		}
		// Case-insensitive, because FName matching is — two entries differing only by case
		// would collide on the client and silently serve one hero twice.
		key := lower(h)
		if seen[key] {
			t.Errorf("duplicate hero id (case-insensitively): %q", h)
		}
		seen[key] = true
	}
}

func lower(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 32
		}
	}
	return string(b)
}

// TestHeroMasteryOffByDefault is the blast-radius guard.
//
// A wrong-typed matched key rejects the WHOLE FPlayerProgression document, which would close the
// missions page, the Hunter's Journey pass and news-banner gate 2 at once. So the default must
// emit no HeroMastery key at all, leaving the document byte-identical to the pre-S120 one.
func TestHeroMasteryOffByDefault(t *testing.T) {
	got := getProgression(t, "p-off")
	if _, ok := got["HeroMastery"]; ok {
		t.Fatal("HeroMastery served with AGS_SERVE_HEROMASTERY unset; it must be opt-in")
	}
	// The three surfaces that ride this document must still be present.
	for _, k := range []string{"MissionInfo", "AccountPass", "Version", "ID"} {
		if _, ok := got[k]; !ok {
			t.Errorf("key %q missing from the default document", k)
		}
	}
}

// TestHeroMasteryModes checks the two candidate FPrimaryAssetId type prefixes.
//
// WHY BOTH ARE MODELLED: the evidence is split. "Hero:" is what disassembly shows
// GetHeroMastery being CALLED with (base+0x57B856E loads ULokiDataAsset_HeroMastery::Hero at
// +0xC0 and passes it), and the field is named HeroId. "HeroMastery:" is what the client's own
// log emits as progressionTrackId. Until one is confirmed live, both must be servable.
func TestHeroMasteryModes(t *testing.T) {
	for _, tc := range []struct {
		mode        string
		wantN       int
		wantPrefix  []string
	}{
		{"hero", 25, []string{"Hero:"}},
		{"mastery", 25, []string{"HeroMastery:"}},
		{"both", 50, []string{"Hero:", "HeroMastery:"}},
	} {
		t.Run(tc.mode, func(t *testing.T) {
			t.Setenv("AGS_SERVE_HEROMASTERY", tc.mode)
			got := getProgression(t, "p-"+tc.mode)
			raw, ok := got["HeroMastery"].([]any)
			if !ok {
				t.Fatalf("HeroMastery missing or not a JSON array: %#v", got["HeroMastery"])
			}
			if len(raw) != tc.wantN {
				t.Errorf("got %d entries, want %d", len(raw), tc.wantN)
			}
			perPrefix := map[string]int{}
			for i, e := range raw {
				m, ok := e.(map[string]any)
				if !ok {
					t.Fatalf("entry %d is not an object: %#v", i, e)
				}
				// Every scalar leaf of FHeroMasteryProgress we serve must be present; a missing
				// one is fine for UE (absent is safe) but signals an assembly bug here.
				for _, k := range []string{"HeroId", "Level", "XP", "Cleared"} {
					if _, ok := m[k]; !ok {
						t.Errorf("entry %d missing %q", i, k)
					}
				}
				id, _ := m["HeroId"].(string)
				matched := false
				for _, p := range tc.wantPrefix {
					// "HeroMastery:" also has the "Hero" substring, so count by exact prefix
					// and attribute to the LONGEST match.
					if len(id) > len(p) && id[:len(p)] == p {
						if p == "Hero:" && len(id) > len("HeroMastery:") && id[:len("HeroMastery:")] == "HeroMastery:" {
							continue
						}
						perPrefix[p]++
						matched = true
					}
				}
				if !matched {
					t.Errorf("entry %d HeroId %q matches no expected prefix %v", i, id, tc.wantPrefix)
				}
			}
			for _, p := range tc.wantPrefix {
				if perPrefix[p] != 25 {
					t.Errorf("prefix %q appeared %d times, want 25 (one per shipped hero)", p, perPrefix[p])
				}
			}
		})
	}
}

// TestHeroMasteryProbeDeltaDiscriminates covers the self-discriminating flight.
//
// In "both" mode with a nonzero AGS_HEROMASTERY_PROBE_DELTA, the "HeroMastery:"-typed duplicate
// carries a different Level from the "Hero:"-typed one, so whichever Level the UI draws NAMES the
// key the client actually consumed — resolving the prefix question in one launch instead of two.
func TestHeroMasteryProbeDeltaDiscriminates(t *testing.T) {
	t.Setenv("AGS_SERVE_HEROMASTERY", "both")
	t.Setenv("AGS_HEROMASTERY_PROBE_DELTA", "7")

	s, _ := newTestService()
	s.SetHeroMastery("p-probe", "Alchemist", HeroMasteryProgress{Level: 3, XP: 1500})
	entries, _ := s.heroMasteryEntries("p-probe")

	levels := map[string]int{}
	for _, e := range entries {
		m := e.(map[string]any)
		if id := m["HeroId"].(string); id == "Hero:Alchemist" || id == "HeroMastery:Alchemist" {
			levels[id] = m["Level"].(int)
		}
	}
	if got, want := levels["Hero:Alchemist"], 3; got != want {
		t.Errorf("Hero:Alchemist Level = %d, want %d (the stored value, unmodified)", got, want)
	}
	if got, want := levels["HeroMastery:Alchemist"], 10; got != want {
		t.Errorf("HeroMastery:Alchemist Level = %d, want %d (stored 3 + delta 7)", got, want)
	}
}

// TestHeroMasteryBaseLevelIsDigested is a regression test for a bug that was written and caught
// within one edit: the per-hero digest records the STORED level, so a diagnostic floor applied at
// serialization time is invisible to it. Version would then NOT advance when AGS_HEROMASTERY_BASE_LEVEL
// changed, the strict `>` adoption gate would drop the document, and the knob would read as inert.
//
// This is the same failure shape the file's header warns about, which is exactly why it is tested
// rather than merely commented.
func TestHeroMasteryBaseLevelIsDigested(t *testing.T) {
	t.Setenv("AGS_SERVE_HEROMASTERY", "hero")
	s, _ := newTestService()

	_, d0 := s.heroMasteryEntries("p-base")
	t.Setenv("AGS_HEROMASTERY_BASE_LEVEL", "3")
	entries, d3 := s.heroMasteryEntries("p-base")
	if d0 == d3 {
		t.Fatalf("digest unchanged when base level changed (%q); Version would not advance", d0)
	}
	for _, e := range entries {
		if lvl := e.(map[string]any)["Level"].(int); lvl != 3 {
			t.Fatalf("base level not applied: got %d, want 3", lvl)
		}
	}

	// A stored value must always beat the diagnostic floor — the floor is a fallback for heroes
	// with no progress, never an override of real progress.
	s.SetHeroMastery("p-base", "Storm", HeroMasteryProgress{Level: 9, XP: 42})
	entries, _ = s.heroMasteryEntries("p-base")
	for _, e := range entries {
		m := e.(map[string]any)
		if m["HeroId"] == "Hero:Storm" && m["Level"].(int) != 9 {
			t.Errorf("stored level 9 was overridden by the floor: got %v", m["Level"])
		}
	}
}

// TestHeroMasteryMovesVersion is the load-bearing one.
//
// The native ingester's adoption gate is a STRICT `>` on dword[PM+0xA0] (+585A594 cmp / +585A597
// jle). If arming the knob does not move Version, a client that already adopted the current
// Version silently ignores the new key — and the experiment reads as "serving HeroMastery does
// nothing", which is the single most expensive way this could fail.
func TestHeroMasteryMovesVersion(t *testing.T) {
	const id = "p-version"

	off := getProgression(t, id)["Version"].(float64)
	if again := getProgression(t, id)["Version"].(float64); again != off {
		t.Fatalf("Version moved with no content change: %v -> %v (would re-broadcast forever)", off, again)
	}

	t.Setenv("AGS_SERVE_HEROMASTERY", "hero")
	armed := getProgression(t, id)["Version"].(float64)
	if armed <= off {
		t.Fatalf("arming the knob did not advance Version (%v -> %v); the strict `>` gate would drop the document", off, armed)
	}

	// Changing the mode is also a content change and must advance again.
	t.Setenv("AGS_SERVE_HEROMASTERY", "both")
	both := getProgression(t, id)["Version"].(float64)
	if both <= armed {
		t.Fatalf("switching mode did not advance Version (%v -> %v)", armed, both)
	}
}

// TestHeroMasteryStoredProgressRoundTrips checks the admin/write path reaches the wire.
func TestHeroMasteryStoredProgressRoundTrips(t *testing.T) {
	t.Setenv("AGS_SERVE_HEROMASTERY", "hero")
	s, _ := newTestService()

	s.SetHeroMastery("p-rt", "reshealer", HeroMasteryProgress{Level: 4, XP: 12345, Cleared: true})
	// Negative values are clamped, mirroring SetAccountPass.
	s.SetHeroMastery("p-rt", "RONIN", HeroMasteryProgress{Level: -3, XP: -1})

	entries, digest := s.heroMasteryEntries("p-rt")
	found := map[string]map[string]any{}
	for _, e := range entries {
		m := e.(map[string]any)
		found[m["HeroId"].(string)] = m
	}

	rh := found["Hero:reshealer"]
	if rh == nil {
		t.Fatal("Hero:reshealer absent")
	}
	if rh["Level"] != 4 || rh["XP"] != 12345 || rh["Cleared"] != true {
		t.Errorf("reshealer round-trip wrong: %#v", rh)
	}
	ro := found["Hero:RONIN"]
	if ro == nil {
		t.Fatal("Hero:RONIN absent")
	}
	if ro["Level"] != 0 || ro["XP"] != 0 {
		t.Errorf("negatives not clamped: %#v", ro)
	}
	// An untouched hero is served as the honest fresh-account zero, not omitted — the client
	// needs a row per hero to render a track.
	if al := found["Hero:Alchemist"]; al == nil || al["Level"] != 0 {
		t.Errorf("untouched hero should be served at level 0, got %#v", al)
	}
	if digest == "" {
		t.Error("empty digest while armed; Version could not track content changes")
	}
	if fmt.Sprint(digest[:3]) != "hm1" {
		t.Errorf("digest %q lost its version prefix", digest)
	}
}
