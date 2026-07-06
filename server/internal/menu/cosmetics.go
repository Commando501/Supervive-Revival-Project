package menu

import (
	_ "embed"
	"strings"
)

// Individual-cosmetic offers for the STORE's SKINS and ACCESSORIES tabs.
//
// Those tabs don't read our StoreOffer packs — they filter the storefront's ItemOffers by
// the offer's RESOLVED PrimaryAssetType (bpdump of WBP_UI_Storefront_SkinsBundles):
//   - SKINS       (GetSortedCosmeticsBundlesListForStore) keeps type == "HeroCosmeticsBundle"
//   - ACCESSORIES keeps type == "SlotCosmetics" (Gliders/Emotes/Wisps/Sprays/Avatars)
// so they need ItemOffers whose SKU resolves to those types. The SKU must be the full
// "<Type>:<PrimaryAssetName>" PrimaryAssetId string (same rule the StoreOffer tabs needed).
//
// The names below are the REAL PrimaryAssetName keys, read live from the client's own
// LokiAssetLoader maps (HeroCosmeticsBundleAssets=391, SlotCosmeticsAssets=536) via
// tools/re RPM — the packed asset short-names, not display names. Embedded as data files
// (927 names) rather than inlined.

//go:embed data/skins.txt
var skinsData string

//go:embed data/slots.txt
var slotsData string

func lines(s string) []string {
	raw := strings.Split(s, "\n")
	out := make([]string, 0, len(raw))
	for _, ln := range raw {
		if ln = strings.TrimSpace(ln); ln != "" {
			out = append(out, ln)
		}
	}
	return out
}

// cosmeticOffers builds []LokiStorefrontPlayerItemOffer for a cosmetic type. All fields are
// type-safe per schema.txt; SKU is the full "<assetType>:<name>" PrimaryAssetId string.
func cosmeticOffers(names []string, assetType, category string) []map[string]any {
	offers := make([]map[string]any, 0, len(names))
	for _, n := range names {
		offers = append(offers, map[string]any{
			"SKU":         assetType + ":" + n,
			"Category":    category,
			"NameSpace":   "",
			"Purchasable": true,
			"PID":         n,
			"Costs":       storeCosts(),
			"SteamItemID": 0,
		})
	}
	return offers
}

// ownedAssetEntries builds inventory AssetEntries marking every asset of the given type as
// IsOwned=true. Marking cosmetics owned drives the client CatalogManager to set
// CatalogEntry.IsOwned=1 → CanUse=1 → the browse-tab tiles render (heroes work this way in
// handleInventory today; cosmetics need the same treatment).
func ownedAssetEntries(names []string, assetType string) []map[string]any {
	entries := make([]map[string]any, 0, len(names))
	for _, n := range names {
		entries = append(entries, map[string]any{
			"AssetId":   assetType + ":" + n,
			"IsOwned":   true,
			"IsDefault": false,
		})
	}
	return entries
}
