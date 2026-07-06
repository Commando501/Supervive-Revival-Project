package menu

import (
	"encoding/json"
	"log"
	"os"
)

// Config is the operator-editable server configuration for the menu/storefront
// surface. A self-hosted dedicated server reads this at startup (the -config flag)
// to control which heroes/cosmetics are advertised and owned, and (once the client
// offering-cost path is wired — see OfferCost) their prices, WITHOUT recompiling.
//
// Every field is OPTIONAL. An absent or empty field falls back to the built-in
// defaults (defaultConfig), so a missing config file yields byte-identical
// responses to the pre-config server. NOTE: because empty means "use default",
// there is currently no way to advertise an empty list (e.g. zero heroes) via
// config; that distinction can be added later with pointer/null fields if needed.
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
// when left empty, so an operator only overrides them to curate a subset.
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

// cfg is the active configuration. Initialized to the built-in defaults so the
// server works with no config file; Load overlays an operator file onto it.
var cfg = defaultConfig()

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

// Load reads a JSON config file and overlays its non-empty fields onto the
// defaults. An empty path, a missing file, or a parse error leaves the defaults in
// place (logged) so the server always starts. Call once at startup before serving.
func Load(path string) {
	if path == "" {
		return
	}
	b, err := os.ReadFile(path)
	if err != nil {
		log.Printf("menu: config %q not read (%v) — using built-in defaults", path, err)
		return
	}
	var file Config
	if err := json.Unmarshal(b, &file); err != nil {
		log.Printf("menu: config %q parse error (%v) — using built-in defaults", path, err)
		return
	}

	merged := defaultConfig()
	if file.Region != "" {
		merged.Region = file.Region
	}
	if len(file.Wallet) > 0 {
		merged.Wallet = file.Wallet
	}
	if len(file.Heroes) > 0 {
		merged.Heroes = file.Heroes
	}
	if len(file.Store.Bundles) > 0 {
		merged.Store.Bundles = file.Store.Bundles
	}
	if len(file.Store.Currency) > 0 {
		merged.Store.Currency = file.Store.Currency
	}
	if len(file.Store.Featured) > 0 {
		merged.Store.Featured = file.Store.Featured
	}
	if len(file.Store.Skins) > 0 {
		merged.Store.Skins = file.Store.Skins
	}
	if len(file.Store.Accessories) > 0 {
		merged.Store.Accessories = file.Store.Accessories
	}
	if len(file.Prices) > 0 {
		merged.Prices = file.Prices
	}
	cfg = merged

	log.Printf("menu: loaded config %q (heroes=%d bundles=%d currency=%d featured=%d skins=%d accessories=%d prices=%d)",
		path, len(cfg.Heroes), len(cfg.Store.Bundles), len(cfg.Store.Currency),
		len(cfg.Store.Featured), len(cfg.Store.Skins), len(cfg.Store.Accessories), len(cfg.Prices))
}
