# R2 Findings: external usmap dumper unlocked SUPERVIVE catalog extraction

This is the harvest summary from running `tools/usmapdump/usmapdump.exe extract` against
the live game and feeding the produced `mappings.usmap` into the existing
`tools/extractor/` CUE4Parse tool. Captured during the 2026-06-26 elevated session.

## Pipeline (now fully working)

```
SUPERVIVE-Win64-Shipping.exe (live, elevated, CIG-protected)
       │
       │  OpenProcess(VM_READ)  — no injection, no anti-cheat interaction
       ▼
tools/usmapdump/usmapdump.exe extract
       │  • frequency histogram of exec ptrs in data regions
       │  • metaclass discovery via UClass-self-class signature
       │  • 5,324 UClass + 6,037 UScriptStruct + 2,226 UEnum enumerated
       │  • 43,802 FProperty walks across all UStructs
       │  • 47,037 UEnum values harvested
       ▼
tools/extractor/mappings.usmap (1.86 MB)
       │
       ▼
tools/extractor/extractor (CUE4Parse, .NET 9)
       │  • mounts 107,123 paks unencrypted
       │  • `dump <path>` produces decoded JSON exports
       ▼
tools/extractor/out/*.json  — actual game data
```

Per-run cost: ~5 minutes from launching `extract` to `mappings.usmap` on disk.

## Layout discoveries (this build — non-standard)

This build has a non-standard +8B pad inside UObjectBase and otherwise uses
case-preserving FName pool format (Len10+probehash) but stores NamePrivate as
a plain 8-byte FName (ComparisonIndex+Number, **no** DisplayIndex slot).

| Offset within UObject | Field |
|---|---|
| `+0x00` | vtable |
| `+0x08` | ObjectFlags(u32) + InternalIndex(u32) |
| `+0x10` | **8 bytes pad** (non-standard) |
| `+0x18` | ClassPrivate (`*UClass`) |
| `+0x20` | NamePrivate (FName, 8 bytes) |
| `+0x28` | OuterPrivate (`*UObject`) |

| Offset within UStruct | Field |
|---|---|
| `+0x38` | UField::Next (`*UField`) |
| `+0x48` | SuperStruct (`*UStruct`) |
| `+0x50` | Children (`*UField` — includes UFunctions; skip for usmap) |
| `+0x58` | **ChildProperties** (`*FField` — the FProperty chain to walk) |

| Offset within FField | Field |
|---|---|
| `+0x00` | vtable |
| `+0x08` | ClassPrivate (`*FFieldClass`) |
| `+0x10` | Owner (`FFieldVariant`) |
| `+0x18` | Next (`*FField`) |
| `+0x20` | NamePrivate |
| `+0x38` | PropertyFlags (u64) |
| `+0x70` | type-specific ref (struct for Struct, class for Object/Class) |
| `+0x80` | embedded inner FField (Array/Set/Optional inner; Map key) |

| Offset within UEnum | Field |
|---|---|
| `+0x48` | Names TArray data pointer |
| `+0x50` | ArrayNum (i32) + ArrayMax (i32) |
| Entry stride | 16 bytes: `[FName ComparisonIndex(4) + Number(4) + int64 Value(8)]` |

## Real catalog data harvested

### Currencies (from `ST_Currencies`)

| Key | Display |
|---|---|
| `Gold` | "Coin" |
| `Gems` | "Prisma" |
| `Tears` | "Shards" |

Plus all-caps variants (`GoldAllCaps`, `GemsAllCaps`, `TearsAllCaps`) and `.Explanation`
suffix variants for tooltips.

### Rarity tiers (from `ST_Rarities`)

| Key | Display |
|---|---|
| `Starter` | "Basic" |
| `Tier0.White` / `tier.0` | "Common" |
| `Tier1.Green` / `tier.1` | "Uncommon" |
| `Tier2.Blue` / `tier.2` | "Rare" |
| `Tier3.Purple` / `tier.3` | "Epic" |
| `Tier4.Gold` / `tier.4` | "Legendary" |
| `Tier5.Red` / `tier.5` | "Exotic" |

Plus `format.N` keys with "{rarity} {object}" templates for composing display names.

### Item-type taxonomy (from `ST_Armory`)

| Key | Display |
|---|---|
| `item.type.power` | "Perks" |
| `item.type.equipment` | "Relics" |
| `item.type.boot` | "Kicks" |
| `item.type.minorEquipment` | "Grips" |
| `item.type.powerUsable` | "Consumables" |

Plus rarity-qualified variants: `item.type.{kind}RarityLabel` = `"{rarity} {kind}"`.

### Full StoreOffer catalog (56 entries)

See `tools/extractor/out/catalog/storeoffers_summary.txt`. Distinct kinds:

**Currency offers** (no `GrantOfferEntitlement: true`):
- Theorycraft Coin tiers: 475, 600, 1000, 2000, 3650, 5350, 11000 (+ `…ExchangeToken` mirrors)
- Vive Points tiers: 10, 20, 30, 40, 50, 90, 100, 120, 150, 240, 270, 480
- The label string in `LongDescription` is what the storefront UI displays, e.g.
  `"950 Theorycraft Coin\r\n+ 50 Bonus"`.

**Cosmetic / bundle offers** (`GrantOfferEntitlement: true`):
hero packs (CyberpunkWukongPack="Great Sage Wukong", DemonessFlexPack="Underworld Shiv",
HuntressGodQueenPack="Eternal Empire Myth", …), themed packs (Winter2025Pack,
MidAutumnPack, BackToSchoolPack), influencer packs (ChinchillaPack="NoWay4u Pack",
RatPack="Caedrel Pack", EmotePack="Tyler1 Emote Pack"), and the megabundles
StarterPack / SupporterPack / CollectorPack (with `LongDescription` rich-text listing
their permanent rewards).

### LokiDataAsset_StoreOffer property shape

```
LokiDataAsset_StoreOffer : LokiDataAsset_BaseCosmetic (12 props)
    PreviewIcon              SoftObjectProperty (UObject)         // TX_* texture
    WideSplashArt            SoftObjectProperty (UObject)         // featured-tile art
    Description              TextProperty                          // short subtitle
    LongDescription          TextProperty                          // main display string
    TextStyleSet             ObjectProperty (DataTable)            // rich-text styles
    GrantOfferEntitlement    BoolProperty                          // true=bundle
    CurrencyGrants           ArrayProperty<...>                    // see note
    AssetGrants              ArrayProperty<...>                    // see note
    Discounts                ArrayProperty<...>
    Previews                 ArrayProperty<...>
    bShowSpecificPreviews    BoolProperty
    bCurrencyOnly            BoolProperty
```

**Note on the Array fields:** the usmap emits `ArrayProperty<Byte>` for these (safer than
guessing the inner StructProperty type and crashing CUE4Parse), so the dumps show the
raw bytes of these arrays — usable for some inspection but not semantically decoded.
The bundle/currency association is recoverable from the asset name and class hierarchy
without needing the array contents.

### Hero codenames (25, internal)

`Alchemist Assault BacklineHealer Beebo BountyHunter BurstCaster Earthtank FarShot
FireFox Flex Freeze Gunner HookGuy Huntress Reaper ResHealer RocketJumper Ronin
ShieldBot Sniper Stalker Storm Succubus Void Wukong` plus the `Shared` directory for
ability/cosmetic helpers.

Each hero's default skin is at:
`Loki/Content/Loki/Characters/Heroes/<Hero>/Cosmetics/Default/BP_<Hero>_DefaultCosmeticsBundle`
inheriting `LokiHeroCosmeticsBundle` (parent of all skin/chroma cosmetics).

## How to consume this for Track B

The storefront/heroes/inventory backend endpoints can now return real data instead of
probe-guessed shapes:

1. **`/storefront/heroes`** — return the 25 hero codenames (already wired). Real
   prices and `GoldText` rewards data is in the bundle `LongDescription` strings.
2. **`/content-service/manifest/{version}`** — the `ContentManifest` struct has these
   TMaps: Heroes, Items, Emotes, PlayerTitles, HeroCosmeticsBundles, StoreOffers,
   SlotCosmetics, Minions, GameAugments, Equipment, Powers (each `TMap<FString,
   ContentServicePrimaryAsset>`). Populate each from the corresponding Loki/Content
   directory — every `BP_*` blueprint becomes one ContentServicePrimaryAsset.
3. **`/storefront/{playerId}/store`** — return entries matching the
   `BP_StoreOffer_*` catalog. SKU = the `_*` suffix (e.g. `vp100`, `tc1000`,
   `CyberpunkWukongPack`).
4. **`/inventory/players/{id}`** — return owned subset, keyed by the same SKU
   namespace.

The `mappings.usmap` is now under version control via `tools/extractor/mappings.usmap`;
rerun `tools/usmapdump/usmapdump.exe extract "SUPERVIVE-Win64-Shipping.exe"` whenever
the game updates to regenerate it.
