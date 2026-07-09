package menu

import (
	"os"
	"path/filepath"
	"testing"
)

// resetConfig restores the built-in defaults and clears the persistence path so
// tests never leak state into each other (Load/Apply mutate package globals).
func resetConfig() {
	publish(defaultConfig())
	savePath = ""
}

// TestDefaultConfigCounts pins the built-in defaults to the known catalog sizes.
// If these drift, the store/roster behavior changed — update deliberately, not by
// accident. (25 heroes, 25 StoreOffer bundles, 19 currency, 5 featured, 391
// HeroCosmeticsBundle skins, 536 SlotCosmetics accessories.)
func TestDefaultConfigCounts(t *testing.T) {
	d := defaultConfig()
	cases := []struct {
		name string
		got  int
		want int
	}{
		{"heroes", len(d.Heroes), 25},
		{"bundles", len(d.Store.Bundles), 25},
		{"currency", len(d.Store.Currency), 19},
		{"featured", len(d.Store.Featured), 5},
		{"skins", len(d.Store.Skins), 391},
		{"accessories", len(d.Store.Accessories), 536},
	}
	for _, c := range cases {
		if c.got != c.want {
			t.Errorf("default %s = %d, want %d", c.name, c.got, c.want)
		}
	}
	if d.Region != "us-east" {
		t.Errorf("default region = %q, want us-east", d.Region)
	}
	if d.Wallet["vp"] != 2004 {
		t.Errorf("default wallet vp = %d, want 2004", d.Wallet["vp"])
	}
}

// TestLoadEmptyPathKeepsDefaults verifies that no -config leaves the defaults in
// place (byte-identical to the pre-config server).
func TestLoadEmptyPathKeepsDefaults(t *testing.T) {
	resetConfig()
	Load("")
	if len(current().Heroes) != 25 {
		t.Fatalf("after Load(\"\"): heroes = %d, want 25", len(current().Heroes))
	}
}

// TestLoadOverlay verifies a partial file overrides only its PRESENT fields and
// leaves absent ones as defaults (no skins key => embedded 391 retained).
func TestLoadOverlay(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "store.json")
	const js = `{
	  "region": "eu-west",
	  "store": { "featured": ["OnlyOnePack"] },
	  "prices": { "OnlyOnePack": { "price": 999, "discountedPrice": 0, "currency": "vp" } }
	}`
	if err := os.WriteFile(path, []byte(js), 0o644); err != nil {
		t.Fatal(err)
	}
	defer resetConfig()

	Load(path)
	cfg := current()

	if cfg.Region != "eu-west" {
		t.Errorf("region = %q, want eu-west", cfg.Region)
	}
	if len(cfg.Store.Featured) != 1 || cfg.Store.Featured[0] != "OnlyOnePack" {
		t.Errorf("featured = %v, want [OnlyOnePack]", cfg.Store.Featured)
	}
	// Untouched fields fall back to defaults.
	if len(cfg.Store.Skins) != 391 {
		t.Errorf("skins = %d, want default 391", len(cfg.Store.Skins))
	}
	if len(cfg.Heroes) != 25 {
		t.Errorf("heroes = %d, want default 25", len(cfg.Heroes))
	}
	if p, ok := cfg.Prices["OnlyOnePack"]; !ok || p.Price != 999 {
		t.Errorf("prices[OnlyOnePack] = %+v, want price 999", p)
	}
}

// TestLoadPresentEmptyIsAuthoritative pins the 2026-07-08 semantics change: a
// PRESENT-but-empty list is honored (this is how the admin panel expresses "zero
// heroes unlocked"), while absent fields still default.
func TestLoadPresentEmptyIsAuthoritative(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "store.json")
	const js = `{ "heroes": [], "store": { "bundles": [] } }`
	if err := os.WriteFile(path, []byte(js), 0o644); err != nil {
		t.Fatal(err)
	}
	defer resetConfig()

	Load(path)
	cfg := current()

	if len(cfg.Heroes) != 0 {
		t.Errorf("heroes = %d, want 0 (present-empty is authoritative)", len(cfg.Heroes))
	}
	if len(cfg.Store.Bundles) != 0 {
		t.Errorf("bundles = %d, want 0 (present-empty is authoritative)", len(cfg.Store.Bundles))
	}
	// Absent fields still default.
	if len(cfg.Store.Skins) != 391 {
		t.Errorf("skins = %d, want default 391", len(cfg.Store.Skins))
	}
}

// TestLoadInvalidFileKeepsDefaults verifies a parse error is non-fatal.
func TestLoadInvalidFileKeepsDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad.json")
	if err := os.WriteFile(path, []byte("{ not json"), 0o644); err != nil {
		t.Fatal(err)
	}
	resetConfig()
	defer resetConfig()
	Load(path)
	if len(current().Heroes) != 25 {
		t.Errorf("after invalid Load: heroes = %d, want default 25", len(current().Heroes))
	}
}

// TestApplyPublishesAndPersists verifies the admin write path: Apply swaps the
// live snapshot, persists ALL fields to the config path, and a reload of that
// file reproduces the exact state (including empty lists).
func TestApplyPublishesAndPersists(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "menu-config.json")
	resetConfig()
	defer resetConfig()
	Load(path) // file doesn't exist yet — records the save path, keeps defaults

	edited := Snapshot()
	edited.Region = "test-region"
	edited.Heroes = []string{"alchemist", "wukong"}
	edited.Store.Bundles = []string{} // empty must survive the round-trip
	edited.Wallet = map[string]int{"vp": 123456}
	if err := Apply(edited); err != nil {
		t.Fatalf("Apply: %v", err)
	}

	if got := current(); got.Region != "test-region" || len(got.Heroes) != 2 {
		t.Errorf("published snapshot not applied: region=%q heroes=%d", got.Region, len(got.Heroes))
	}

	// Simulate a restart: reset then reload the persisted file.
	publish(defaultConfig())
	Load(path)
	cfg := current()
	if cfg.Region != "test-region" {
		t.Errorf("reloaded region = %q, want test-region", cfg.Region)
	}
	if len(cfg.Heroes) != 2 {
		t.Errorf("reloaded heroes = %d, want 2", len(cfg.Heroes))
	}
	if len(cfg.Store.Bundles) != 0 {
		t.Errorf("reloaded bundles = %d, want 0 (persisted empty list)", len(cfg.Store.Bundles))
	}
	if cfg.Wallet["vp"] != 123456 {
		t.Errorf("reloaded wallet vp = %d, want 123456", cfg.Wallet["vp"])
	}
}

// TestSnapshotIsDeepCopy verifies mutating a Snapshot cannot corrupt the live
// published config (the admin API hands Snapshots to JSON encoding / callers).
func TestSnapshotIsDeepCopy(t *testing.T) {
	resetConfig()
	defer resetConfig()
	snap := Snapshot()
	snap.Heroes[0] = "MUTATED"
	snap.Wallet["vp"] = -1
	if current().Heroes[0] == "MUTATED" {
		t.Error("Snapshot aliases the live Heroes slice")
	}
	if current().Wallet["vp"] == -1 {
		t.Error("Snapshot aliases the live Wallet map")
	}
}
