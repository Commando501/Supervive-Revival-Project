package menu

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
)

// Config is the operator-editable server configuration for the menu/storefront
// surface. A self-hosted dedicated server reads this at startup (the -config flag)
// to control which heroes/cosmetics are advertised and owned, and (once the client
// offering-cost path is wired — see OfferCost) their prices, WITHOUT recompiling.
//
// 2026-07-08: the config is now also RUNTIME-mutable via the admin panel
// (internal/admin): Apply publishes a new snapshot and persists it to the config
// path, so operator edits take effect on the client's next fetch of the affected
// endpoint (inventory/store/wallet refetch on menu re-entry) and survive restarts.
//
// FILE SEMANTICS (changed 2026-07-08, was "empty means default"): a field that is
// ABSENT from the JSON file falls back to the built-in default; a field that is
// PRESENT is authoritative even when empty. This is what lets the admin panel
// express "zero heroes unlocked" / an empty store tab — previously impossible
// because empty and absent were conflated (see the old note on this struct). The
// distinction is implemented by parsing into fileConfig (pointer fields) in Load;
// old partial configs that simply omit fields behave exactly as before.
type Config struct {
	Region string               `json:"region"`
	Wallet map[string]int       `json:"wallet"`
	Heroes []string             `json:"heroes"`
	Store  StoreConfig          `json:"store"`
	Prices map[string]OfferCost `json:"prices"`
}

// StoreConfig lists the SKUs advertised on each storefront tab. Bundles are
// StoreOffer packs (routed to BUNDLES + SUPPORTER PACKS by PrimaryAssetType);
// Currency are the real-money top-up packs; Featured drives the carousel; Skins
// are HeroCosmeticsBundle; Accessories are SlotCosmetics. Skins/Accessories
// default to the full embedded lists (data/skins.txt = 391, data/slots.txt = 536)
// when absent from the file, so an operator only overrides them to curate a subset.
//
// NOTE: these lists drive BOTH the storefront advertising (handlePlayerStore)
// AND ownership (handleInventory marks every listed asset IsOwned=true). Removing
// a skin here therefore locks it in the COSMETICS browser too, not just the store.
type StoreConfig struct {
	Bundles     []string `json:"bundles"`
	Currency    []string `json:"currency"`
	Featured    []string `json:"featured"`
	Skins       []string `json:"skins"`
	Accessories []string `json:"accessories"`
}

// OfferCost is a per-SKU price, keyed in Config.Prices by the offer's
// PrimaryAssetName (the same key used in the store SKU lists).
//
// NOT YET CONSUMED (2026-07-06): the client reads a tile's displayed price from
// the packed CatalogEntry.GetOffers() (native), NOT from the backend offer's Costs
// field — sending Costs was proven inert (see storeCosts() and the store-status
// memory). Prices is defined here so the operator surface exists and is stable; the
// "server-driven prices" work will feed these values into the client cost path
// (either a discovered backend endpoint or an injected cost bridge). Until then,
// setting a price has no visible effect in-client.
type OfferCost struct {
	Price           int    `json:"price"`
	DiscountedPrice int    `json:"discountedPrice"`
	Currency        string `json:"currency"`
}

// active is the published configuration snapshot. Snapshots are IMMUTABLE once
// published: handlers grab the pointer via current() and read it without further
// locking; Apply/Load build a fresh Config and swap the pointer under cfgMu.
var (
	cfgMu    sync.RWMutex
	active   = defaultConfig()
	savePath string // where Apply persists; set by Load (even if the file didn't exist yet)
)

// current returns the active immutable config snapshot. Handlers call this once
// per request (`cfg := current()`) and read fields off the snapshot.
func current() *Config {
	cfgMu.RLock()
	defer cfgMu.RUnlock()
	return active
}

// publish swaps in a new snapshot.
func publish(c *Config) {
	cfgMu.Lock()
	active = c
	cfgMu.Unlock()
}

// defaultConfig returns the built-in values — the pre-config hardcoded lists. This
// is the single source of truth for defaults: the package vars heroCodenames,
// virtualStoreSKUs, realMoneyStoreSKUs, featuredStoreSKUs and the embedded
// skins/slots data files back it, so changing a default in one place updates both
// the fallback and the code paths.
func defaultConfig() *Config {
	return &Config{
		Region: "us-east",
		Wallet: map[string]int{"vp": 2004},
		Heroes: heroCodenames,
		Store: StoreConfig{
			Bundles:     virtualStoreSKUs,
			Currency:    realMoneyStoreSKUs,
			Featured:    featuredStoreSKUs,
			Skins:       lines(skinsData),
			Accessories: lines(slotsData),
		},
		Prices: map[string]OfferCost{},
	}
}

// fileConfig mirrors Config with pointer/nilable fields so Load can distinguish
// "absent" (nil → keep default) from "present but empty" (non-nil → authoritative).
// Maps get presence semantics for free (missing key stays nil; `{}` is non-nil).
type fileConfig struct {
	Region *string        `json:"region"`
	Wallet map[string]int `json:"wallet"`
	Heroes *[]string      `json:"heroes"`
	Store  struct {
		Bundles     *[]string `json:"bundles"`
		Currency    *[]string `json:"currency"`
		Featured    *[]string `json:"featured"`
		Skins       *[]string `json:"skins"`
		Accessories *[]string `json:"accessories"`
	} `json:"store"`
	Prices map[string]OfferCost `json:"prices"`
}

// Load reads a JSON config file and overlays its PRESENT fields onto the defaults
// (absent fields keep the built-in default; a present-but-empty list is honored —
// see the Config doc). An empty path, a missing file, or a parse error leaves the
// defaults in place (logged) so the server always starts. Call once at startup
// before serving. The path is remembered as the persistence target for Apply,
// including when the file does not exist yet (the admin panel's first save
// creates it).
func Load(path string) {
	if path == "" {
		return
	}
	savePath = path

	b, err := os.ReadFile(path)
	if err != nil {
		log.Printf("menu: config %q not read (%v) — using built-in defaults", path, err)
		return
	}
	var file fileConfig
	if err := json.Unmarshal(b, &file); err != nil {
		log.Printf("menu: config %q parse error (%v) — using built-in defaults", path, err)
		return
	}

	merged := defaultConfig()
	if file.Region != nil && *file.Region != "" {
		merged.Region = *file.Region
	}
	if file.Wallet != nil {
		merged.Wallet = file.Wallet
	}
	if file.Heroes != nil {
		merged.Heroes = *file.Heroes
	}
	if file.Store.Bundles != nil {
		merged.Store.Bundles = *file.Store.Bundles
	}
	if file.Store.Currency != nil {
		merged.Store.Currency = *file.Store.Currency
	}
	if file.Store.Featured != nil {
		merged.Store.Featured = *file.Store.Featured
	}
	if file.Store.Skins != nil {
		merged.Store.Skins = *file.Store.Skins
	}
	if file.Store.Accessories != nil {
		merged.Store.Accessories = *file.Store.Accessories
	}
	if file.Prices != nil {
		merged.Prices = file.Prices
	}
	publish(merged)

	log.Printf("menu: loaded config %q (heroes=%d bundles=%d currency=%d featured=%d skins=%d accessories=%d prices=%d)",
		path, len(merged.Heroes), len(merged.Store.Bundles), len(merged.Store.Currency),
		len(merged.Store.Featured), len(merged.Store.Skins), len(merged.Store.Accessories), len(merged.Prices))
}

// Snapshot returns a deep copy of the active config for the admin API (safe for
// the caller to mutate and feed back to Apply).
func Snapshot() Config { return copyConfig(current()) }

// Defaults returns a deep copy of the built-in defaults — the admin GUI renders
// its hero/SKU checklists against these full lists.
func Defaults() Config { return copyConfig(defaultConfig()) }

// ConfigPath returns where Apply persists the config ("" = persistence disabled).
func ConfigPath() string { return savePath }

// Apply validates, publishes, and persists a full config (admin panel PUT). The
// incoming value is deep-copied before publishing so the caller's maps/slices
// can't mutate the active snapshot. Persistence is best-effort-with-error: the
// new config is ALWAYS published in-memory; a save failure is reported so the
// operator knows edits won't survive a restart.
func Apply(c Config) error {
	cp := copyConfig(&c)
	// Nil maps/slices normalize to empty so handlers never nil-check.
	if cp.Wallet == nil {
		cp.Wallet = map[string]int{}
	}
	if cp.Prices == nil {
		cp.Prices = map[string]OfferCost{}
	}
	publish(&cp)
	log.Printf("menu: admin applied config (heroes=%d bundles=%d currency=%d featured=%d skins=%d accessories=%d prices=%d)",
		len(cp.Heroes), len(cp.Store.Bundles), len(cp.Store.Currency),
		len(cp.Store.Featured), len(cp.Store.Skins), len(cp.Store.Accessories), len(cp.Prices))

	if savePath == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(savePath), 0o755); err != nil {
		return fmt.Errorf("config dir: %w", err)
	}
	b, err := json.MarshalIndent(cp, "", "  ")
	if err != nil {
		return fmt.Errorf("config marshal: %w", err)
	}
	// All fields are materialized in the saved file (fileConfig presence semantics:
	// present == authoritative), so a reload reproduces this exact state.
	tmp := savePath + ".tmp"
	if err := os.WriteFile(tmp, b, 0o644); err != nil {
		return fmt.Errorf("config write: %w", err)
	}
	if err := os.Rename(tmp, savePath); err != nil {
		return fmt.Errorf("config rename: %w", err)
	}
	return nil
}

// copyConfig deep-copies a Config so published snapshots are never aliased.
// Lists copy via copyList (never nil): an empty list must marshal as [] — a nil
// slice marshals as null, which fileConfig reads back as ABSENT, silently
// reverting a persisted "empty on purpose" to the defaults (caught by
// TestApplyPublishesAndPersists).
func copyConfig(c *Config) Config {
	cp := Config{
		Region: c.Region,
		Wallet: make(map[string]int, len(c.Wallet)),
		Heroes: copyList(c.Heroes),
		Store: StoreConfig{
			Bundles:     copyList(c.Store.Bundles),
			Currency:    copyList(c.Store.Currency),
			Featured:    copyList(c.Store.Featured),
			Skins:       copyList(c.Store.Skins),
			Accessories: copyList(c.Store.Accessories),
		},
		Prices: make(map[string]OfferCost, len(c.Prices)),
	}
	for k, v := range c.Wallet {
		cp.Wallet[k] = v
	}
	for k, v := range c.Prices {
		cp.Prices[k] = v
	}
	return cp
}

// copyList copies a string list, returning a non-nil (possibly empty) slice.
func copyList(s []string) []string {
	out := make([]string, len(s))
	copy(out, s)
	return out
}
