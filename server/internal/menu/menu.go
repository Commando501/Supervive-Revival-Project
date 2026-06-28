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
	"time"
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
	// PROBE #3 (real assets, usmap-backed): each hero entry carries the real
	// ContentServicePrimaryAsset data from BP_HeroAsset_<Hero> — PrimaryAssetType "Hero",
	// PrimaryAssetName (the InternalName / codename, e.g. "assault"; the asset overrides
	// GetPrimaryAssetId to a clean name, confirmed by the hero's DefaultCosmeticsBundle ref
	// being "AssaultDefault" not the BP_ asset name), and the full AssetPath.
	//   - PROBE #1 sent only PrimaryAssetName, no type -> AssetManager "Invalid Primary
	//     Asset Type ... failed to find NameData" (every hunter = UnknownHero "?").
	//   - PROBE #2 ("HeroAsset") and #3 ("Hero" as a flat string): SAME error. The manifest
	//     DESERIALIZED fine each time, but the AssetManager never registered the type.
	//   - PROBE #4 (current): the real cause is FIELD TYPES, not the value. The
	//     BP_HeroAsset dump shows FPrimaryAssetType fields serialize as {"Name": ...} and
	//     FSoftObjectPath fields as {"AssetPathName","SubPathString"}. We were sending flat
	//     strings, which UE silently SKIPS (wrong type) -> type/path register EMPTY ->
	//     "failed to find NameData". Now sent in the proper nested struct forms.
	// GROUND TRUTH (extracted Loki/Config/DefaultGame.ini via the extractor's new `raw`
	// mode): PrimaryAssetType="Hero", AssetBaseClass=/Script/Loki.LokiHeroAsset, scanned
	// from /Game/Loki/Characters/Heroes — so "Hero" is the type and the AssetManager scans
	// the heroes itself. Crucially [AssetManagerSettings] bShouldManagerDetermineTypeAndName
	// =True, which means the manager DERIVES PrimaryAssetName from the asset's SHORT NAME
	// ("BP_HeroAsset_Assault"), NOT the GetPrimaryAssetId override (so codename "assault"
	// gave "Invalid Primary Asset Id"). PROBE #5: PrimaryAssetName = the BP_HeroAsset_<Hero>
	// basename. Relaunch readback: HUNTERS grid / pedestal render real models (no "?").
	heroes := map[string]any{}
	for sku, folder := range heroFolders {
		asset := "BP_HeroAsset_" + folder
		path := "/Game/Loki/Characters/Heroes/" + folder + "/" + asset + "." + asset + "_C"
		heroes[sku] = map[string]any{
			// EXACT ContentServicePrimaryAsset shape (usmap schema): all plain FStrings + bool.
			// PrimaryAssetName = the hero codename / InternalName ("assault") — the config
			// scan that would force the asset-short-name ("BP_HeroAsset_Assault") is NOT running
			// in this build (Season:S2_Season also fails), so the runtime id comes from
			// LokiHeroAsset's GetPrimaryAssetId override = InternalName, matching what
			// /storefront/heroes ("Unlockable heroes fetched") uses. AssetPath still points at
			// the real BP_HeroAsset file so the registered id resolves to the asset.
			"PrimaryAssetType": "Hero",
			"PrimaryAssetName": sku,
			"AssetPath":        path,
			"Status":           "Enabled",
			"IsDefault":        false,
		}
	}
	// MISSION PROBE #2 RESULT (2026-06-28): injecting a MissionPool entry into the proven-
	// consumed Heroes map (per-entry PrimaryAssetType "MissionPool") STILL failed —
	// "Invalid Primary Asset Id MissionPool:DA_MissionPoolDailyChallenge: failed to find
	// NameData". So the manifest consumer keys the registered type off the MAP NAME, not the
	// entry's PrimaryAssetType field. With no mission map in ContentServiceContentManifest, the
	// manifest CANNOT register missions/pools — confirmed not backend-fixable. The fix is
	// native (trigger LokiAssetManager's primary-asset scan). Probe reverted.
	// HeroCosmeticsBundles: the hero's 3D model on the pedestal/grid is its DEFAULT
	// cosmetics bundle, which the hero asset references as HeroCosmeticsBundle:<Hero>Default
	// (e.g. "AssaultDefault"). With this map empty the client logs "SetHero with CosmeticsAssetId
	// ( - true)" (empty) -> UnknownHero "?". We register each default bundle: key + name =
	// "<Folder>Default" (the hero's hardcoded reference), AssetPath = the real bundle. Only the
	// 14 heroes with a canonical BP_<Hero>_DefaultCosmeticsBundle are populated here; the rest
	// use irregular names (added once this is validated).
	cosmetics := map[string]any{}
	for folder, assetBase := range heroDefaultBundles {
		bpath := "/Game/Loki/Characters/Heroes/" + folder + "/Cosmetics/Default/" + assetBase + "." + assetBase + "_C"
		sku := folder + "Default"
		cosmetics[sku] = map[string]any{
			"PrimaryAssetType": "HeroCosmeticsBundle",
			"PrimaryAssetName": sku,
			"AssetPath":        bpath,
			"Status":           "Enabled",
			"IsDefault":        true,
		}
	}

	// MISSIONS: NOT backend-fixable via this manifest. MISSION PROBE #1 (2026-06-28) injected
	// the 16 mission pools (each self-describing PrimaryAssetType "MissionPool") into the Powers
	// map + pointed CurrentSeason at MissionPool:DA_MissionPoolDailyChallenge. Relaunch result:
	// "Invalid Primary Asset Id MissionPool:DA_MissionPoolDailyChallenge: ... failed to find
	// NameData" — so the manifest keys the registered type off the MAP NAME, not each entry's
	// PrimaryAssetType field, and there is no Missions/MissionPool map in
	// ContentServiceContentManifest. Missions are local UE primary assets the modal must
	// ENUMERATE (LokiDataAsset_MissionPool/_Mission under /Game/Loki/Core/Missions); that
	// enumeration is dead in this build (stripped AssetRegistry.bin + no runtime scan) — the
	// SAME client-side blocker as the hunters grid. Fix is client-side (repack AssetRegistry.bin
	// with primary-asset data, or AngelScript), not this server. Probe reverted below.

	// Top-level ContentServiceContentManifest fields (usmap schema): ID, ETag, Version
	// (Int64), CurrentSeason (FPrimaryAssetId), CurrentPatchVersion, PatchVersions, + the
	// content maps. The earlier manifest omitted ID/ETag/Version/CurrentSeason — the client
	// re-fetched it 3338x (a reject/retry loop, never processing it). ETag+Version drive
	// change-detection, so we send stable values. CurrentSeason is an FPrimaryAssetId, which
	// (unlike ContentServicePrimaryAsset.PrimaryAssetType) IS a nested struct:
	// {PrimaryAssetType:{Name:"Season"}, PrimaryAssetName:"S2_Season"} (release 2.4 = S2).
	writeJSON(w, map[string]any{
		"ID":      "supervive-revival-manifest",
		"ETag":    "1",
		"Version": 1,
		// CurrentSeason is eagerly loaded via ChangeBundleStateForPrimaryAssets. DIAGNOSTIC
		// CONFIRMED (2026-06-27): pointing it at Hero:assault produced NO error — i.e. the
		// manifest's Heroes map DOES register primary assets and "Hero:assault" (codename) is
		// the valid id. Season has no map so it can't be registered; we leave it pointing at the
		// real season (a harmless "no NameData" warning) rather than mis-registering it.
		"CurrentSeason": map[string]any{
			"PrimaryAssetType": map[string]any{"Name": "Season"},
			"PrimaryAssetName": "S2_Season",
		},
		"CurrentPatchVersion":  r.PathValue("version"),
		"PatchVersions":        []any{},
		"Heroes":               heroes,
		"Items":                map[string]any{},
		"Emotes":               map[string]any{},
		"PlayerTitles":         map[string]any{},
		"HeroCosmeticsBundles": cosmetics,
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

// heroFolders maps each hero SKU (lowercase InternalName, the content-manifest /
// storefront key) to its PascalCase content folder + asset basename, recovered from the
// usmap dump of BP_HeroAsset_<Hero> (path /Game/Loki/Characters/Heroes/<Folder>/
// BP_HeroAsset_<Folder>). Used to build real ContentServicePrimaryAsset entries.
var heroFolders = map[string]string{
	"alchemist": "Alchemist", "assault": "Assault", "backlinehealer": "BacklineHealer",
	"beebo": "Beebo", "bountyhunter": "BountyHunter", "burstcaster": "BurstCaster",
	"earthtank": "Earthtank", "farshot": "FarShot", "firefox": "FireFox", "flex": "Flex",
	"freeze": "Freeze", "gunner": "Gunner", "hookguy": "HookGuy", "huntress": "Huntress",
	"reaper": "Reaper", "reshealer": "ResHealer", "rocketjumper": "RocketJumper",
	"ronin": "Ronin", "shieldbot": "ShieldBot", "sniper": "Sniper", "stalker": "Stalker",
	"storm": "Storm", "succubus": "Succubus", "void": "Void", "wukong": "Wukong",
}

// heroDefaultBundles maps a hero's content folder to the basename of its default cosmetics
// bundle asset (usmap path enumeration). Only the 14 heroes with a canonical
// BP_<Hero>_DefaultCosmeticsBundle are listed; note FireFox's asset is "Firefox" (lowercase f).
var heroDefaultBundles = map[string]string{
	"Assault": "BP_Assault_DefaultCosmeticsBundle", "BacklineHealer": "BP_BacklineHealer_DefaultCosmeticsBundle",
	"FireFox": "BP_Firefox_DefaultCosmeticsBundle", "Flex": "BP_Flex_DefaultCosmeticsBundle",
	"Freeze": "BP_Freeze_DefaultCosmeticsBundle", "Gunner": "BP_Gunner_DefaultCosmeticsBundle",
	"HookGuy": "BP_HookGuy_DefaultCosmeticsBundle", "Huntress": "BP_Huntress_DefaultCosmeticsBundle",
	"RocketJumper": "BP_RocketJumper_DefaultCosmeticsBundle", "Ronin": "BP_Ronin_DefaultCosmeticsBundle",
	"ShieldBot": "BP_ShieldBot_DefaultCosmeticsBundle", "Sniper": "BP_Sniper_DefaultCosmeticsBundle",
	"Storm": "BP_Storm_DefaultCosmeticsBundle", "Void": "BP_Void_DefaultCosmeticsBundle",
}

// handleInventory returns LokiPlatformInventory { AssetEntries: [...], Version } — now
// granting ownership of every hero + its default cosmetics, so the hunters are PLAYable
// (not "PURCHASE 20,000") and the hero-select preview can resolve an owned model.
// Model (usmap schema): LokiPlatformInventoryAssetEntry { AssetId (FPrimaryAssetId, nested
// {PrimaryAssetType:{Name},PrimaryAssetName}); bool IsOwned/IsFree/IsDefault/IsPremiumBenefit;
// EntitlementIDs[] }. AssetIds match the content-manifest entries (Hero:BP_HeroAsset_<X>,
// HeroCosmeticsBundle:<X>Default).
func handleInventory(w http.ResponseWriter, r *http.Request) {
	entries := []any{}
	now := time.Now().UTC().Format(time.RFC3339)
	owned := func(typeName, assetName string, isDefault bool) map[string]any {
		// Full OWNED entry: IsOwned alone didn't flip "PURCHASE 20,000", so we also supply a
		// non-empty EntitlementIDs (entitlement-based ownership) + AdditionalDetails.PurchasedAt
		// (TMap, confirmed by the PurchasedAt_Key companion) — the real "this was acquired"
		// signal. EntitlementID is synthetic but non-empty.
		entID := "ent-" + typeName + "-" + assetName
		return map[string]any{
			"AssetId": map[string]any{
				"PrimaryAssetType": map[string]any{"Name": typeName},
				"PrimaryAssetName": assetName,
			},
			"IsOwned":          true,
			"IsFree":           false,
			"IsDefault":        isDefault,
			"IsPremiumBenefit": false,
			"EntitlementIDs":   []any{entID},
			"AdditionalDetails": map[string]any{
				"PurchasedAt": map[string]any{entID: now},
			},
		}
	}
	for codename := range heroFolders {
		entries = append(entries, owned("Hero", codename, false))
	}
	for folder := range heroDefaultBundles {
		entries = append(entries, owned("HeroCosmeticsBundle", folder+"Default", true))
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
	// /storefront/heroes IS the HUNTERS grid source (confirmed: emptying it emptied the grid).
	// It is NOT the ownership signal either (emptying it did not clear PURCHASE). So the grid
	// lists all 25 here; ownership/PURCHASE is determined elsewhere (still unresolved).
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
