// Package menu implements the post-login "main menu" services the client polls
// once it reaches the menu (Milestone 2). These run on the AccelByte HTTP base
// (:8080) because client-config's ServiceHostnames maps every service name —
// storefront, personalization, party, playerstats, etc. — to localhost:8080,
// and the game calls {base}/{service}/{endpoint}.
//
// Validity model (deduced from Loki.log — two distinct LogLokiPlatformQuery
// error strings, confirmed in the binary):
//   - "Invalid response received"  -> a pre-deserialize validity predicate failed
//     (a required top-level field is absent). Our {} stub hits this.
//   - "Deserialization failure"    -> the JSON parsed but its container type does
//     not match the target UStruct. A bare [] hits this (array vs. object struct).
//
// So the list endpoints expect a top-level JSON **object wrapper** (the AccelByte
// "...Result" model) whose required field (`data`) must be present. Returning
// {"data": [], "paging": {}} satisfies the predicate (data present) and
// deserializes cleanly (object -> object struct), both fields empty-but-typed so
// there is no wrong-type-rejects-whole-doc risk. Empty data == no battlepass
// shown, but the retry loop stops. The {}->[] transition is what proved this:
// {} gave "Invalid response received"; [] flipped it to "Deserialization failure".
package menu

import (
	"encoding/json"
	"net/http"
)

type Service struct{}

func New() *Service { return &Service{} }

func (s *Service) Register(mux *http.ServeMux) {
	// Battlepass progression tracks. Response model:
	// FAccelByteModelsListProgressionTrackInfoResult { Data: TArray<...>, Paging }.
	// See the validity-model note above for why this is an object wrapper, not a
	// bare array.
	mux.HandleFunc("GET /storefront/battlepass/progressiontracks", handleProgressionTracks)

	// Storefront commerce (UStorefrontManager / StorefrontOrderModel.cpp). Custom
	// Theorycraft "FLokiStorefront*" models, not stock AccelByte. These currently
	// accept the {} catch-all silently (no validity predicate, one-shot — they just
	// render empty), so populating them can't tight-loop; worst case a wrong-typed
	// *matched* field rejects the doc back to empty.
	mux.HandleFunc("GET /storefront/wallet/{id}", handleWallet)
	mux.HandleFunc("GET /storefront/heroes", handleHeroes)
	mux.HandleFunc("GET /storefront/offers/{id}", handlePlayerStore)

	// Platform inventory (UPlatformInventoryManager). Model LokiPlatformInventory
	// { AssetEntries: TArray<...> }. The hero-token count the Hunters screen wants
	// ("LogBattlepassHeroUnlocker: Failed to get hero token amount") is a currency
	// exchange token coded "heroToken" (a literal string, not a packed SKU), held
	// as an AssetEntries entry.
	mux.HandleFunc("GET /inventory/players/{id}", handleInventory)
	mux.HandleFunc("GET /inventory/free", handleFreeInventory)

	// Real-money store (UStorefrontManager::GetRealMoneyStorefront) — drives the
	// STORE tab. Valid-empty PlayerStore-shaped wrapper so the FEATURED carousel
	// settles instead of spinning on the {} catch-all. (Populating real offers
	// needs packed-config item SKUs.)
	mux.HandleFunc("GET /storefront/real/offers/{id}", handlePlayerStore)

	// AccelByte per-player progression tracks (distinct from the storefront
	// battlepass tracks). Model FAccelByteModelsListUserProgressionInfoPagingSliced
	// Result — standard data/paging wrapper.
	mux.HandleFunc("GET /progression/players/{id}/tracks", handleEmptyDataPaging)

	// Content-service master manifest — the catalog of what EXISTS (heroes,
	// cosmetics, offers, …). This is the lever for the HUNTERS grid / STORE /
	// cosmetics: the client retried our {} stub 264x/run because it's invalid, and
	// with no manifest it has no catalog (empty grid; LogAssetManager "Invalid
	// Primary Asset Type"). See handleContentManifest for the recovered model.
	mux.HandleFunc("GET /content-service/manifest/{version}", handleContentManifest)
}

// handleContentManifest returns the ContentManifest — the master content catalog.
// Model recovered from the shipping-exe FName pool (the packer left the reflection
// pool intact): a set of TMap<FString SKU, ContentServicePrimaryAsset> fields —
// Heroes, Items, Emotes, PlayerTitles, HeroCosmeticsBundles, StoreOffers,
// SlotCosmetics, Minions, GameAugments, Equipment, Powers — plus scalar
// CurrentPatchVersion + PatchVersions. Each entry is a ContentServicePrimaryAsset
// (fields incl. PrimaryAssetName/AssetPath/DisplayName — pooled, types unconfirmed).
//
// PROBE #1 (shape-first): all maps present so the validity predicate passes and the
// 264x retry stops; Heroes populated with the 25 lowercase codenames carrying ONLY
// PrimaryAssetName (almost certainly FString) so a wrong-typed reject would still
// name the field rather than silently zeroing everything. Other maps empty. Relaunch
// readback: OnContentManifestUpdated firing + the 264x dropping confirms the model;
// any "Invalid response"/"Deserialization failure" names the next fix; the HUNTERS
// grid shows whether PrimaryAssetName alone resolves a card (likely needs AssetPath
// next).
func handleContentManifest(w http.ResponseWriter, r *http.Request) {
	heroes := map[string]any{}
	for _, h := range heroCodenames {
		heroes[h] = map[string]any{"PrimaryAssetName": h}
	}
	writeJSON(w, map[string]any{
		"CurrentPatchVersion":  r.PathValue("version"),
		"PatchVersions":        []any{},
		"Heroes":               heroes,
		"Items":                map[string]any{},
		"Emotes":               map[string]any{},
		"PlayerTitles":         map[string]any{},
		"HeroCosmeticsBundles": map[string]any{},
		"StoreOffers":          map[string]any{},
		"SlotCosmetics":        map[string]any{},
		"Minions":              map[string]any{},
		"GameAugments":         map[string]any{},
		"Equipment":            map[string]any{},
		"Powers":               map[string]any{},
	})
}

// handleEmptyDataPaging returns the standard AccelByte {data:[],paging:{}} wrapper
// for list endpoints whose required field is `data` (present-but-empty satisfies
// the validity predicate without a wrong-type risk).
func handleEmptyDataPaging(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"data":   []any{},
		"paging": map[string]any{"previous": "", "next": ""},
	})
}

// handleInventory returns LokiPlatformInventory { AssetEntries: [...] } — valid
// empty. (A probe putting "heroToken" entries here parsed but did not satisfy the
// hero-token read, so that count is tested via the wallet instead; see handleWallet.
// Populating owned cosmetics here needs packed-config SKUs we can't yet read.)
// heroCodenames are the 25 packed hero codenames (from IoStore path enumeration),
// lowercased — the format hero-pack store offers use to reference heroes, and the
// format /storefront/heroes accepted as "Unlockable heroes fetched: 25".
var heroCodenames = []string{
	"alchemist", "assault", "backlinehealer", "beebo", "bountyhunter",
	"burstcaster", "earthtank", "farshot", "firefox", "flex",
	"freeze", "gunner", "hookguy", "huntress", "reaper",
	"reshealer", "rocketjumper", "ronin", "shieldbot", "sniper",
	"stalker", "storm", "succubus", "void", "wukong",
}

// handleInventory returns owned items. The inventory-probe (25 owned heroes keyed by
// lowercase codename) was REVERTED to empty: it triggered `LogAssetManager: Invalid
// Primary Asset Type` — proving the roster resolves through UE's AssetManager
// PrimaryAssetId/bundle system, NOT plain SKUs. The real lever is the CONTENT-SERVICE
// MANIFEST (the master catalog declaring which heroes/cosmetics/offers exist); inventory
// only marks ownership of catalog entries. Repopulate this once the manifest + the
// ContentServicePrimaryAsset entry shape are nailed (see handleContentManifest TODO).
func handleInventory(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"AssetEntries": []any{}})
}

// handleFreeInventory returns the free-rotation inventory — valid empty wrapper.
func handleFreeInventory(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"AssetEntries": []any{}})
}

// handleWallet returns FLokiStorefrontPlayerWallet. Binary shows exactly one
// field on the struct: `Balances` with a `Balances_Key` companion => it is a
// TMap<FString, ?>. The map's VALUE type isn't visible statically, so this is a
// probe: we send int values. Relaunch outcomes pin it down via Loki.log —
//   - clean parse                          => value type is int (or number);
//     currency shows iff these codes are the ones the UI reads.
//   - "Deserialization failure" on
//     FLokiStorefrontPlayerWallet           => value is a struct, not int — switch
//     to FLokiStorefrontCurrencyAmount-shaped values next.
// Currency codes are not static strings in the exe (server/packed-config defined),
// so the keys here are best-guess and may need correction once the value type is
// confirmed.
func handleWallet(w http.ResponseWriter, r *http.Request) {
	// Balances is TMap<FString,int> (confirmed). DECODE RESULTS so far:
	//   - purple counter showed 2004 => Vive Points key is "vp"  ✅
	//   - gold counter (Theorycraft Coins, premium) stayed 0 => none of batch-1's
	//     premium candidates (coins/Coins/theorycraft_coins/TheorycraftCoins/tc/
	//     premium_currency/premium/tc_coin/PremiumCurrency/gold/Gold) is the key.
	//
	// DECODE COMPLETE. "vp" => Vive Points (purple counter). The GOLD counter is
	// Theorycraft Coins — the real-money premium currency; a fresh account has 0,
	// so 0 is AUTHENTIC (and is why all 91 wallet-key candidates failed: premium
	// balance isn't a virtual-wallet entry). Probe retired; real balances below.
	writeJSON(w, map[string]any{
		"Balances": map[string]any{
			"vp": 2004, // Vive Points (purple counter) — the one wallet currency the
			// menu surfaces. Gold counter = Theorycraft Coins = real-money premium,
			// authentically 0. (Confirmed a "heroToken" wallet balance does NOT feed
			// UBattlepassHeroUnlocker — the hero-token count comes from the battlepass
			// reward-track claim state, which needs packed reward SKUs.)
		},
	})
}

// handleHeroes returns FLokiStorefrontHeroes. CONFIRMED last relaunch: the array
// field is "heroes" (the probe element-count 2 => "Unlockable heroes fetched: 2").
// Real HeroId codenames came from asset paths in Loki.log (/Game/Loki/Characters/
// Heroes/<Name>): ShieldBot, HookGuy, Beebo, Wukong, Ronin, Huntress, Stalker,
// Reaper, Storm, Void, Freeze, Gunner, Alchemist, Sniper, ...
//
// handleHeroes returns FLokiStorefrontHeroes { heroes: TArray<FString> } (hero
// IDs). CONFIRMED the array parses strings cleanly, but the "ALL HUNTERS" grid
// resolves each ID against the packed hero catalog by a SKU/asset-id format that
// is baked into the IoStore .pak data (not in the exe, not the codename/display
// name). Without IoStore catalog extraction we can't supply resolvable IDs, so we
// return a valid-empty list (no error, no phantom cards) until that path exists.
func handleHeroes(w http.ResponseWriter, r *http.Request) {
	// IoStore extraction (Track A) recovered the storefront SKU vocabulary from the
	// packed BP_StoreOffer_* name maps (tools/extractor). Hero-pack offers reference
	// heroes by LOWERCASE codename (assault, beebo, flex, freeze, gunner, rocketjumper,
	// stalker, void seen in offer name maps) — strongly implying the hero unlock SKU is
	// the lowercase codename, NOT the PascalCase asset codename the Milestone-2 probe
	// sent (which rendered nothing). Sending all 25 lowercase codenames as the confirmed
	// FLokiStorefrontHeroes { heroes: TArray<FString> } shape. Relaunch + LogPlatform
	// Storefront ("Unlockable heroes fetched: %d") / the HUNTERS grid confirm the format.
	heroes := []string{
		"alchemist", "assault", "backlinehealer", "beebo", "bountyhunter",
		"burstcaster", "earthtank", "farshot", "firefox", "flex",
		"freeze", "gunner", "hookguy", "huntress", "reaper",
		"reshealer", "rocketjumper", "ronin", "shieldbot", "sniper",
		"stalker", "storm", "succubus", "void", "wukong",
	}
	writeJSON(w, map[string]any{"heroes": heroes})
}

// handlePlayerStore returns FLokiStorefrontPlayerStore (the /storefront/offers/{id}
// response): RotatingOffers, FeaturedItemOffers, TypeOffers (arrays) + NextRotation
// (omitted — it's almost certainly an FDateTime and a bad string would reject the
// doc; an absent field safely defaults). Empty arrays = valid container, empty shop
// — no regression, and the correct shape to grow item offers into later.
func handlePlayerStore(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"RotatingOffers":     []any{},
		"FeaturedItemOffers": []any{},
		"TypeOffers":         []any{},
	})
}

func handleProgressionTracks(w http.ResponseWriter, r *http.Request) {
	// Empty data deserializes cleanly, but the battlepass managers then tight-loop
	// this endpoint (~100 req/s, silently — no per-request error in Loki.log)
	// because the consumer `UStorefront::GetCurrentPublishedProgressionTracks`
	// finds no *published* track to adopt and immediately re-queries.
	//
	// So we now return one populated FAccelByteModelsListProgressionTrackInfo
	// element. Field selection follows the validity rule (endpoints.md): UE's
	// JsonObjectStringToUStruct *ignores* JSON keys that match no UPROPERTY and
	// only rejects the whole doc when a key that DOES match has a wrong type. So
	// every field below is either confirmed on this struct by the binary's
	// FName cluster (ProgressionType, RewardTrackCodes) or — if present at all —
	// is an FString/enum-string (Id, Code, Status), which is the type AccelByte
	// uses for these. None are bool/int/struct, so a populated element cannot
	// regress the clean parse we already have.
	//
	//   ProgressionType  EAccelByteProgressionTrackType  -> "SEASON_PASS"
	//                    (enum values: NONE | SEASON_PASS | PROGRESSION_TRACK)
	//   Status           EAccelByteProgressionTrackStatus -> "PUBLISHED"
	//                    (enum values: NONE | DRAFT | PUBLISHED | RETIRED) — the
	//                    bet that quiets "current *published*" filter.
	//   RewardTrackCodes TArray<FString> — confirmed on this struct.
	//
	// If a relaunch shows the loop persists or a new "Invalid response"/
	// "Deserialization failure" appears, the log names the next field to add or
	// the wrong-typed one to drop.
	writeJSON(w, map[string]any{
		"data": []any{
			map[string]any{
				"Id":               "supervive-season-1",
				"Code":             "supervive-season-1",
				"ProgressionType":  "SEASON_PASS",
				"Status":           "PUBLISHED",
				"RewardTrackCodes": []string{"supervive-season-1-track"},
			},
		},
		"paging": map[string]any{"previous": "", "next": ""},
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(v)
}
