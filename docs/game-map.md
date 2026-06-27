# SUPERVIVE game map

A comprehensive catalog of every gameplay-defining asset extracted from the shipping
build via [the external usmap dumper](r2-findings.md). 6,363 assets across 14
categories, all decoded to JSON and indexed to per-category CSVs.

## Master index

| Category | Count | Description | Index CSV | Raw JSON |
|---|---:|---|---|---|
| `ge` | 2,429 | GameplayEffects — buffs/debuffs, damage, status | `catalog/ge_index.csv` | `catalog/ge/` |
| `titles` | 659 | Player titles (BP_PlayerTitle_*) | `catalog/titles_index.csv` | `catalog/titles/` |
| `gs` | 596 | GameplaySpells — ability instances | `catalog/gs_index.csv` | `catalog/gs/` |
| `da` | 494 | DataAssets — configs (Mission/Equipment/Power/etc.) | `catalog/da_index.csv` | `catalog/da/` |
| `items` | 481 | In-game items (BP_ITEM_*) | `catalog/items_index.csv` | `catalog/items/` |
| `bundles` | 353 | Hero cosmetic bundles (skins/chromas) | `catalog/bundles_index.csv` | `catalog/bundles/` |
| `gp` | 344 | GameplayPersistent (passive effects) | `catalog/gp_index.csv` | `catalog/gp/` |
| `emotes` | 326 | Emotes (BP_Emote_*) | `catalog/emotes_index.csv` | `catalog/emotes/` |
| `avatars` | 233 | Profile avatars (BP_Avatar_*) | `catalog/avatars_index.csv` | `catalog/avatars/` |
| `sprays` | 146 | Sprays (BP_Spray_*) | `catalog/sprays_index.csv` | `catalog/sprays/` |
| `gliders` | 116 | Gliders (BP_Glider_*) | `catalog/gliders_index.csv` | `catalog/gliders/` |
| `dt` | 113 | DataTables (gameplay numbers) | `catalog/dt_index.csv` | `catalog/dt/` |
| `st` | 64 | StringTables (UI text, localization keys) | `catalog/st_index.csv` | `catalog/st/` |
| `ga` | 9 | GameplayAbilities (base ability classes) | `catalog/ga_index.csv` | `catalog/ga/` |
| `storeoffers` | 56 | Store offers (currency tiers + bundle packs) | `catalog/storeoffers_summary.txt` | `BP_StoreOffer_*.json` |
| **Total** | **6,419** | | | |

## Bundles per hero (= unique skins)

| Hero | Bundles |
|---|---:|
| Freeze | 23 |
| Assault | 21 |
| Storm | 19 |
| Huntress | 19 |
| Ronin | 18 |
| ResHealer | 18 |
| BurstCaster | 18 |
| BacklineHealer | 18 |
| Void | 17 |
| Gunner | 17 |
| FireFox | 17 |
| Sniper | 16 |
| Wukong | 14 |
| Stalker | 14 |
| Beebo | 14 |
| ShieldBot | 13 |
| RocketJumper | 13 |
| Flex | 13 |
| HookGuy | 11 |
| Succubus | 9 |
| BountyHunter | 9 |
| FarShot | 8 |
| Earthtank | 8 |
| Reaper | 3 |
| Alchemist | 3 |
| **Total** | **353** |

## StringTables (UI text)

64 string tables with **1000+ total entries**. Selected high-value tables:

| Table | Keys | Contents |
|---|---:|---|
| `ST_Armory` | 132 | Item types (Perks/Relics/Kicks/Grips), weekly chest tiers, sort options, error strings |
| `ST_AbilityTooltips` | 64 | Hero ability descriptions |
| `ST_Armory_FlavorText` | 98 | Lore/flavor strings for items |
| `ST_Items` | ~12 | Armor tier names, Boots descriptions |
| `ST_Rarities` | ~30 | Tier0-5 = Common/Uncommon/Rare/Epic/Legendary/Exotic + format strings |
| `ST_Currencies` | ~8 | Gold→Coin, Gems→Prisma, Tears→Shards |
| `ST_AttributeDisplayNames` | 16 | Stat display names |
| `ST_AttributeDescriptions` | 4 | Stat tooltip text |
| `ST_Announcements` | 15 | In-game announcement strings |

See `catalog/st/<TableName>.json` for full key→value mappings.

## DataAssets (DA_*) breakdown

494 data assets across these subtypes (by name prefix):

| Subtype | Count | Examples |
|---|---:|---|
| `DA_Mission_*` | 330 | Hunter missions, daily/weekly challenges |
| `DA_Equipment_*` | 110 | Equipment (Relics) — `DA_Equipment_AirBlast`, `DA_Equipment_IronFist`, etc. |
| `DA_MapIcon_*` | 37 | Map icons |
| `DA_Power_*` | 35 | Power-up assets (Perks) |
| `DA_BiomeLighting_*` | 32 | Per-biome lighting configs |
| `DA_PaginatedModal_*` | 4 | UI modals |
| `DA_MissionPool*` | 11 | Mission rotation pools (Daily/Weekly/Tutorial/Onboarding) |
| `DA_Capsule_*` | 2 | Capsule (loot box) types |
| `DA_ArmoryTables_*` | 1 | Master armory catalog |

## DataTables (DT_*) breakdown

113 data tables. Sample row structs and counts:

```
DT_AccountLevelCrowns          UserDefinedStruct'FAccountLevelCrownEntry'      7 rows
DT_AugmentWeightList           UserDefinedStruct'AugmentWeight'               31 rows
DT_<Hero>_Default_BarkBehavior LokiBarkBehavior                             6-12 rows
DT_<Hero>_Default_BarkAudio    LokiBarkAudio                                   0 rows*
```

*BarkAudio rows are loaded at runtime from referenced soundbanks; the table itself is
just the schema.

## Cosmetic catalog details (frontend display data)

### Avatars (233)

Each `BP_Avatar_<Name>` has:
- `Portrait`: `/Game/Loki/Personalization/Avatars/<Name>/TX_Avatar_<Name>` — main UI icon
- `ExtendedPortrait`: `/Game/Loki/Personalization/Avatars/<Name>/TX_Avatar_<Name>_Extended` — large variant

Parent class: `LokiSlotCosmeticsAsset_Avatar`.

### Player titles (659)

Each `BP_PlayerTitle_<Name>` has a `Title` FText whose `SourceString` is empty in the
asset — display strings are looked up at runtime from a localization table by the
title's stable ID. Backend must echo the title ID; client renders the localized string.

Parent class: `LokiDataAsset_PlayerTitle`.

### Cosmetics bundles (353)

Skin variants per hero. Pattern: `BP_<Hero>_<Skin>_CosmeticsBundle`. Parent class:
`LokiHeroCosmeticsBundle`. Each bundle's single significant property is
`MenuCosmeticsControllerClass` → SoftClassPath to the in-game cosmetics controller
that swaps the hero's mesh/materials/animations.

## Store offers (56, fully decoded)

See `catalog/storeoffers_summary.txt` for the full list. Two kinds:

**Currency offers** — `BP_StoreOffer_<N>(VivePoints|TheorycraftCoins)[ExchangeToken]`:

| Tier | SKU pattern | Display |
|---|---|---|
| 10–480 VP | `BP_StoreOffer_<N>VivePoints` | "{N} Vive Points" (some have bonus) |
| 475–11000 TC | `BP_StoreOffer_<N>TheorycraftCoins[ExchangeToken]` | "{N} Theorycraft Coin\n+ {bonus} Bonus" |

**Cosmetic bundles** (`GrantOfferEntitlement: true`):

| SKU | Display label |
|---|---|
| `CyberpunkWukongPack` | "Great Sage Wukong" |
| `DemonessFlexPack` | "Underworld Shiv" |
| `HuntressGodQueenPack` | "Eternal Empire Myth" |
| `FreezeBrideOfSwordsPack` | "Bride of Swords Celeste" |
| `GAResHealerPack` | "Angelic Force Elluna" |
| `GodOfTimeVoidPack` | "God of Time Void" |
| `NecroGhostPack` | "Necromancer Ghost" |
| `OniHookguyPack` | "Oni Kingpin" |
| `SanctuarySentinelShieldBotPack` | "Sanctuary Sentinel Oath" |
| `SpaceMarineAssaultPack` | "Hyperion Ghost" |
| (full list in catalog/storeoffers_summary.txt) | |

Mega bundles `StarterPack`, `SupporterPack`, `CollectorPack` (and their
`*ExchangeToken` variants) include rich-text `LongDescription` enumerating the bundle's
permanent rewards (skins, currencies, callsigns, pedestals, emotes).

## How Track B consumes this

The catalog CSVs and per-asset JSONs let the menu backend respond with **real game
data** instead of probe-guessed shapes. Direct mappings:

| Endpoint | Data source |
|---|---|
| `/storefront/heroes` | `catalog/bundles_index.csv` filtered to `skin=Default*` |
| `/storefront/{playerId}/store` | `catalog/storeoffers_summary.txt` — every row is an offer |
| `/content-service/manifest/{version}` | Each ContentManifest TMap populated from its category's index CSV: Heroes (25 codenames), HeroCosmeticsBundles (bundles_index), Emotes (emotes_index), PlayerTitles (titles_index), StoreOffers (storeoffers), Equipment (items_index + da_index Equipment), Powers (da_index Power), Items (items_index), SlotCosmetics (avatars + sprays + gliders) |
| `/inventory/players/{id}` | Owned-asset subset of the above; the catalog defines the universe of possible SKUs |

## Regenerating this catalog

```powershell
# 1. Generate fresh usmap from the live (elevated) game:
cd "G:\git\Supervive Revival Project\tools\usmapdump"
.\usmapdump.exe extract "SUPERVIVE-Win64-Shipping.exe"

# 2. Batch-dump every category to JSON:
cd "G:\git\Supervive Revival Project\tools\extractor\out"
for cat in titles avatars sprays emotes gliders items dt da bundles ga gp gs ge; do
  bash /tmp/batch_dump.sh /tmp/$cat.txt $cat 80
done

# 3. Rebuild indexes + summary:
go run index_catalog.go
```

Total wall time: ~10 minutes for the full pipeline.
