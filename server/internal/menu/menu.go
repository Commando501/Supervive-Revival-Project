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
	// currency top-up packs. Same FLokiStorefrontPlayerStore shape as the virtual
	// store; now populated with the real Theorycraft Coin / Vive Point pack SKUs
	// (storeoffers_summary.json). See handleRealMoneyStore.
	mux.HandleFunc("GET /storefront/real/offers/{id}", handleRealMoneyStore)

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
// Reverted 2026-06-28 after probe #2 (populated HeroCosmeticsBundles with 25 entries
// carrying PrimaryAssetType/PrimaryAssetName/AssetPath) produced ZERO observable
// effect: grid still empty, "?" preview unchanged, no new ChangeBundleState log
// activity for any of the registered bundle IDs. Combined with probe #3 (inventory
// ownership entries — see handleInventory) and the prior session's RE, this confirms
// `LokiAssetManager` registers manifest assets but the menu's grid/store enumeration
// queries through `ScanPrimaryAssetTypesFromConfig` (deliberately bypassed in this
// build), NOT through manifest registrations. Backend route closed; see
// docs/hero-roster-attempts.md for the full attempt log.
func handleContentManifest(w http.ResponseWriter, r *http.Request) {
	// The client ALWAYS requests this with ?nonEnabledOnly=true — i.e. "which content
	// is NOT enabled/released?". Anything we return here is therefore treated by the
	// client as NON-enabled and HIDDEN. Prior sessions populated Heroes here, which
	// (we now understand) marked all 25 heroes non-enabled — so the ALL HUNTERS grid
	// filtered them out even once the AssetManager enumeration was populated
	// (scan_on_enum: GetPrimaryAssetIdList(Hero) returns 25). Session 44: return an
	// EMPTY heroes map for the nonEnabledOnly query so every hero stays ENABLED and the
	// grid can render the enumerated roster. (Only the full-manifest form, which the
	// client does not request, lists heroes.)
	nonEnabledOnly := r.URL.Query().Get("nonEnabledOnly") == "true"
	heroes := map[string]any{}
	if !nonEnabledOnly {
		for _, h := range heroCodenames {
			heroes[h] = map[string]any{"PrimaryAssetName": h}
		}
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

// handleInventory returns owned items. Earlier probe (25 owned heroes keyed by
// lowercase codename) triggered `LogAssetManager: Invalid Primary Asset Type`
// because the field is interpreted as a typed PrimaryAssetId, not a plain SKU.
//
// 2026-06-28 probe #3 (the "ownership gates grid" hypothesis): returned 50 entries
// of shape `{"AssetId": "Hero:<lower>"}` + `{"AssetId": "HeroCosmeticsBundle:<Pascal>Default"}`.
// Result: parser accepted the payload (no deserialization error, `LogPlatformInventory:
// Refreshed player inventory` succeeded), but UI was identical — grid empty, "?" preview,
// zero new ChangeBundleState activity. That probe had TWO now-known problems: (a) it ran
// BEFORE the IsCatalogDataReady gate was fixed (session 47 — the whole catalog UI was gated
// off from building, so nothing could reflect ownership); (b) the entries carried NO
// `IsOwned:true` — the real ownership signal per the recovered model.
//
// MODEL (usmap schema.txt): LokiPlatformInventory { AssetEntries: []LokiPlatformInventoryAssetEntry,
// Version int64 }; LokiPlatformInventoryAssetEntry { AssetId PrimaryAssetId, IsFree bool, IsOwned
// bool, IsDefault bool, IsPremiumBenefit bool, EntitlementIDs [], AdditionalDetails {} }. The
// "Hero:<name>" string form parses into the AssetId PrimaryAssetId (custom text import); FName
// match is case-insensitive so the lowercase codenames link to the mixed-case catalog names.
//
// Session 47 (post-gate-fix): own all 25 heroes with IsOwned=true so the ALL HUNTERS tiles unlock
// (drop the "Hunter not owned" lock) and the menu can surface a default hunter instead of the "?"
// empty-inventory placeholder. IsDefault marks a starting hunter.
func handleInventory(w http.ResponseWriter, r *http.Request) {
	entries := make([]any, 0, len(heroCodenames))
	for i, h := range heroCodenames {
		entries = append(entries, map[string]any{
			"AssetId":   "Hero:" + h,
			"IsOwned":   true,
			"IsDefault": i == 0, // one starting hunter (alchemist) as the default
		})
	}
	writeJSON(w, map[string]any{"AssetEntries": entries, "Version": 1})
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

// handlePlayerStore returns FLokiStorefrontPlayerStore, the /storefront/offers/{id}
// response (the virtual-currency store: cosmetic bundles/skins bought with vp/coins).
//
// SCHEMA CORRECTION (2026-07-05, schema.txt): the earlier stub sent empty
// RotatingOffers/FeaturedItemOffers/TypeOffers and NEVER sent the field that actually
// carries purchasable items. Per schema.txt LokiStorefrontPlayerStore has SIX fields:
//
//	Region             StrProperty
//	ItemOffers         Array<LokiStorefrontPlayerItemOffer>   <- the real offer list
//	RotatingOffers     Array<DateTime>   (rotation timestamps, NOT offers)
//	NextRotation       DateTime
//	FeaturedItemOffers Array<LokiStorefrontTypeOffer>  (AssetType+SlotName structs)
//	TypeOffers         Array<Str>
//
// So the store has never actually been handed an offer array. PROBE #1: populate
// ItemOffers with the real SKUs recovered by IoStore extraction
// (tools/extractor/out/catalog/storeoffers_summary.json — 56 offers from the packed
// BP_StoreOffer_* assets). This is only viable now that the catalog is loaded
// client-side (catalog_ready_fix opens the IsCatalogDataReady gate → the 904-entry
// CatalogManager map holds every one of these SKUs), so an advertised SKU can resolve
// to its packed presentation (icon/name/price via LokiStorefrontOfferingCost baked in
// the offer asset). RotatingOffers/NextRotation are omitted (Array<DateTime>/DateTime —
// an absent field safely defaults; a bad datetime string would reject the whole doc).
//
// Validity: every LokiStorefrontPlayerItemOffer field is Str/Bool/Int/Array<Str>, so
// nothing here can wrong-type-reject the doc. Costs is left empty on probe #1 (the
// packed offer asset carries the real cost); NameSpace empty (a guessed namespace could
// silently filter). If the relaunch shows offers parsed but priceless/hidden, the next
// single variables in order are: Costs format, then Category routing, then NameSpace.
// Readback: LogPlatformStorefront (the "…fetched" channel) should report the offer
// count, and the STORE tab shows whether an advertised SKU resolves to a tile.
func handlePlayerStore(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"Region":             "us-east",
		"ItemOffers":         storeItemOffers(virtualStoreSKUs, "Bundles", "StoreOffer"),
		"FeaturedItemOffers": storeFeaturedOffers(featuredStoreSKUs),
	})
}

// featuredStoreSKUs — offers highlighted in the FEATURED carousel. Bare offer names;
// storeFeaturedOffers prefixes each into "StoreOffer:<name>" (the PrimaryAssetId string
// the carousel's `Get Carousel Offers` filter requires).
//
// TWO conditions must BOTH hold for the carousel to render (learned live 2026-07-05):
//  (1) SKU = "StoreOffer:<name>" so GetCatalogEntry(PrimaryAssetIDFromString(SKU)) is
//      valid — else the offer is filtered out. (StoreOffer: prefix fixes this.)
//  (2) the offer's asset must have a non-null WideSplashArt to async-load — else the
//      carousel logs "RequestAsyncLoad() called with empty or only null assets!" and
//      spins. The supporter packs (Starter/Superviver/Patron) resolved fine (1) but have
//      NULL WideSplashArt (3x that warning at store-open) => spin. The cosmetic SKIN
//      packs are authored WITH WideSplashArt for featuring, so switch to those.
var featuredStoreSKUs = []string{
	"CyberpunkWukongPack", "HuntressGodQueenPack", "GodOfTimeVoidPack",
	"OniHookguyPack", "DemonessFlexPack",
}

// storeFeaturedOffers builds []LokiStorefrontTypeOffer for the FEATURED carousel.
//
// ROOT CAUSE (bpdump of WBP_UI_Storefront_Featured::"Get Carousel Offers"): the carousel
// filters FeaturedItemOffers by
//     id    = PrimaryAssetIDFromString(offer.SKU)     // parses "Type:Name", IGNORES AssetType
//     entry = GetCatalogManager().GetCatalogEntry(id)
//     keep iff IsValid(entry) && !IsHidden() && !IsDisabled()
// So the SKU field must be the FULL PrimaryAssetId STRING "StoreOffer:<name>" (same
// "Type:Name" form as the hero catalog key "Hero:assault"). Probes #1/#2 sent a BARE SKU
// ("StarterPack") — FPrimaryAssetId::FromString finds no ':' => invalid id =>
// GetCatalogEntry null => every offer filtered out => empty carousel => it SPINS forever
// (and AssetType JSON shape was a red herring — the carousel never reads AssetType).
// Probe #4 (this): prefix SKU with "StoreOffer:". AssetType is still sent as the
// canonical string for any OTHER consumer, but the carousel filter uses SKU only.
func storeFeaturedOffers(skus []string) []map[string]any {
	offers := make([]map[string]any, 0, len(skus))
	for _, sku := range skus {
		offers = append(offers, map[string]any{
			"SKU":       "StoreOffer:" + sku,
			"Costs":     []string{},
			"AssetType": "StoreOffer",
			"SlotName":  "",
		})
	}
	return offers
}

// handleRealMoneyStore returns the /storefront/real/offers/{id} response
// (UStorefrontManager::GetRealMoneyStorefront — the currency top-up packs bought with
// real money). Same FLokiStorefrontPlayerStore shape as the virtual store; ItemOffers
// carries the Theorycraft Coin / Vive Point packs. See handlePlayerStore for the
// schema-correction and probe rationale.
func handleRealMoneyStore(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"Region":     "us-east",
		"ItemOffers": storeItemOffers(realMoneyStoreSKUs, "Currency", ""),
	})
}

// virtualStoreSKUs — cosmetic bundle/skin offers (bought with virtual currency).
//
// *** THESE ARE THE REAL PrimaryAssetNames, read LIVE from the game's own
// LokiAssetLoader.StoreOfferAssets map (RPM of the running client, tools/re/probe). ***
// The storeoffers_summary.json "id" field is NOT the catalog key — it's a display/config
// name, and for many offers it DIFFERS from the actual PrimaryAssetName the loader keys
// by (StarterPack→starter2024, SupporterPack→supporter2024, CollectorPack→collector2024,
// EarlyBirdBundle→earlybirdob, EmotePack→t1emotepack, FreezeBrideOfSwordsPack→
// BrideOfSwordsFreezePack, JTW_EpicsBundle→JTWEpicsPack, SpaceMarineAssaultPack→
// SpaceMarineGhostPack; currency tiers → tp####/vp##). Using the summary "id" made
// LokiAssetLoader::LoadStoreOfferAsset MISS on the map lookup ("Failed to load store
// offer asset with ID StoreOffer:StarterPack") so the BUNDLES tab rendered blank even
// though the map holds all 56 offers. These are the exact 56 keys (token variants omitted).
var virtualStoreSKUs = []string{
	"BackToSchoolPack", "BrideOfSwordsFreezePack", "ChinchillaPack", "CyberpunkWukongPack",
	"CybertigerStalkerPack", "DarkOrderSniperPack", "DemonessFlexPack", "GAResHealerPack",
	"GodOfTimeVoidPack", "HuntressGodQueenPack", "JTWEpicsPack", "MidAutumnPack",
	"NecroGhostPack", "OniHookguyPack", "RatPack", "S1Special", "S2Special",
	"SanctuarySentinelShieldBotPack", "SpaceMarineGhostPack", "Winter2025Pack",
	"collector2024", "earlybirdob", "starter2024", "supporter2024", "t1emotepack",
}

// realMoneyStoreSKUs — currency top-up packs (real PrimaryAssetNames from the live map).
var realMoneyStoreSKUs = []string{
	"tp475", "tp600", "tp1000", "tp2000", "tp3650", "tp5350", "tp11000",
	"vp10", "vp20", "vp30", "vp40", "vp50", "vp90", "vp100", "vp120",
	"vp150", "vp240", "vp270", "vp480",
}

// storeItemOffers builds a []LokiStorefrontPlayerItemOffer for the given SKUs. All
// fields are type-safe per schema.txt (Str/Bool/Int/Array<Str>). Costs empty (client
// resolves price from the packed offer asset); Category is a best-guess routing hint.
//
// skuType: when non-empty, the SKU is emitted as the full PrimaryAssetId string
// "<skuType>:<name>". The BUNDLES tab's native GetStoreOfferBundleListForStore resolves
// the offer SKU the same way the FEATURED carousel does (PrimaryAssetIDFromString), so a
// bare SKU produces an invalid id and the tab shows "No Results" — hence "StoreOffer".
// (Currency/real-money store passes "" for the bare form.)
func storeItemOffers(skus []string, category, skuType string) []map[string]any {
	offers := make([]map[string]any, 0, len(skus))
	for _, sku := range skus {
		id := sku
		if skuType != "" {
			id = skuType + ":" + sku
		}
		offers = append(offers, map[string]any{
			"SKU":         id,
			"Category":    category,
			"NameSpace":   "",
			"Purchasable": true,
			"PID":         sku,
			"Costs":       []string{},
			"SteamItemID": 0,
		})
	}
	return offers
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
