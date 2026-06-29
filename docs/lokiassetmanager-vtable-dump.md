# LokiAssetManager vtable dump (128 slots) — 2026-06-28

Captured via new `tools/usmapdump vtdump SUPERVIVE-Win64-Shipping.exe 0x7FF667F5CB78 128`
(absolute address = module_base 0x7FF65F6D0000 + RVA 0x888CB78).

## High-level structure

- **79 unique fn pointers** in 128 slots.
- **83 distinct functions total** (4 are shared "empty virtual" stubs MSVC ICF-folded
  across many UE classes):
  - `0xF7EC20` (31 occurrences) — `virtual void Empty() {}` style
  - `0xF7EB60` (11 occurrences) — `virtual void EmptyXorAlReturn() { xor al; ret }` style
  - `0xB9E1F0` (4 occurrences) — `mov al, 1; ret` (return-true stub)
  - `0xF7EB50` (3 occurrences) — `xor eax, eax; ret` (return-zero stub)
- The 79 unique slots are LokiAssetManager's REAL overrides (plus inherited
  UAssetManager / UObject virtuals it doesn't override).

## Two distinct code regions

Looking at the module-RVA distribution of unique fns:

### Region 1: RVA 0x12Cxxxx–0x12Dxxxx (UAssetManager core virtuals?)

Slots 33–78 mostly cluster here:
- 0x12C5060, 0x12C5680 (typo? 0x12C56A0), 0x12C5A10, 0x12C6AE0, 0x12C6EF0, 0x12C7260,
  0x12C7E80, 0x12C8430, 0x12C8580, 0x12C84D0, 0x12C83F0, 0x12C85B0, 0x12CB060,
  0x12CB110, 0x12CB310, 0x12C68B0, 0x12CC100
- 0x12D1B20, 0x12D1B90, 0x12D3F90

This range looks like one .cpp compilation unit — probably UAssetManager.cpp
(the base UE class).

### Region 2: RVA 0x34Axxxx–0x34Dxxxx (LokiAssetManager.cpp)

**ALL of slots 88–127 fall in this range.** This is almost certainly the
LokiAssetManager.cpp compilation unit.

- 0x34CF9F0 (slot 88), 0x34CF880 (89), 0x34CE490 (90), 0x34CE360 (91)
- 0x34D3D20 (92), 0x34D4D80 (93)
- 0x34AB870 (94)
- 0x34CA500 (95), 0x34C35C0 (96), 0x34B6FC0 (97), 0x34AB430 (98)
- 0x34BE5E0 (99), 0x34BE730 (100), 0x34BFB50 (101), 0x34BFBE0 (102), 0x34BFF20 (103),
  0x34BFF80 (104), 0x34BEC10 (105), 0x34BF2B0 (106), 0x34BEF00 (107), 0x34BECE0 (108),
  0x34BEBB0 (109), 0x34BF320 (110)
- 0x34C0420 (111), 0x34C04F0 (112), 0x34C50E0 (113), 0x34C4FD0 (114), 0x34C51A0 (115)
- 0x34D60E0 (116), 0x34D6060 (117), 0x34D6320 (118)
- 0x34AF2A0 (119), 0x34AF140 (120), 0x34C8760 (121), 0x34C4A90 (122)
- 0x34BB130 (123), 0x34BAFF0 (124), 0x34B7CC0 (125), 0x34AA5D0 (126), 0x34AA740 (127)

Prior recon found `UAssetManager::ScanPrimaryAssetTypesFromConfig` at RVA 0x34D0807.
It is NOT in this vtable dump — meaning it's a **non-virtual helper method** called
internally from a virtual (almost certainly `StartInitialLoading` which we identified
as a likely candidate at slot 47 with its 8-register-save prologue).

## Likely-identifiable virtuals by prologue pattern

(Cross-reference with UE source for definitive identification in next session.)

- **Slot 47** at +0x12CC100: `40 55 53 56 57 41 54 41 55 41 56 41 57 48 8D 6C` — 8 reg
  saves + lea rbp. Massive prologue. **Strong candidate: `StartInitialLoading`** (the
  heavy virtual that drives all init-time asset scanning).
- **Slot 78** at +0x1344E10: `40 55 56 57 41 54 41 55 41 56 41 57 48 81 EC 70` — also
  big. Possible `PostInitialAssetScan` or similar post-init virtual.
- **Slot 95** at +0x34CA500: `4C 8B DC 55 49 8D 6B A8 48 81 EC 50 01 00 00` — MSVC
  r11-frame, 0x150 stack frame. Major LokiAssetManager-specific override.
- **Slot 97** at +0x34B6FC0: `48 89 4C 24 08 55 56 57 41 55 41 56 48 81 EC 80` — also
  large.

## Practical next steps

The goal: **find a way to register additional primary assets at runtime**, bypassing
LokiAssetManager's manifest-only registration limit.

### Approach A — AddDynamicAsset direct call — RVA LANDED 2026-06-28

**`LokiAssetManager::AddDynamicAsset` at module-RVA `+0x34AB870` (vtable slot 94).**

Identification chain (proven repeatable on this build):

1. `usmapdump wstrings SUPERVIVE-Win64-Shipping.exe "AddDynamicAsset" 5`
   → one in-module hit at mod-RVA **+0x7F6F8B0**, UTF-16:
   `"AddDynamicAsset on %s called with conflicting AssetId %s"` (the
   conflict-detected `UE_LOG(LogAssetManager, Warning, ...)` inside
   `UAssetManager::AddDynamicAsset` — vanilla UE5.4 source line).
2. The standard UE `FStaticLogRecord` struct sits 0x20 bytes before the format
   string: log-record at mod-RVA **+0x7F6F890** (format ptr +0x7F6F8B0, file ptr,
   line `0x520` = 1312, verbosity `0x03` = Warning, FName category ptr).
3. `usmapdump xrefstr SUPERVIVE-Win64-Shipping.exe <abs of log-record> 10`
   → exactly ONE LEA targeting the log-record at mod-RVA **+0x34ABCC9**
   (`48 8D 15 C0 3B AC 04` — `lea rdx, [rip+0x04AC3BC0]`).
4. The LEA at +0x34ABCC9 sits inside the function entering at **+0x34AB870** —
   the very slot we already saw at vtable position **94** in the dump above.
   Offset of LEA into function: 0x459.
5. `usmapdump vtdump SUPERVIVE-Win64-Shipping.exe 0x7FF667F5CE68 5` reads
   slots 94..98 directly; slot 94 prologue
   `4C 89 4C 24 20 4C 89 44 24 18 48 89 4C 24 08 55` matches the function entry
   (saves r9/r8/rcx home slots then `push rbp; push rbx; push rsi; push rdi;
   push r12..r15` — 9 reg saves, 0x108 frame, ample state — fits a real virtual
   that walks a hash map and may allocate).

**Body sanity** (first 256 bytes disasmed): standard UE TMap hash lookup pattern
walking `[this+0x478]` (likely `AssetTypeMap`), with `mov ecx, 0x1c8; call <alloc>`
for the not-found branch — `0x1c8` matches `sizeof(FPrimaryAssetTypeData)` in
vanilla UE5.4. **Real implementation, not a stub.** Calling vtable[94] performs
actual registration.

### Singleton finder — LANDED 2026-06-28

`usmapdump findptr SUPERVIVE-Win64-Shipping.exe 0x7FF667F5CB78 20` (abs addr of
the LokiAssetManager UClass vtable at module-base + 0x888CB78) returns exactly
**2 hits** at the steady-state menu:

| Hit | Address (this run)   | [+0x0C] ObjectFlags | Verdict |
|-----|----------------------|---------------------|---------|
| 1   | `0x1CBB033EE90`      | `0x00000000`        | **Real singleton** |
| 2   | `0x1CBF474A120`      | `0x00000031`        | CDO (bit `0x10` = `RF_ClassDefaultObject` set) |

Both objects share `ClassPrivate` at `[+0x18]` = `0x01CBF9CE6280` (the
LokiAssetManager `UClass*`). Singleton filter is therefore:

1. Scan committed `MEM_PRIVATE` for any qword equal to `modBase + 0x888CB78`.
2. For each hit, read `[+0x0C]` (uint32 ObjectFlags) and skip those with bit
   `0x10` set.
3. Take the first remaining match.

In-process heap addresses are NOT stable across runs — the singleton scan must
happen each launch — but the SHAPE of the hits (count = 2, exactly one with
flags=0) is stable. The CLAUDE.md ObjectFlags-at-+0x0C note is correct for this
build; layout summary on the singleton (per peek):

```
+0x00: vtable ptr        (LokiAssetManager UClass vtable = modBase + 0x888CB78)
+0x08: InternalIndex     (uint32, e.g. 0)
+0x0C: ObjectFlags       (uint32; CDO has 0x10 bit set, singleton = 0)
+0x10: another uint32    (e.g. 0xB016 on singleton, 0x8DAA on CDO)
+0x18: ClassPrivate      (UClass* — same value for CDO + real instance)
+0x20: NamePrivate       (FName, 8 bytes)
+0x28: OuterPrivate      (UObject*)
... per-class fields ...
+0x478: AssetTypeMap     (TMap<FName, FPrimaryAssetTypeData> — per disasm)
+0x480: TMap meta uint32
+0x4AC: TMap meta uint32
```

### FName layout — 8 bytes (verified by disasm + CDO peek)

The `usmapdump/objects.go:findMetaclass` block comment hedges toward a 12-byte
case-preserving FName, but the actual layout in this build's UObject
`NamePrivate` and in the function args passed to `AddDynamicAsset` is the
vanilla **8-byte** form. Two independent confirmations:

1. **`AddDynamicAsset` disasm reads exactly 16 bytes for the `FPrimaryAssetId`**:
   ```
   +0x34AB897  mov rbx, qword ptr [rdx]      ; read PrimaryAssetType FName (8 bytes)
   +0x34AB8B6  mov rax, qword ptr [rdx+0x8]  ; read PrimaryAssetName FName (8 bytes)
   +0x34AB8AD  cmp rbx, rcx                  ; rcx=0 — ensure Type FName non-zero
   +0x34AB8BF  cmp rax, rcx                  ; ensure Name FName non-zero
   ```
   If FName were 12 bytes, `FPrimaryAssetId` would be 24 bytes and the second
   FName would start at `[rdx+0xC]`, not `[rdx+0x8]`. The 16-byte read pattern is
   definitive.

2. **CDO NamePrivate decodes cleanly as 8-byte FName**: at `+0x20` of the CDO
   we observed `7B 05 6B 00 00 00 00 00 | B0 3A FE F3 CB 01 00 00`. As an 8-byte
   FName: `ComparisonIndex=0x6B057B, Number=0`. Next field at `+0x28` is
   `OuterPrivate = 0x01CBF3FE3AB0` (a valid heap ptr). If FName were 12 bytes,
   `OuterPrivate` would be at `+0x2C` (misaligned, half inside the FName's
   would-be Number slot) — and `Number` would need to read `0xF3FE3AB0` which is
   implausibly huge.

The Len10+probehash NamePool layout refers to how individual *name entries* are
stored in the pool (10-bit length prefix + probe hash byte), not to the FName
struct itself. Don't conflate the two.

**Sizeof table** for shim arg construction (vanilla layouts apply):

| Type | Size | Layout |
|---|---|---|
| `FName` | 8 | `{ uint32 ComparisonIndex; uint32 Number; }` |
| `FPrimaryAssetId` | 16 | two FNames (PrimaryAssetType + PrimaryAssetName) |
| `FTopLevelAssetPath` | 16 | two FNames (PackageName + AssetName) |
| `FString` (empty, no alloc) | 16 | `{ TCHAR* Data=null; int32 Num=0; int32 Max=0; }` |
| `FSoftObjectPath` | 32 | `{ FTopLevelAssetPath; FString SubPath; }` |
| `TArray<FName>` (empty) | 16 | `{ FName* Data=null; int32 Num=0; int32 Max=0; }` |

### FName construction — open sub-problem before the shim can build

The shim needs to produce FName values for: type names (`Mission`, `MissionPool`,
`Hero`, `HeroCosmeticsBundle`, `StoreOffer`, ...), per-asset names
(`DA_Mission_*`, `FireFox`, `assault`, ...), and package/asset path FNames
(`/Game/Loki/Characters/Heroes/FireFox/...`, `BP_FireFox_Default_CosmeticsBundle`).

Two routes; one must be picked at the start of the shim session:

**Route A — Lookup all needed FName IDs from the live NamePool and bake them
into the shim.** Cleanest because all target names are cooked → already pooled.
But `usmapdump`'s existing `findNameID` (in `objects.go`) walks ONLY block 0
(first 4MB). Most Loki-specific names live in later blocks. **Need to extend
`usmapdump` with a new `nameid <substring> [maxhits]` subcommand** that walks
all 128 blocks and prints `block:offset (= 32-bit ComparisonIndex value)` for
each match. Then bake a constant table into the shim like:

```cpp
constexpr uint32 kNameId_Mission           = 0x......; // from nameid lookup
constexpr uint32 kNameId_DA_Mission_Mortar = 0x......;
// etc., one per name we need
```

ComparisonIndex calc per `objects.go:43` is `off / fnameStride` for block 0
(typically `fnameStride = 2`), then extended for block N as
`(N << 16) | (off / 2)` — confirm encoding by cross-checking against the CDO's
known-good NamePrivate value at scan time. **~1 session for tooling +
exhaustive-id extraction + bake; another session for shim build itself.**

**Route B — Find `FName::FName(const TCHAR*)` in the binary and call it from
the shim.** Faster shim (no per-name bake), but FName ctor RTTI strings are
stripped in this shipping build (verified: `wstrings "FName::FName"` → 0 hits).
Would need to identify it via a TRACE-name, a known constant pattern (the
ePackageHashing seed, the empty-name slot ID, etc.), or by finding `FString`
→ `FName` glue inside a known-anchored function. Higher RE variance.

Pick Route A. The bake table is mechanical and reproducible; Route B's hunt for
an un-anchored ctor is open-ended.

### `usmapdump nameid` — LANDED 2026-06-28

Multi-needle batch lookup across all 128 NamePool blocks. Single pool discovery
(~30s) → many needles scanned in one walk. Exact-match `=` prefix avoids noise
on short common tokens.

```
usmapdump nameid <proc> <needle1>[,<needle2>,...] [maxhits-per-needle]
```

**Validated identification:** "LokiAssetManager" lookup returned id=0x00586413,
which matches EXACTLY the ComparisonIndex observed at the singleton's
`NamePrivate@+0x20`. "Default__LokiAssetManager" returned id=0x006B057B, the
exact value at the CDO's `NamePrivate@+0x20`. Both confirm the encoding
`id = (block << 16) | (offset_in_block / 2)` and confirm our singleton + CDO
identification is correct.

### Baked PrimaryAssetType FName indices (2026-06-28)

All 13 type names registered/known by LokiAssetManager are pooled. One batch
command extracted them all:

```cpp
// All 13 PrimaryAssetType FName ComparisonIndex values, this build/run.
// FName.Number = 0 in every case (these are unsuffixed type names).
constexpr uint32 kType_StoreOffer          = 0x00016257; // block=1   off=0xC4AE
constexpr uint32 kType_Mission             = 0x000162B8; // block=1   off=0xC570
constexpr uint32 kType_MissionPool         = 0x00016F06; // block=1   off=0xDE0C
constexpr uint32 kType_Hero                = 0x0001A568; // block=1   off=0x14AD0
constexpr uint32 kType_HeroCosmeticsBundle = 0x0001A572; // block=1   off=0x14AE4
constexpr uint32 kType_SlotCosmetics       = 0x0001A58C; // block=1   off=0x14B18
constexpr uint32 kType_Equipment           = 0x0001A5D1; // block=1   off=0x14BA2
constexpr uint32 kType_Items               = 0x005E69D6; // block=94  off=0xD3AC
constexpr uint32 kType_Powers              = 0x00627C84; // block=98  off=0xF908
constexpr uint32 kType_GameAugments        = 0x00628068; // block=98  off=0x100D0
constexpr uint32 kType_Minions             = 0x00628078; // block=98  off=0x100F0
constexpr uint32 kType_PlayerTitles        = 0x006280B6; // block=98  off=0x1016C
constexpr uint32 kType_Emotes              = 0x006280C6; // block=98  off=0x1018C
```

Note the clustering: the 11 type names registered by the manifest consumer
(per prior PROBE #2 analysis: StoreOffer, Mission *implicit*, MissionPool
*implicit*, Hero, HeroCosmeticsBundle, SlotCosmetics, Equipment, Items, Powers,
GameAugments, Minions, PlayerTitles, Emotes) live in adjacent NamePool offsets
within blocks 1, 94, 98. Mission and MissionPool ARE pooled (visible in the
batch above) — they just don't have a corresponding map in the manifest's
`ContentServiceContentManifest` struct, which is why the manifest can't carry
them. That asymmetry is the WHOLE reason this route exists.

### Sample per-asset names + package paths — pooled, ready to bake

```
DA_Mission_Mortar01           — example daily mission asset name (need exact form for each of the 16)
DA_MissionPoolDailyChallenge  — the pool name we already patched in AR.bin
/Game/Loki/Characters/Heroes/FireFox/...  — full package paths exist as single FNames
FireFox / Earthtank / ...     — hero codenames (PascalCase, exact case from cooked catalog)
```

Sample batch hits showed:
- `DA_Mission_Mortar01` not yet looked up directly — substring "DA_Mission" returned 7 hero-mission variants. Each of the 16 daily missions needs an exact-name lookup to extract its ComparisonIndex.
- `/Game/Loki/Core/Missions/...` whole paths exist as single FNames (verified for several `BP_MissionObjective_*` and `DA_Mission_*` packages).

### Baked MissionPool PrimaryAssetName FName indices (16/16, validated 2026-06-28)

All 16 `LokiDataAsset_MissionPool` PrimaryAssetNames enumerated from
`tools/extractor/out/catalog/da_index.csv` and batch-looked-up in one
`nameid` call. **16/16 hits, all `kName_*` constants are ready to bake.**
(One pool name — `DA_MissionPoolTutorialMaps` — appears in two NamePool slots;
either id resolves to the same string, pick the first.)

```cpp
// All 16 LokiDataAsset_MissionPool PrimaryAssetName FName ComparisonIndex values.
// PrimaryAssetType for every entry = kType_MissionPool (0x00016F06).
constexpr uint32 kName_DA_MissionPoolDailyEasy_Planbee        = 0x000646D1;
constexpr uint32 kName_DA_MissionPoolTutorialMaps             = 0x00117A37;
constexpr uint32 kName_DA_MissionPoolWeekly_Planbee           = 0x00137B5D;
constexpr uint32 kName_DA_MissionPoolDailyChallenge           = 0x0013D7DA;
constexpr uint32 kName_DA_MissionPool_Tournament              = 0x00148033;
constexpr uint32 kName_DA_MissionPoolDailyPCB_Armory          = 0x00148041;
constexpr uint32 kName_DA_MissionPoolOnboardingPlanbee        = 0x001F4BD2;
constexpr uint32 kName_DA_MissionPoolOnboarding               = 0x0025292C;
constexpr uint32 kName_DA_MissionPoolWeekly                   = 0x0025D9CE;
constexpr uint32 kName_DA_MissionPoolDailyEasy                = 0x0029D2DA;
constexpr uint32 kName_DA_MissionPoolWeeklyChallenge          = 0x002EFC99;
constexpr uint32 kName_DA_MissionPoolWeeklyChallenge_Planbee  = 0x002F52FC;
constexpr uint32 kName_DA_MissionPoolDailyChallenge_Planbee   = 0x0034A90E;
constexpr uint32 kName_DA_MissionPoolHunterMissions           = 0x0047A890;
constexpr uint32 kName_DA_MissionPoolArmoryOnboarding         = 0x004A410E;
constexpr uint32 kName_DA_MissionPoolDailyPCB                 = 0x0056032C;
```

This single PrimaryAssetType is sufficient for a SMOKE-TEST shim: register all
16 mission pools, observe Loki.log for `ChangeBundleStateForPrimaryAssets`
activity against `MissionPool:DA_MissionPool*` IDs (the missing piece that
PROBE #3 confirmed as the trigger for grid population). If the smoke test
shows registration + warnings clear but the Missions modal still renders no
pools, the downstream UI kill criterion is real and we pivot to RE'ing the
modal widget. If pools appear in the modal, the same pattern scales mechanically
to the 105 mission assets + the 25 hero assets + the 25 cosmetics bundles +
the store offers etc.

### Smoke test executed 2026-06-28 evening — 16/16 registrations succeeded (twice)

`tools/sigbypass-mod/registration_shim.cpp` built, injected (live process via
`tools/inject mmap`), ran end-to-end twice in succession on the same running
game. Marker file at `docs/registration-shim-marker.txt`.

Per-run sequence (both identical):
1. DllMain attached at remote heap base, worker spawned (no DllMain blocking).
2. GGameThreadId resolved on loop=1 (slot at +0x9D49158 confirmed stable).
3. 10s grace + singleton scan.
4. Scan filter results: ~19,790 regions, 5-6 vt-ptr hits, 1 self-skip (our DLL),
   2-3 badClassSkips (stack-region coincidental matches), 1 CDO, 1 singleton.
   Picked singleton = **0x1CBB033EE90** (exactly matching recon).
5. APC queued on game thread tid=36396; fires within seconds on next alertable
   wait (Vivox/UI tick).
6. APC body resolved `vtable[94] = AddDynamicAsset @ 0x7FF662B7B870`
   (= module base 0x7FF65F6D0000 + RVA 0x34AB870 — exactly the value derived
   from string-anchor → log-record → xrefstr in recon).
7. All 16 MissionPool registrations called sequentially; each returned cleanly.
   Marker logged `[apc] DONE: 16 / 16 registrations completed`.

**Self-match filter was critical.** First attempt (without filter) picked a
spurious match in a low-address stack region (0x000000C8...) because our DLL has
the LokiAssetManager vtable address baked in as a constant, AND nearby stack
qwords coincidentally match. The re-validation step in the APC body caught it
(singleton ptr no longer readable → graceful abort, no crash). Filters added:
- Skip qwords inside our own DLL's image range (captured in `DllMain` from
  `hModule` + reading `OptionalHeader.SizeOfImage` at +0x50 of NT headers).
- `[+0x18]` (ClassPrivate) must be 8-byte-aligned heap-range pointer AND must
  be a readable page (PageReadable check).
- These together reduced "5 hits" → "1 singleton + 1 CDO" — matches the
  `findptr` recon result exactly.

**Game state after 2 successful runs:** alive, ~5.85 GB working set (slightly
down from peak — likely GC), Loki.log shows zero NEW `LogAssetManager`
warnings (the only 2 in the log predate injection by 38 minutes, from the
initial SetHero("") path). Zero `ChangeBundleStateForPrimaryAssets` activity
for `MissionPool:*` IDs — registration is complete BUT NOT YET TRIGGERED by
any UI/code path.

**Vanilla UE conflict-warning is silent on identical re-registration.** UE
source's `AddDynamicAsset` only emits the
`"AddDynamicAsset on %s called with conflicting AssetId %s"` warning when the
NEW path differs from the EXISTING path. Run 2 used the same paths as run 1,
so the absence of warnings is consistent with both: "registrations landed in
run 1 and were re-found by exact match in run 2" AND "registrations did not
land in run 1 and run 2 silently created fresh entries". Confirming which
requires either: (a) a third run with a DELIBERATELY DIFFERENT path for at
least one ID (would force conflict warning IF entries persisted), OR (b) a UI
test of the Missions modal — opening it and observing whether mission pools
appear.

### Next decision point — UI test or further programmatic validation

The path-conflict re-run is purely programmatic + definitive: change one byte
of one PackageName in the shim, rebuild, re-inject. Conflict warning fires →
proven persistence. No warning → either run-1 calls were no-ops or our second
run's path-FName-id pointed at the same string.

The UI test is the actual goal: open the Missions modal and see if anything
appears. If yes, the smoke test scales to the 105 missions / 25 heroes / 25
cosmetics bundles + the route is open. If no, the downstream UI kill criterion
has fired (UI enumerates via AR query, not RegisteredPrimaryAssets) and we
pivot to RE'ing `WBP_UI_MissionModal_C` data binding OR the in-memory
FAssetRegistry patch route (Approach C from this doc).

### Concrete next-session work order for shim build

1. **Enumerate exact asset names per type** via `tools/extractor` catalog. We
   already have `tools/extractor/out/catalog/` containing per-bundle JSON with
   asset paths. For each of the 16 missions / 4 mission pools / 25 heroes / 25
   cosmetics bundles, extract the exact PrimaryAssetName + PackageName +
   AssetName + AssetPath strings.
2. **Single batch `nameid` lookup** for all extracted strings — at this scale
   (~150-200 needles) one pool walk finishes in ~30s + per-needle scan time.
   Bake the resulting `kName_*` constants into the shim.
3. **Build `tools/sigbypass-mod/registration_shim.cpp`** modeled on
   `mount_shim.cpp`'s worker+APC framework. Singleton finder per spec above.
   Loop body calls `vtable[94](singleton, &id, &path, &bundles)` per asset
   with structs constructed from the baked FName indices.
4. **Verify by relaunching + signing in + opening Missions modal.** Watch
   marker file + Loki.log for `Invalid Primary Asset Type/Id` warnings clearing
   + `ChangeBundleStateForPrimaryAssets` activity for our registered IDs.
5. **If warnings clear but UI is still empty**, downstream kill criterion has
   fired and route closes at UI layer (see below).

### Shim plan (ready to build — next session)

Extend `tools/sigbypass-mod/mount_shim.cpp` framework into a new
`registration_shim.cpp` that:

1. Waits for `GGameThreadId` non-zero (proven mechanism, slot at +0x9D49158),
   then sleeps a few seconds to let LokiAssetManager finish init.
2. Singleton finder: scans `MEM_PRIVATE` for `qword == modBase + 0x888CB78`
   then filters by `*(uint32*)(p + 0x0C) & 0x10 == 0`. Picks first match.
3. Constructs the three argument structs per registration:
   - `FPrimaryAssetId { FName Type; FName Name; }` — 16 bytes.
   - `FSoftObjectPath { FTopLevelAssetPath{FName PackageName; FName AssetName}; FString SubPath; }`
     — 24 bytes (16 for the two FNames + 16 for the empty FString).
   - `TArray<FName> Bundles { void* Data; int32 Num; int32 Max; }` — 16 bytes.
   FNames must be EXISTING NamePool indices (asset names are already pooled
   because they're cooked into AR.bin and the manifest consumer). Lookup via
   `usmapdump names` + per-name index extraction; bake the table into the shim
   at build time. Avoids calling `FName::FName(TCHAR*)` (which would itself need
   an RVA we don't have).
4. APC-queues a callback on the game thread that loops over the registration
   table and invokes `vtable[94](singleton, &id, &path, &bundles)` for each
   entry.
5. Marker logging per-call so we see exactly which ID succeeded vs. crashed.

### Kill criterion to bear in mind

Per the MISSION PROBE #2 analysis at the bottom of `docs/hero-roster-attempts.md`,
even a successful `AddDynamicAsset` for every missing primary asset may not
populate the UI. The Missions modal / hero grid / store / cosmetics widgets may
enumerate via a DIFFERENT path (direct AssetRegistry query filtered by AssetClass)
that doesn't read `RegisteredPrimaryAssets`. If the shim runs cleanly + the
`Invalid Primary Asset Type/Id` warnings disappear + new `ChangeBundleState`
activity appears for the registered IDs, but the UI still renders empty, the
route closes at the UI layer and the remaining options are: (a) RE the
`WBP_UI_*_C` blueprint widgets' data sources; (b) in-memory FAssetRegistry patch
(Approach C).

**Approach B — Patch LokiAssetManager vtable to call UAssetManager base impls.**
For each slot in 88–127 that overrides a UAssetManager virtual:
1. Identify the equivalent base UAssetManager fn via slot-by-slot comparison
   (find a UAssetManager-only vtable in heap — there might be one if any UE
   editor/runtime utility class instantiates the base directly).
2. Overwrite the override slot with the base fn pointer.

Result: scan-related virtuals would fall through to UE's standard impls,
including `ScanPrimaryAssetTypesFromConfig`. This sidesteps the "find
AddDynamicAsset" RE work but trades it for "find a base UAssetManager vtable
to copy from". Harder unless we can synthesize one.

**Approach C — In-memory FAssetRegistry patch (alternative route).** Skip
LokiAssetManager entirely. Find the loaded FAssetRegistry singleton + patch
its FAssetData entries directly in heap. Anchors at +0x79D5DF0 and +0x79D5B40.
Doesn't depend on LokiAssetManager doing anything. May still hit the deeper
kill criterion (whether the UI actually QUERIES the modified entries).

## Tooling created this session

- `tools/usmapdump vtdump <proc> <hexVtableAddr> [numSlots]` — slot-by-slot
  vtable dump with shared-vs-unique annotation + first-16-byte prologue. Useful
  for any UE class identification.
- `tools/usmapdump vtslot <proc> <slot> <hexFnAddr> [maxhits]` — find any
  vtable in committed memory whose specified slot holds a target function.
  Useful for detecting MSVC ICF folding across class hierarchies.
