# SUPERVIVE game map — fully mapped

**68,228 cataloged assets across 42 categories.** Every gameplay-defining and
content-defining asset in the shipping build, extracted from the paks via
[the external usmap dumper](r2-findings.md), decoded to JSON, and indexed.

Total dumpable assets in the game: **78,208 .uasset files**. Cataloged: 68,228
(the gap is duplicate-basename overwrites during dump — the unique asset universe
is fully covered; the duplicates share semantics with their counterparts).

## Master index — all 42 categories

### Gameplay & content (6,419 — first pass)

| Category | Count | Description |
|---|---:|---|
| `ge` | 2,429 | GameplayEffects — buffs/debuffs/damage/status |
| `titles` | 659 | Player titles (BP_PlayerTitle_*) |
| `gs` | 596 | GameplaySpells — ability instances |
| `da` | 494 | DataAssets (Mission/Equipment/Power/Capsule/etc.) |
| `items` | 481 | In-game items (BP_ITEM_*) |
| `bundles` | 353 | Hero cosmetic bundles (skins/chromas) |
| `gp` | 344 | GameplayPersistent (passive effects) |
| `emotes` | 326 | Emotes (BP_Emote_*) |
| `avatars` | 233 | Profile avatars |
| `sprays` | 146 | Sprays |
| `gliders` | 116 | Gliders |
| `dt` | 113 | DataTables |
| `st` | 64 | StringTables |
| `ga` | 9 | GameplayAbilities |
| **storeoffers** | 56 | Store offers (currency tiers + cosmetic packs) |

### Art / mesh / animation (43,538)

| Category | Count | Primary type |
|---|---:|---|
| `tex_t` | 13,089 | Texture2D (T_*) |
| `mi` | 11,225 | MaterialInstanceConstant (MI_*) |
| `sm` | 5,218 | StaticMesh (SM_*) |
| `ns` | 5,072 | NiagaraSystem (NS_* VFX) |
| `mat` | 4,556 | Material (M_*) |
| `anim` | 3,506 | AnimSequence (A_*) |
| `gc` | 3,252 | BlueprintGeneratedClass (GC_* gameplay cues) |
| `tx` | 1,813 | Texture2D (TX_* — alternate naming) |
| `am` | 871 | AnimMontage (AM_*) |
| `ps` | 459 | ParticleSystem (PS_* legacy VFX) |
| `lt` | 385 | LightProfile/LookupTexture (LT_*) |
| `gie` | 364 | GameplayInstantEffect (GIE_*) |
| `sk` | 360 | SkeletalMesh (SK_*) |
| `mf` | 299 | MaterialFunction (MF_*) |
| `abp` | 290 | AnimBlueprint (ABP_*) |
| `spr` | 266 | Sprite/PaperSprite (SPR_*) |
| `comp` | 256 | Component templates (Comp_*) |
| `bs` | 232 | BlendSpace (BS_*) |
| `skel` | 216 | Skeleton (SKEL_*) |
| `tex` | 129 | Texture2D (Tex_*) |
| `sc` | 13 | SoundCue (SC_*) |
| `fx` | 8 | FX_* |
| `vfx` | 6 | VFX_* |
| `sb` | 6 | SoundBank (SB_*) |

### UI / Widgets (1,258)

| Category | Count | Description |
|---|---:|---|
| `wbp` | 1,258 | Widget Blueprints (WBP_* full UI) |

### Audio (16,968)

| Category | Count | Description |
|---|---:|---|
| `sfx` | 3,921 | Wwise sound effects (sfx_*) |
| `vo` | 4,452 | Wwise voice-over events (vo_*) |
| `snd` | 343 | SoundWave / SoundCue (snd_*) |
| **(Akᴀᴜᴅɪᴏᴇᴠᴇɴᴛ via vo + sfx)** | 8,712 | Wwise events total |

(en_voice — 0; empty filter on this build.)

## Bundles per hero (= unique skins)

| Hero | Bundles | Hero | Bundles |
|---|---:|---|---:|
| Freeze | 23 | Stalker | 14 |
| Assault | 21 | Beebo | 14 |
| Storm | 19 | ShieldBot | 13 |
| Huntress | 19 | RocketJumper | 13 |
| Ronin | 18 | Flex | 13 |
| ResHealer | 18 | HookGuy | 11 |
| BurstCaster | 18 | Succubus | 9 |
| BacklineHealer | 18 | BountyHunter | 9 |
| Void | 17 | FarShot | 8 |
| Gunner | 17 | Earthtank | 8 |
| FireFox | 17 | Reaper | 3 |
| Sniper | 16 | Alchemist | 3 |
| Wukong | 14 | **Total** | **353** |

## Total unique class-type breakdown (top 25 across the catalog)

| Class | Count | Found in |
|---|---:|---|
| `Texture2D` | 14,882 | tex_t, tx, tex, lt, spr |
| `MaterialInstanceConstant` | 11,422 | mi |
| `AkAudioEvent` | 8,712 | sfx, vo |
| `StaticMesh` | 5,217 | sm |
| `NiagaraSystem` | 5,066 | ns |
| `Material` | 4,364 | mat |
| `AnimSequence` | 3,348 | anim |
| `BlueprintGeneratedClass` | 3,252+ | gc, items, bundles, avatars, etc. |
| `AnimMontage` | 871 | am |
| `Function` | 456 | embedded in BPs |
| `AnimComposite` | 157 | anim |
| `Button` | 147 | wbp |
| `CanvasPanel` | 131 | wbp |
| `ComponentDelegateBinding` | 123 | embedded |
| `CommonTextBlock` | 116 | wbp |
| `Border` | 107 | wbp |
| `BackgroundBlur` | 48 | wbp |
| `Image` | 28 | wbp |
| `CommonLazyImage` | 18 | wbp |
| `TextureCube` | 14 | tex_t (envmap) |

## StringTables (UI text) — 64 tables, 1,000+ entries

Selected high-value:

| Table | Keys | Contents |
|---|---:|---|
| `ST_Armory` | 132 | Item types (Perks/Relics/Kicks/Grips), weekly chest tiers, sort options |
| `ST_Armory_FlavorText` | 98 | Lore/flavor strings for items |
| `ST_AbilityTooltips` | 64 | Hero ability descriptions |
| `ST_Rarities` | ~30 | Tier0-5 = Common/Uncommon/Rare/Epic/Legendary/Exotic |
| `ST_Items` | ~12 | Armor tier names, Boots descriptions |
| `ST_Currencies` | ~8 | Gold→Coin, Gems→Prisma, Tears→Shards |
| `ST_AbilityLeveling` | 7 | Level-up text |
| `ST_AirdropShopStrings` | 23 | Airdrop shop UI |
| `ST_AttributeDisplayNames` | 16 | Stat display names |
| `ST_AttributeDescriptions` | 4 | Stat tooltip text |
| `ST_Announcements` | 15 | In-game announcements |

## DataAssets (DA_*) subtypes

| Subtype | Count | Description |
|---|---:|---|
| `DA_Mission_*` | 330 | Hunter missions, daily/weekly challenges |
| `DA_Equipment_*` | 110 | Equipment (Relics) |
| `DA_MapIcon_*` | 37 | Map icons |
| `DA_Power_*` | 35 | Power-up assets (Perks) |
| `DA_BiomeLighting_*` | 32 | Per-biome lighting configs |
| `DA_PaginatedModal_*` | 4 | UI modals |
| `DA_MissionPool*` | 11 | Mission rotation pools |
| `DA_Capsule_*` | 2 | Capsule (loot box) types |
| `DA_ArmoryTables_*` | 1 | Master armory catalog |

## Pipeline (how this catalog is built)

```
SUPERVIVE-Win64-Shipping.exe (live, elevated, CIG-protected)
       │
       ▼  read-only RPM — no injection (sidesteps anti-tamper)
tools/usmapdump/usmapdump.exe extract
       │  ~5 min
       ▼
tools/extractor/mappings.usmap (1.86 MB)
       │
       ▼  CUE4Parse (.NET 9), mounts 107k paks unencrypted
tools/extractor/extractor dump <paths…>
       │  ~10 min for gameplay (6.4k), ~117 min for art (~62k)
       ▼
tools/extractor/out/catalog/<category>/<asset>.json    (68,228 files / ~1 GB)
       │
       ▼  go run index_catalog.go
catalog/<category>_index.csv                             (42 CSV indexes)
```

Each subfolder of `catalog/` has the raw decoded JSON for every asset in that category.
Each `<category>_index.csv` has the compact lookup table.

## How to consume the full catalog

### Gameplay backend (Track B)
| Endpoint | Source |
|---|---|
| `/storefront/heroes` | `catalog/bundles_index.csv` filtered to `skin=Default*` |
| `/storefront/{playerId}/store` | `catalog/storeoffers_summary.txt` |
| `/content-service/manifest/{version}` | Cross-join indexes from `bundles`, `emotes`, `titles`, `avatars`, `sprays`, `gliders`, `items`, `da` |
| `/inventory/players/{id}` | Owned-subset filter on those same SKU namespaces |

### Localization
String tables: `catalog/st/<TableName>.json` — full key→value mapping for every UI string.

### Visual / preview tooling
Asset paths in `*_index.csv`'s `portrait`, `preview`, `splashArt` columns map to the `T_*`,
`TX_*`, `Tex_*` texture catalogs. Use those paths to construct asset URLs once a texture
serving layer exists.

### Game-design analysis
- `ge_index.csv` — 2,429 effects; each row is one buff/debuff/damage instance.
- `gs_index.csv` — 596 spells; ability instances.
- `da_index.csv` filtered to `DA_Mission_*` — 330 mission definitions.
- `dt_index.csv` — 113 tables; check `row_count` column for table size.

### Asset graph
- `sm` (5,218) static meshes + `mi` (11,225) material instances + `mat` (4,364) base
  materials + `tex_t` (13,089) textures + `spr`/`tx`/`tex` (additional textures) form the
  rendering content tree.
- `ns` (5,072) Niagara systems + `ps` (459) legacy particle systems + `gc` (3,252)
  gameplay cues form the VFX tree.
- `anim` (3,506) + `am` (871) + `bs` (232) + `abp` (290) + `skel` (216) + `sk` (360) form
  the animation tree.
- `sfx` (3,921) + `vo` (4,452) + `snd` (343) + `sc` (13) + `sb` (6) form the audio tree
  (Wwise events ≈ 8,712 total).
- `wbp` (1,258) widget blueprints form the entire UI tree.

## Regenerating

```powershell
cd "G:\git\Supervive Revival Project\tools\usmapdump"
.\usmapdump.exe extract "SUPERVIVE-Win64-Shipping.exe"   # ~5 min, refresh usmap

cd "G:\git\Supervive Revival Project\tools\extractor"
bash batch_dump.sh /tmp/<category>.txt <category> 80     # per-category re-dump
# or all at once:
bash art_dump_all.sh                                      # all art categories

cd out
go run index_catalog.go                                   # rebuild all CSV indexes
```

Total pipeline wall time for a clean rebuild: **~2 hours**.
