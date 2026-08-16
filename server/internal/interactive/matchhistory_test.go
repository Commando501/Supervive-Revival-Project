package interactive

import (
	"encoding/json"
	"strings"
	"testing"
)

// TestMatchHistoryOffIsByteIdentical pins the property the whole S123 design rests on: with
// AGS_MATCH_HISTORY unset, the served document is EXACTLY what it was before matchhistory.go
// existed — `"Matches": []` under the payload tag `mh1-empty`.
//
// WHY PIN IT. `Matches` feeds the news-banner gate (`IsMatchHistoryLoaded`, [MatchHistoryManager
// +0x68] >= -1), and the payload tag feeds the served Version. A regression in either is SILENT:
// a rejected document leaves the -2 sentinel and the banner simply stops appearing, with nothing
// in the log to say why. This project has four recorded instances of a payload changing without
// its version/eTag moving (FPlayerRank's gate, client-config, regions, matchmaking), so the
// version-tag half is pinned too, not just the array.
//
// ⚠ `nil` vs `[]any{}` is the trap here: a nil slice marshals to `null`, not `[]`, and `null`
// against a TArray is a wrong-typed MATCHED key — exactly the class of error that rejects the
// WHOLE document. The test asserts the literal bytes rather than the length for that reason.
func TestMatchHistoryOffIsByteIdentical(t *testing.T) {
	t.Setenv("AGS_MATCH_HISTORY", "")

	if got := matchHistoryPayloadTag(); got != "mh1-empty" {
		t.Errorf("payload tag with knob off = %q, want %q (a changed tag advances the served "+
			"Version for a document that did not change)", got, "mh1-empty")
	}

	m := matchHistoryMatches("player-1")
	if m == nil {
		t.Fatal("matchHistoryMatches returned nil; a nil slice marshals to `null`, not `[]`, and " +
			"`null` against TArray<FMatchHistoryEntry> rejects the whole document")
	}
	b, err := json.Marshal(map[string]any{"Matches": m})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if string(b) != `{"Matches":[]}` {
		t.Errorf("off payload = %s, want {\"Matches\":[]}", b)
	}
}

// TestMatchHistoryModesAreDistinctAndTagged checks that each mode (a) actually produces rows and
// (b) carries a DIFFERENT payload tag, so that switching modes on a live client advances the
// Version and the new document is not silently discarded as stale.
func TestMatchHistoryModesAreDistinctAndTagged(t *testing.T) {
	tags := map[string]string{}
	for _, mode := range []string{"", "minimal", "full"} {
		t.Setenv("AGS_MATCH_HISTORY", mode)
		tag := matchHistoryPayloadTag()
		if prev, dup := tags[tag]; dup {
			t.Errorf("mode %q and mode %q share payload tag %q; the second would be served under a "+
				"non-advancing Version and silently ignored", mode, prev, tag)
		}
		tags[tag] = mode

		got := len(matchHistoryMatches("player-1"))
		want := 0
		if mode != "" {
			want = 1
		}
		if got != want {
			t.Errorf("mode %q produced %d rows, want %d", mode, got, want)
		}
	}
}

// TestMatchHistoryMinimalOmitsEveryRiskyField is the single-variable ladder, enforced.
//
// `minimal` exists so that a blank Career->History panel is interpretable: if the row carries no
// FPrimaryAssetId, no enum, no nested struct and no array, then a rejected document cannot be
// blamed on an unresolvable asset id (the missions `InternalName` failure), a bad enum string (the
// S118 `ELokiActivityState` failure), or a container/type mismatch. If any of those fields leaks
// into `minimal`, the ladder collapses and the arm stops being able to localise a fault.
func TestMatchHistoryMinimalOmitsEveryRiskyField(t *testing.T) {
	t.Setenv("AGS_MATCH_HISTORY", "minimal")
	rows := matchHistoryMatches("player-1")
	if len(rows) != 1 {
		t.Fatalf("want 1 row, got %d", len(rows))
	}
	row, ok := rows[0].(map[string]any)
	if !ok {
		t.Fatalf("row is %T, want map[string]any", rows[0])
	}
	for _, risky := range []string{
		"HeroAssetID",         // FPrimaryAssetId — unresolvable id drops the element silently
		"StartingRank",        // ERank — a wrong enum string sinks the whole document
		"TeamInfo",            // nested struct, itself containing an array of structs
		"PersonalStats",       // nested struct, 38 fields
		"ArmoryRewardsEarned", // TArray<FArmoryReward>, each holding an FPrimaryAssetId
	} {
		if _, present := row[risky]; present {
			t.Errorf("minimal row contains risky field %q; minimal must be scalars, strings and "+
				"FDateTime only, or a null result cannot be localised", risky)
		}
	}
	// And it must still be a usable row rather than an empty object.
	for _, need := range []string{"ID", "MatchStart", "MatchEnd", "QueueID", "NumTeams"} {
		if _, present := row[need]; !present {
			t.Errorf("minimal row is missing %q", need)
		}
	}
	// FDateTime imports from ISO-8601; a missing Z (or a local-time offset) is a matched key with
	// an unparseable value.
	if s, _ := row["MatchStart"].(string); !strings.HasSuffix(s, "Z") {
		t.Errorf("MatchStart = %q, want an ISO-8601 UTC string ending in Z", s)
	}
}

// TestMatchHistoryFullServesMeasuredGoodValues guards the two values that were chosen because this
// project MEASURED the client accepting them, rather than because they looked plausible.
func TestMatchHistoryFullServesMeasuredGoodValues(t *testing.T) {
	t.Setenv("AGS_MATCH_HISTORY", "full")
	row := matchHistoryMatches("player-1")[0].(map[string]any)

	// S121 measured "Gold1" accepted on /mmr/leaderboard, and a live read of UEnum::Names confirms
	// it is ERank index 12. Any other value is unmeasured.
	if row["StartingRank"] != "Gold1" {
		t.Errorf("StartingRank = %v, want \"Gold1\" (the one ERank string measured accepted)",
			row["StartingRank"])
	}
	// S120 measured the `Hero:` prefix (not `HeroMastery:`) being the form the UI resolved.
	if s, _ := row["HeroAssetID"].(string); !strings.HasPrefix(s, "Hero:") {
		t.Errorf("HeroAssetID = %q, want the measured-good `Hero:<name>` form", s)
	}
}
