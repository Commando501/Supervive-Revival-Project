package menu

import (
	"os"
	"path/filepath"
	"testing"
)

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
	cfg = defaultConfig()
	Load("")
	if len(cfg.Heroes) != 25 {
		t.Fatalf("after Load(\"\"): heroes = %d, want 25", len(cfg.Heroes))
	}
}

// TestLoadOverlay verifies a partial file overrides only its non-empty fields and
// leaves the rest as defaults (empty skins list => embedded 391 retained).
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
	defer func() { cfg = defaultConfig() }() // restore for other tests

	Load(path)

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

// TestLoadInvalidFileKeepsDefaults verifies a parse error is non-fatal.
func TestLoadInvalidFileKeepsDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad.json")
	if err := os.WriteFile(path, []byte("{ not json"), 0o644); err != nil {
		t.Fatal(err)
	}
	cfg = defaultConfig()
	defer func() { cfg = defaultConfig() }()
	Load(path)
	if len(cfg.Heroes) != 25 {
		t.Errorf("after invalid Load: heroes = %d, want default 25", len(cfg.Heroes))
	}
}
