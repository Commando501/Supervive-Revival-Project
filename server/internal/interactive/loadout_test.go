package interactive

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// newTestService builds a Service with a memory-only store and its mux, so tests
// exercise the real route patterns (verbs, {id}, {rest...}) end-to-end.
func newTestService() (*Service, *http.ServeMux) {
	s := &Service{store: &store{players: map[string]*playerState{}}}
	mux := http.NewServeMux()
	s.Register(mux)
	return s, mux
}

func doJSON(t *testing.T, mux *http.ServeMux, method, path, body string) map[string]any {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s %s -> %d, want 200", method, path, rec.Code)
	}
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s %s: response not JSON: %v\n%s", method, path, err, rec.Body.String())
	}
	return m
}

// TestSlotCosmeticRoundTrip covers the one CAPTURED write on the surface: the
// glider equip from the 2026-07-06 session. The POSTed entry must come back on
// the personalization-root GET as slotCosmeticsEntries, with the doc version
// advanced (the reconciler gate), and an empty-asset re-POST must unequip it.
func TestSlotCosmeticRoundTrip(t *testing.T) {
	_, mux := newTestService()

	doJSON(t, mux, "POST", "/personalization/players/p1/slotcosmetics",
		`{"slot":"Glider","asset":"SlotCosmetics:GLIDER_AngelicForce"}`)

	got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if got["version"].(float64) != 1 {
		t.Fatalf("version = %v, want 1 after first write", got["version"])
	}
	entries := got["slotCosmeticsEntries"].([]any)
	if len(entries) != 1 {
		t.Fatalf("slotCosmeticsEntries = %v, want 1 entry", entries)
	}
	e := entries[0].(map[string]any)
	if e["slot"] != "Glider" || e["asset"] != "SlotCosmetics:GLIDER_AngelicForce" {
		t.Fatalf("entry = %v", e)
	}

	// Second slot: both present, version advances.
	doJSON(t, mux, "POST", "/personalization/players/p1/slotcosmetics",
		`{"slot":"Wisp","asset":"SlotCosmetics:WISP_Chickling"}`)
	got = doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if got["version"].(float64) != 2 || len(got["slotCosmeticsEntries"].([]any)) != 2 {
		t.Fatalf("after 2nd equip: version=%v entries=%v", got["version"], got["slotCosmeticsEntries"])
	}

	// Unequip the glider (empty asset) — entry removed, never a wipe of others.
	doJSON(t, mux, "POST", "/personalization/players/p1/slotcosmetics",
		`{"slot":"Glider","asset":""}`)
	got = doJSON(t, mux, "GET", "/personalization/players/p1", "")
	entries = got["slotCosmeticsEntries"].([]any)
	if len(entries) != 1 || entries[0].(map[string]any)["slot"] != "Wisp" {
		t.Fatalf("after unequip: entries = %v, want only Wisp", entries)
	}

	// A slotless body is a no-op, not a crash/wipe.
	doJSON(t, mux, "POST", "/personalization/players/p1/slotcosmetics", `{}`)
	got = doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if len(got["slotCosmeticsEntries"].([]any)) != 1 {
		t.Fatalf("slotless POST changed entries: %v", got["slotCosmeticsEntries"])
	}
}

// TestEmotesTitlesVerbatim: the arrays are stored raw and echoed as
// emoteIds/titleIds without re-modeling the element type.
func TestEmotesTitlesVerbatim(t *testing.T) {
	_, mux := newTestService()

	doJSON(t, mux, "POST", "/personalization/players/p1/emotes",
		`{"emotes":["Emote:Wave","Emote:Laugh"]}`)
	doJSON(t, mux, "PUT", "/personalization/players/p1/titles",
		`{"titles":["PlayerTitle:Legend"]}`)

	got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if e := got["emoteIds"].([]any); len(e) != 2 || e[0] != "Emote:Wave" {
		t.Fatalf("emoteIds = %v", got["emoteIds"])
	}
	if ti := got["titleIds"].([]any); len(ti) != 1 || ti[0] != "PlayerTitle:Legend" {
		t.Fatalf("titleIds = %v", got["titleIds"])
	}
	if got["version"].(float64) != 2 {
		t.Fatalf("version = %v, want 2", got["version"])
	}
}

// TestCosmeticsBundleTolerantParse: no request struct exists in the usmap, so
// the handler must pair Hero:*/HeroCosmeticsBundle:* ids found in the body, the
// path remainder, or the query — and no-op when it can't pair.
func TestCosmeticsBundleTolerantParse(t *testing.T) {
	cases := []struct {
		name, method, path, body string
	}{
		{"body ids", "POST", "/personalization/players/p1/cosmeticsbundle",
			`{"heroAssetId":"Hero:bishop","cosmeticsBundleAssetId":"HeroCosmeticsBundle:SKIN_Bishop_Cyber"}`},
		{"hero in path", "PUT", "/personalization/players/p1/cosmeticsbundle/Hero:bishop",
			`{"bundle":"HeroCosmeticsBundle:SKIN_Bishop_Cyber"}`},
		{"hero in query", "POST", "/personalization/players/p1/cosmeticsbundle?hero=Hero:bishop",
			`{"bundle":"HeroCosmeticsBundle:SKIN_Bishop_Cyber"}`},
		{"object-form ids", "POST", "/personalization/players/p1/cosmeticsbundle",
			`{"hero":{"type":"Hero","name":"bishop"},"bundle":{"type":"HeroCosmeticsBundle","name":"SKIN_Bishop_Cyber"}}`},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			_, mux := newTestService()
			doJSON(t, mux, c.method, c.path, c.body)
			got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
			prefs := got["heroCosmeticsBundlePreferences"].(map[string]any)
			if prefs["Hero:bishop"] != "HeroCosmeticsBundle:SKIN_Bishop_Cyber" {
				t.Fatalf("prefs = %v", prefs)
			}
		})
	}

	// Unpairable (no hero id anywhere) => no-op, still a clean 200 echo.
	_, mux := newTestService()
	doJSON(t, mux, "POST", "/personalization/players/p1/cosmeticsbundle",
		`{"bundle":"HeroCosmeticsBundle:SKIN_Bishop_Cyber"}`)
	got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if prefs := got["heroCosmeticsBundlePreferences"].(map[string]any); len(prefs) != 0 {
		t.Fatalf("unpairable request stored prefs: %v", prefs)
	}
}

// TestLuxeChromaRoundTrip: SetLuxeSkinChromaPreferenceRequest round-trips into
// luxeSkinChromaPreferences, and an empty chroma unequips.
func TestLuxeChromaRoundTrip(t *testing.T) {
	_, mux := newTestService()

	doJSON(t, mux, "POST", "/personalization/players/p1/luxechromas",
		`{"luxeAssetId":"HeroCosmeticsBundle:LUXE_Jin","chromaAssetId":"SlotCosmetics:CHROMA_Jin_Red"}`)
	got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
	prefs := got["luxeSkinChromaPreferences"].(map[string]any)
	if prefs["HeroCosmeticsBundle:LUXE_Jin"] != "SlotCosmetics:CHROMA_Jin_Red" {
		t.Fatalf("luxe prefs = %v", prefs)
	}

	doJSON(t, mux, "POST", "/personalization/players/p1/luxechromas",
		`{"luxeAssetId":"HeroCosmeticsBundle:LUXE_Jin","chromaAssetId":""}`)
	got = doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if prefs := got["luxeSkinChromaPreferences"].(map[string]any); len(prefs) != 0 {
		t.Fatalf("after unequip: %v", prefs)
	}
}

// TestLobbyPlatformInLoadout: the backdrop write flows into the loadout doc
// (lobbyPlatformPreference) and bumps the version, and the original probe keys
// are still present on the root GET.
func TestLobbyPlatformInLoadout(t *testing.T) {
	_, mux := newTestService()

	doJSON(t, mux, "PUT", "/personalization/players/p1/lobbyplatforms",
		`{"lobbyPlatformAssetId":"LobbyPlatform:Base"}`)
	got := doJSON(t, mux, "GET", "/personalization/players/p1", "")
	if got["lobbyPlatformPreference"] != "LobbyPlatform:Base" {
		t.Fatalf("lobbyPlatformPreference = %v", got["lobbyPlatformPreference"])
	}
	if got["lobbyPlatformAssetId"] != "LobbyPlatform:Base" || got["equippedLobbyPlatform"] != "LobbyPlatform:Base" {
		t.Fatalf("legacy probe keys missing: %v", got)
	}
	if got["version"].(float64) != 1 {
		t.Fatalf("version = %v, want 1", got["version"])
	}
}
