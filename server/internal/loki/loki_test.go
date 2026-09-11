package loki

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// These tests pin the client-config feature-toggle payload.
//
// WHY THEY EXIST: from S73 until S121 (2026-08-15) this project served
// FeatureToggles[key].Config["default"], but the client's declarative UI gate
// (WBP_UI_ClientConfigVisbilityToggleWidget_C) reads Config[ConfigKey] with a CDO default
// ConfigKey of "enabled". Every Map_Find therefore MISSED and every gate silently fell back to
// its own IsEnabledByDefault. The payload was inert for ~48 sessions and nothing failed loudly —
// there was no test here at all, and internal/loki had no test file.
//
// This is the test that would have caught it. See docs/s121-toggle-fix-confirmed.md.

func fetchConfig(t *testing.T) map[string]any {
	t.Helper()
	s := &Service{}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "http://localhost:8080/configuration/public", nil)
	s.handleClientConfig(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("handleClientConfig status = %d, want 200", rec.Code)
	}
	var doc map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &doc); err != nil {
		t.Fatalf("response is not JSON: %v", err)
	}
	return doc
}

func toggles(t *testing.T, doc map[string]any) map[string]any {
	t.Helper()
	ft, ok := doc["featureToggles"].(map[string]any)
	if !ok {
		t.Fatal("featureToggles missing or not an object")
	}
	return ft
}

// TestEveryToggleCarriesTheEnabledSubKey is THE regression guard. "enabled" is the sub-key the
// client actually reads; "default" alone is what made the whole payload inert.
func TestEveryToggleCarriesTheEnabledSubKey(t *testing.T) {
	ft := toggles(t, fetchConfig(t))
	if len(ft) == 0 {
		t.Fatal("no feature toggles served at all")
	}
	for key, v := range ft {
		entry, ok := v.(map[string]any)
		if !ok {
			t.Errorf("%q: entry is not an object", key)
			continue
		}
		cfg, ok := entry["config"].(map[string]any)
		if !ok {
			t.Errorf("%q: missing \"config\" object", key)
			continue
		}
		if _, ok := cfg["enabled"]; !ok {
			t.Errorf("%q: config has no \"enabled\" sub-key -- this gate can never bind. "+
				"ConfigKey is \"enabled\", not \"default\" (S121).", key)
		}
	}
}

// TestEnabledAndDefaultAgree guards a subtler failure: shipping both sub-keys but letting them
// drift apart, so the observable behaviour depends on which one a given consumer reads.
func TestEnabledAndDefaultAgree(t *testing.T) {
	ft := toggles(t, fetchConfig(t))
	for key, v := range ft {
		cfg, ok := v.(map[string]any)["config"].(map[string]any)
		if !ok {
			continue
		}
		en, hasEn := cfg["enabled"]
		df, hasDf := cfg["default"]
		if hasEn && hasDf && en != df {
			t.Errorf("%q: enabled=%v but default=%v -- the two sub-keys must agree", key, en, df)
		}
	}
}

// TestNeverServeKeysThatAreOnByDefault pins the safety rule.
//
// A key whose IsEnabledByDefault is true is ALREADY ON without us, so serving it can only ever
// turn something OFF. `mastery` is in this list because S121 measured it live as
// IsEnabledByDefault=true on 3 of its instances -- it was mis-classified as a dark key, and
// serving it false would REMOVE the S120 hero-mastery surfaces.
func TestNeverServeKeysThatAreOnByDefault(t *testing.T) {
	onByDefault := []string{
		"EmoteSFX", "KillStreakAsRomanNumeral", "voicechat", "ChatLobby", "CustomGameList",
		"RankedDisplay", "mailbox", "EventHub", "party.fill", "XPBoosts", "PlayerArmoryV2",
		"DebugNav", "GameVersion", "supporterpacks", "redeemcode", "DiscordButton", "OBSButton",
		"mastery",
	}
	ft := toggles(t, fetchConfig(t))
	for _, key := range onByDefault {
		if _, served := ft[key]; served {
			t.Errorf("%q is IsEnabledByDefault=true and must never be served -- "+
				"sending it can only turn a working surface OFF", key)
		}
	}
}

// TestTrailingSpaceArmoryKeyIsPreserved guards a GAME DATA BUG, not ours: four shipped sites
// declare "ArmoryItemProgression " WITH a trailing space. A clean key can never satisfy them, so
// both spellings must ship. This test exists so nobody "fixes the typo".
func TestTrailingSpaceArmoryKeyIsPreserved(t *testing.T) {
	ft := toggles(t, fetchConfig(t))
	if _, ok := ft["ArmoryItemProgression "]; !ok {
		t.Error(`the trailing-space key "ArmoryItemProgression " is missing. ` +
			`It is a bug in the SHIPPED ASSET and must be served verbatim -- do not "fix" it.`)
	}
	if _, ok := ft["ArmoryItemProgression"]; !ok {
		t.Error(`the clean key "ArmoryItemProgression" is missing`)
	}
}

// TestMotdCarriesAMessageBody pins that `motd` is special: the toggle alone does nothing because
// "Try Show MOTD" bails at Map_Find(Config,"key") and "Get Message of the Day" reads
// key/title/text. The sub-keys ARE the message; there is no MOTD endpoint.
func TestMotdCarriesAMessageBody(t *testing.T) {
	ft := toggles(t, fetchConfig(t))
	entry, ok := ft["motd"]
	if !ok {
		t.Skip("motd not served (AGS_MOTD=0?)")
	}
	cfg, ok := entry.(map[string]any)["config"].(map[string]any)
	if !ok {
		t.Fatal("motd has no config object")
	}
	for _, sub := range []string{"key", "title", "text"} {
		if v, ok := cfg[sub]; !ok || v == "" {
			t.Errorf("motd config is missing a non-empty %q -- "+
				"the toggle alone cannot show a message", sub)
		}
	}
}

// TestETagIsBumped is a weak but cheap guard: the handler's own comment warns that an unchanged
// eTag with changed content is a plausible silent no-op. This catches the specific case of
// leaving the eTag at a value a previous session already flew.
func TestETagIsBumped(t *testing.T) {
	doc := fetchConfig(t)
	etag, _ := doc["eTag"].(string)
	if etag == "" {
		t.Fatal("no eTag served")
	}
	for _, stale := range []string{
		"supervive-revival-2",
		"supervive-revival-3-fk17banner",
		"supervive-revival-4-uitoggles",
	} {
		if etag == stale {
			t.Errorf("eTag %q was already flown by an earlier session; bump it", etag)
		}
	}
	if !strings.HasPrefix(etag, "supervive-revival-") {
		t.Errorf("eTag %q does not follow the supervive-revival-<n>-<tag> convention", etag)
	}
}
