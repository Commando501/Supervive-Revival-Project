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

### External AssetTypeMap walk — persistence PROVEN, hypothesis 2 falsified (2026-06-28 late)

After re-injecting the safe shim against the fresh launch (singleton @
0x16AF849E8C0), externally read the TMap at `[singleton + 0x478]` via
`usmapdump peek`. **Persistence is real** — and the deeper finding is even
more important: the blocker is NOT type-or-name registration.

**Outer AssetTypeMap header at `[singleton + 0x478]` (0x16AF849ED38):**

```
+0x00 (data ptr): 0x16B64E195B0   (TArray.Data — TSparseArray of pair elements)
+0x08 (Num):      0x0000001E       (30 entries — see breakdown below)
+0x0C (Max):      0x0000001F       (31 capacity)
+0x40 (hash ptr): 0x16B628CEE00    (hash bucket array)
+0x48 (mask):     0x00000020       (32 buckets, mask = 0x1F)
```

Element stride **32 bytes**, key (FName) at element +0x00, value ptr (to
0x1c8-byte `FPrimaryAssetTypeData`) at element +0x08.

**Decoded 30 entries** include keys that confirm hypothesis assumptions:

| Idx | Key (decoded)        | FName id    | Notes |
|-----|----------------------|-------------|-------|
| 2   | `Hero`               | 0x0001A568  | manifest type |
| 6   | **`Mission`**        | 0x000162B8  | **TYPE REGISTERED AT STARTUP** — not by our shim |
| 7   | `HeroCosmeticsBundle`| 0x0001A572  | manifest type |
| 11  | **`MissionPool`**    | 0x00016F06  | the one we (re-)called AddDynamicAsset on |
| ... | (other 26 types)     |             | Loki types beyond the 11 manifest-mapped |

**This falsifies the long-standing assumption that Mission and MissionPool
have NO registration path** (per Attempts 3-4 in
[docs/hero-roster-attempts.md](hero-roster-attempts.md)). Both types ARE
registered in AssetTypeMap at startup — by Loki code that runs independent of
the manifest consumer. The "Invalid Primary Asset Id MissionPool:..." warning
we saw in Mission Probe #3 was because the probe injected via the wrong
channel (Powers map), not because the type was missing.

**Inner MissionPool FPrimaryAssetTypeData at value ptr 0x16B62968000:**

```
+0x00 (Type key):       0x00016F06 (MissionPool) ✓
+0x178 (AssetMap data): 0x16AFC503620
+0x180 (AssetMap.Num):  16   ← our 16 AddDynamicAsset calls landed here
+0x184 (AssetMap.Max):  17
```

The 16 sub-entries are present. The shim's write path works end-to-end — the
function executes, the TMap accepts the writes, the count rises from
whatever-it-was to 16+. (Stale FName indices in this run mean the keys decode
to garbage strings, but the count matches our call count.)

### Verdict — three earlier hypotheses now settled

1. **UI kill criterion is real**. ✓ Most likely the right diagnosis. The
   modal does NOT enumerate via RegisteredPrimaryAssets — even with 30 types
   registered (including Mission + MissionPool) and our 16 explicit entries,
   the modal renders empty.
2. **Registration didn't persist** — **FALSIFIED**. Entries are in the TMap.
   AddDynamicAsset works.
3. **Registered but assets not loaded (need ChangeBundleState/AsyncLoad)** —
   still possible, would require triggering a load to test. But hypothesis 1
   is now the parsimonious explanation: if the UI doesn't even acknowledge
   the existing 30 registered types (Hero, HeroCosmeticsBundle, etc. — for
   which actual cooked assets exist), it's not reading from this TMap at all.

### UI data-source RE 2026-06-28 (very late) — UMissionsModel + local init

Drilled into the Missions modal's compiled-blueprint data. Findings:

**Widget chain identified:**
- `WBP_UI_MissionModal_C` (the modal) — opens, async-loads a `LokiDataAsset_Season`,
  iterates the Season's `MissionPools` array (a `TArray<TSubclassOf<LokiDataAsset_MissionPool>>`),
  async-loads each pool, creates a `WBP_UI_MissionModalCategoryButton_C` +
  `WBP_UI_MissionModalCategory_C` per pool.
- `WBP_UI_MissionModalCategory_C` (per-pool category) — calls
  **`GetMissionsModel()`** + `GetProgressionManager()` + `BindToMissions(...)`.
  This is the actual data binding.

**Native class identified:** `UMissionsModel` — owns the data. Confirmed via
wstrings hits:
- `"UMissionsModel"`
- `"UMissionsModel::OnMissionAssetLoaded"` — per-asset async-load callback
- `"UMissionsModel::OnPSMissionsUpdated"` — populated when external mission
  data arrives (likely from a parent subsystem broadcasting on player state
  changes)

**Class that owns MissionPoolIDs identified** (one class — same metadata
cluster):
- `MissionPoolIDs` (member, `TArray<FPrimaryAssetId>` — the master list of pools)
- `GetMissionPoolFromPrimaryAssetId` (lookup)
- `GetAllClaimableMissionRewardsForPools` (rewards iteration)
- `OnLocalMissionsInitialized` + `OnLocalXPInitialized` (init-complete delegates)

**Critical assumption REWRITE** (from prior recon at
`docs/trackb-notes.md` "Mission flow" section):
> "Missions are UE Primary Assets the client loads LOCALLY, not backend list
>  data. **There is no missions-list endpoint.**"

This rules out the backend approach entirely. The blocker is **local init
populating `MissionPoolIDs`** — which is empty for some reason.

**Cooked content gap discovered:** The catalog has only 7 `LokiDataAsset_*`
classes — `Mission`, `MissionPool`, `ArmoryTables`, `Capsule`,
`ArmoryOnboardingCapsule`, `Equipment`, `Power`. **No `LokiDataAsset_Season`
data assets are cooked**. So the modal's "async-load a Season → get its
MissionPools" path is unsatisfiable. The Season class exists in `/Script/Loki`
but no concrete `DA_Season*.uasset` exists to load.

If the modal can't load any Season (no concrete asset to load), Construct's
load-Season-then-iterate path fails silently → zero category buttons get
created → modal is empty.

### Concrete next-session focus

Two routes both worth pursuing in parallel:

1. **Find what populates `MissionPoolIDs`.** Either:
   - Find the function that calls `MissionPoolIDs.Add(...)` — callxref any
     pattern that mutates a TArray<FPrimaryAssetId> in the LokiMissionsSubsystem
     class. Substantial.
   - Or find what fires `OnLocalMissionsInitialized` — that's the "all
     populated" signal. Find its `Broadcast()` call site → the function
     that calls Broadcast IS the initializer.
2. **Synthesize a `LokiDataAsset_Season` at runtime** with our 16 MissionPool
   classes in its MissionPools array. Either:
   - Add an in-memory FAssetData entry for a fake Season asset, then register
     it via AddDynamicAsset → modal might load it → iterate MissionPools →
     populate UMissionsModel.
   - Or hook the modal's Season-load-completion delegate to inject our pool
     list directly.

Route 1 is more diagnostic (tells us why it's empty); route 2 is more
constructive (fixes it by feeding the right shape).

### Route A recon 2026-06-28 (latest) — class ownership identified

Walked the reflection metadata around `MissionPoolIDs` /
`OnLocalMissionsInitialized`. Owning class identified:

**`ALokiPlayerState`** — the player's local state class (UE actor, A-prefix).
- Static helper: **`GetLocalLokiPlayerState`** (function — discoverable by
  the same name in the binary).
- Members include: `Wallet`, `HeroAffiliatedObject`, `StatsObject`,
  `PawnComponent`, `bNeedsInitialInventory`, `bNeedsInitialCharacterEffects`,
  `OnPlayerUIDataChanged`, `OnAnyUIEvent`, **`OnLocalStatsInitialized`**,
  **`OnLocalMissionsInitialized`**, **`OnLocalXPInitialized`** (sibling local-
  init delegates), `Knocker`, `GameEvent_GameReady_Controller`, etc. The
  property cluster appears at module addr 0x16AAC0B6C00..D00 in this run
  (heap; ASLR'd) — searchable by any of the above strings + walking the
  cluster.

**`UMissionsModel`** — separate object owned/referenced by PlayerState.
- Source file confirmed: `...issions\MissionsModel.cpp` (UE C++).
- Owning class has a member named **`MissionsModel`** (property), a factory
  **`CreateMissionsModel`**, and a getter **`GetMissionsModel`** (returns
  `UMissionsModel*`). The modal category widget's `CallFunc_GetMissionsModel`
  resolves to this.
- Methods: `UMissionsModel::OnMissionAssetLoaded` (async-load completion),
  `UMissionsModel::OnPSMissionsUpdated` (Platform-Service mission data
  ingest — name strongly implies server-pushed data).

**Data flow inference** (best current model):
1. ALokiPlayerState init creates UMissionsModel via `CreateMissionsModel`.
2. ALokiPlayerState's local-asset init populates `MissionPoolIDs`
   (`TArray<FPrimaryAssetId>` — the master pool list). When complete, it
   fires `OnLocalMissionsInitialized.Broadcast()`.
3. Server-side mission data (PSMissions) eventually arrives → routed to
   `UMissionsModel::OnPSMissionsUpdated` → populates per-mission progress.
4. Modal opens → calls `GetMissionsModel()` → reads UMissionsModel state.

If step 2 silently fails (e.g., the local-asset enumeration finds zero
MissionPool primary assets via some Loki-specific scan path that we haven't
identified yet), `MissionPoolIDs` stays empty → `OnLocalMissionsInitialized`
either never fires or fires with zero pools → modal renders empty.

### The one concrete next step

**Locate the function that calls `OnLocalMissionsInitialized.Broadcast()`** —
this IS the local-init completion point. Once we know it, we can:
- Disassemble it to see what feeds `MissionPoolIDs` (= a config read? an AR
  scan? a hardcoded asset list?).
- Decide whether the right fix is config-side, AR-side, or shim-side.

Path: find `OnLocalMissionsInitialized` as a UPROPERTY name in the
ALokiPlayerState reflection metadata → derive the property offset within
the class → search code for `lea rcx, [this + <offset>]; call <Broadcast>`
to find broadcast call sites. Alternative: find the static
`GetLocalLokiPlayerState` (we have its name as a string anchor) → walk
calls from there to functions that touch the same offset.

### Route A2 — UMissionsModel external read 2026-06-28 (definitive)

Pivoted from the heavy broadcast-call-site hunt to a lightweight external
read. Used the same FName→CDO→vtable→findptr pattern from prior recon.

**ALokiPlayerState instance scan:**
- CDO @ 0x16AC8BCE6D0 (flags 0x31). Vtable @ +0x8A2D718.
- `findptr` returns ONE additional hit @ 0x16B8AD46670 — but its
  `ClassPrivate@+0x18` is 0x1557B (not a heap pointer) → false positive.
- **No live ALokiPlayerState instance exists at the menu.** PlayerState
  only spawns in active matches, so MissionPoolIDs on PlayerState never
  populates in the menu. This rewrites the prior hypothesis that
  ALokiPlayerState owns the menu's mission data — it doesn't.

**UMissionsModel instance scan:**
- CDO @ 0x16AC8BFA600 (flags 0x31). Vtable @ +0x88ADED0.
- 2 LIVE instances: 0x16B77E50100 + 0x16B7C654A80 (flags 0x00 — UE5.4 default-
  spawn pattern; ClassPrivate is a valid heap ptr → validated).
- Reading instance 0x16B77E50100 (384 bytes): **the entire body is zeros**
  except for default-empty TSparseArray/TMap meta values (HashSize=0x80,
  FirstFreeIndex=-1) at regularly spaced offsets (+0x15C, +0x1AC, +0x1F0,
  ...).

**Verdict (Route A2 result):** UMissionsModel exists in memory but **all of
its data structures are empty** — no MissionPoolIDs, no MissionPoolAssets,
no per-mission state. The model was constructed but never populated. The
modal correctly calls `GetMissionsModel()` and gets back this empty model,
which is why the modal renders zero categories.

**Outer chain decoded:**
- UMissionsModel.OuterPrivate@+0x28 = UEndOfGameModel instance (decoded via
  CDO scan of the Outer's vtable, found "Default__EndOfGameModel" at
  block 107 offset 0x5A in NamePool).
- UEndOfGameModel.OuterPrivate = another transient (likely a per-LocalPlayer
  or per-GameInstance summary holder; vtable shared by 5 CDOs suggests it
  may itself be a UClass instance / metaclass).

The "EndOfGame" naming suggests UMissionsModel was originally designed as
part of the end-of-match summary and reused for the menu Missions modal.
Either way, it's a real long-lived UObject, just unfilled.

**Next pursuit (route picked):** the EMPTY model is the smoking gun. The
relevant question is no longer "does init run" but "does init COMPLETE
WITHOUT POPULATING". Two follow-ups:

1. **Find the function that creates UMissionsModel** (via `CreateMissionsModel`
   string anchor we already have). Its caller chain reveals which subsystem/
   class is responsible for init — and likely contains the population logic
   that we'd expect to fill MissionPoolIDs. If that logic has an early-exit
   path that skips population (e.g., gated on "is in match"), that's our
   blocker.
2. **Hook `GetMissionsModel` to return our own populated model.** A more
   constructive route — synthesize a UMissionsModel-shaped struct, fill its
   TMaps with 16 entries, and either patch the function to return our ptr
   or patch the field that holds the model ptr in its Outer chain. Needs the
   field layout of UMissionsModel decoded (which TMap is MissionPoolIDs vs.
   MissionPoolAssets) — currently unknown.

Route (1) is recon-only; route (2) is the actual fix attempt. Both productive.

### Mission vs MissionPool TypeData asymmetry — DEFINITIVE root cause (2026-06-28 final)

Walked Mission's `FPrimaryAssetTypeData` (the value ptr in AssetTypeMap entry 6
= 0x16AC7AC9E00) the same way we walked MissionPool's earlier. Result:

| Type | TypeData ptr | AssetMap ptr | AssetMap.Num | AssetMap.Max |
|------|--------------|--------------|--------------|--------------|
| Mission     | 0x16AC7AC9E00 | 0x16B6 7878 E400 | **330** | 350 |
| MissionPool | 0x16B62968000 | 0x16AFC503620 | 16 (= our shim) | 17 |

**Mission's local scan path RUNS and populates 330 entries** (matches half the
cooked AR.bin count of 660 — the other half may be subobjects filtered out).
**MissionPool's local scan path NEVER RUNS** — Mission FPrimaryAssetTypeData
has many non-zero TArray counts in early fields (Directories,
SpecificAssets, AssetScanPaths), MissionPool's are all zero.

The asymmetry is at the **scan-config layer**, not the registration layer.
LokiAssetManager registers BOTH types (both appear in AssetTypeMap as keys),
but only Mission has scan directories configured to actually find + register
asset entries. MissionPool has no directories → directory enumeration finds
nothing → AssetMap stays empty → all the downstream things that depend on
"list of mission pools" (UMissionsModel.MissionPoolIDs, Season's
MissionPools array, modal category enumeration) come up empty.

**This is the actual root cause.** Hypothesis 1 (UI kill criterion) was
correct in spirit but wrong about the layer — it's not that the UI ignores
RegisteredPrimaryAssets, it's that the upstream UMissionsModel population
chain never gets the MissionPool ID list because Loki's local scan never
configures the MissionPool directory.

**Where this fix lands — three candidates by tractability:**

1. **Runtime PrimaryAssetTypesToScan injection.** Find LokiAssetManager's
   PrimaryAssetTypesToScan TArray (member of UAssetManagerSettings, copied
   into LokiAssetManager state at init), find the offset within the
   singleton, append an FPrimaryAssetTypeInfo for `MissionPool` with
   directory `/Game/Loki/Core/Missions/Pools`. Then trigger a re-scan via
   `ScanPathForPrimaryAssets`. Substantial but mechanical.
2. **In-memory FAssetData injection.** Bypass the scan path entirely. Find
   the live FAssetRegistry singleton (anchors from prior recon at
   +0x79D5DF0 / +0x79D5B40) → walk FAssetData TArray → inject 16 entries
   tagged as `LokiDataAsset_MissionPool`. If the populator queries AR for
   these, it'd find them.
3. **Direct UMissionsModel state injection.** Skip the upstream entirely.
   With UMissionsModel at known address (0x16B77E50100), decode its field
   layout (which TMap is MissionPoolIDs, MissionPoolAssets), and write
   entries directly via WriteProcessMemory or via the existing shim
   framework. Smallest scope; doesn't fix the root, just the symptom.

Route (1) is the "fix it at the right layer" approach. Route (3) is the
"smoke test the UI binding" approach — if we directly populate the model
and the modal STILL doesn't render, then there's a downstream binding gap
we don't yet understand. Both worth pursuing in parallel.

The diagnostic phase is now **complete**. The blocker is precisely
identified. Everything from here is either fix-it engineering OR more
diagnostics to disprove the "directly-populate-the-model fixes it"
hypothesis.

### Route 1 attempt — partial / inconclusive (2026-06-28 final)

Tried the "direct UMissionsModel state injection" smoke test. Hit two
blockers that mean Route 1 needs significantly more recon than initially
scoped:

**Surprise finding — 2 instances, one of them partially populated.** Of the
2 live UMissionsModel instances, instance #2 (@0x16B7C654A80) has a TArray
at offset +0x120 with Num=42, Max=56 (data ptr 0x16AF2347400). Instance #1
(@0x16B77E50100) at same offset is empty.

But: **the populated TArray entries do NOT decode as FPrimaryAssetId**. The
first 4-byte slot of each entry holds values like 0x00016F03 / 0x00016F05 /
0x00016F07 — these land mid-string in NamePool block 1 (specifically
inside "MissionExpeditionRewards"), so they're NOT valid FName
ComparisonIndex values. The 16-byte stride is real but the struct is
something else — possibly an FMissionProgress-like record (paired uint32s
+ a smallish uint64 that isn't a heap pointer either).

**Implications:**
- We don't yet know which offset is `MissionPoolIDs` vs `MissionPoolAssets`
  vs other fields like `ProgressTracker`. Both instances might have their
  actual MissionPool data empty.
- The populated TArray at +0x120 is NOT the MissionPoolIDs field. So
  "copy the populated TArray header to the empty model" wouldn't smoke-
  test the right thing.
- Writing blindly into unknown offsets risks crashing the game or silently
  no-op'ing.

**To unblock Route 1, we need one of:**
- (A) UE5 reflection metadata parsing — walk `UMissionsModel`'s UClass
  property chain and extract each field's `Offset_Internal`. This requires
  understanding the FProperty linked-list format in this build.
- (B) Find a function in the binary that writes to MissionPoolIDs (e.g.,
  via `MissionPoolIDs.Add(...)`) and disassemble it. The instruction
  pattern reveals the offset directly.
- (C) Decode the populated-TArray-at-+0x120 struct to confirm it ISN'T
  MissionPoolIDs (we suspect this; can confirm with more analysis).

Each is substantial.

**Pragmatic pivot — try Route 2 next?** Route 2 (PrimaryAssetTypesToScan
injection) is actually more tractable because:
- The scan config lives in UAssetManager's known structure (we already
  decoded AssetTypeMap at +0x478).
- We've identified that Mission's scan config IS populated (TArray fields
  at known offsets within FPrimaryAssetTypeData) and MissionPool's is NOT.
- Comparing Mission's vs MissionPool's TypeData byte-by-byte would reveal
  which sub-field is the Directories TArray that needs population.
- Once we know the offset, write the missing scan path + call a re-scan
  function (need to find one — `ScanPathForPrimaryAssets` is a vtable
  virtual we could anchor).

This stays within the work we've already done (TypeData walking), avoids
the UMissionsModel field-layout decode problem entirely, and fixes at the
right layer (root cause, not symptom).

**Recommendation: Route 2 should be the next attempt.**

### Route 2 attempt — scan PATHS are correct; scan ITSELF didn't run (2026-06-28 ++)

Read both Mission and MissionPool `FPrimaryAssetTypeData` (456 bytes each)
and diffed them. The wide-char fragments in MissionPool's TypeData turned
out to be **uninitialized heap leftover from our late-shim allocation** —
the meaningful fields are clean numeric/pointer values matching Mission's
layout.

Both TypeData structs have a TArray at offset `+0x70` (Num=1, Max=4) — that
field IS the `Directories` (or first scan-path TArray). Reading the TArray
data:

| Type | First Directory string | Length |
|------|------------------------|--------|
| Mission | `/Game/Loki/Core/Missions` | 24 chars |
| MissionPool | `/Game/Loki/Core/Missions/Pools` | 30 chars |

**Both directories are CORRECT.** The MissionPool path points exactly where
its 16 `.uasset` files (DA_MissionPoolDailyChallenge.uasset, etc.) are
cooked. So injecting a directory path is NOT the fix — the directory is
already configured.

**The actual asymmetry: scan was performed for Mission, not for MissionPool.**
The configured directory is there but `ScanPathForPrimaryAssets("MissionPool",
"/Game/Loki/Core/Missions/Pools", ...)` was never called at startup.

Per prior recon (`docs/trackb-assetregistry-route.md`),
`UAssetManager::ScanPrimaryAssetTypesFromConfig` (the bulk scan trigger) is
overridden in LokiAssetManager to be a no-op or crashes via
`__report_gsfailure` when called externally — that explains why Mission's
scan ran but MissionPool's didn't if Loki has a HARDCODED list of types to
scan that's missing MissionPool.

### The actual fix — call ScanPathForPrimaryAssets for MissionPool

We need to invoke `UAssetManager::ScanPathForPrimaryAssets(FName Type,
FString Path, UClass* BaseClass)` — a virtual on the LokiAssetManager
vtable. Once called, UE's standard scan code walks the directory, finds
the cooked LokiDataAsset_MissionPool .uasset files, and populates
AssetTypeMap[MissionPool].AssetMap automatically. From there, UMissionsModel's
population path (whatever it is — likely triggered by some
`OnAssetTypeAdded` delegate) should fire and the modal renders.

**Next-session work plan:**
1. Locate `ScanPathForPrimaryAssets` in the vtable. It's a UE5 virtual,
   should be in slots 0–127 of LokiAssetManager's vtable (we already have
   the dump). Likely findable by signature pattern or by searching the binary
   for the function's UE_LOG strings (`"Scanning path %s for primary assets
   of type %s"` or similar).
2. Extend `registration_shim.cpp` to call this vtable slot with args
   `(singleton, FName="MissionPool", FString="/Game/Loki/Core/Missions/Pools",
   UClass*=LokiDataAsset_MissionPool)`.
3. The UClass* for `LokiDataAsset_MissionPool` — already at known heap
   address 0x16ACDCBF880 (from MissionPool TypeData +0x30 in this run);
   findable each launch via findptr on the class CDO.
4. Inject + run + check: AssetTypeMap[MissionPool].AssetMap.Num should jump
   from 16 (our shim) to ~32 (cooked count) + 16 = 48.
5. Open Missions modal and observe.

### Vtable slot for type-scan virtual landed — but it's a wrapper chain

Disassembled `ScanPrimaryAssetTypesFromConfig` at +0x34D0807. The loop body
calls a virtual at `[rax+0x418]` = **vtable slot 131** for each entry in
PrimaryAssetTypesToScan. Args (per caller):
- rcx = this
- rdx = `[rsp+0x40]` (16 bytes copied from entry — FName Type + 8 bytes pad)
- r8 = `[rbx+0x10]` (entry+0x10, points into the FPrimaryAssetTypeInfo's
  middle — first 16 bytes of the 12-byte tail-region containing some flags
  + TArray.Num)

**Slot 131 (+0x34D32D0)** turned out to be a **filter/wrapper**:
- Reads multiple bytes/dwords from r8 at various offsets (+0, +4, +8, +9, +0xC)
- Compares each against module-global config bytes (`cmp byte [rip+...]`)
- Combines results via bitwise OR into r10b
- Writes the final flag byte to a local buffer at [rsp+0x2C]
- Calls **vtable slot 132 (+0x34D3380)** with `(this, &16-byte-FName,
  &16-byte-buf-with-flags)`

**Slot 132's body** does more processing:
- Tests `[r8+0xC] & 0xF` (the flag byte from wrapper) for non-zero
- Branches into one of two paths: an inline-add path (`sub rcx, -0x80; call
  +0x34CD7C0`) or a hash-lookup path (calls FName-hash, then accesses TMap
  at `[this+0x80]` — NOT AssetTypeMap at +0x478)

`[this+0x80]` is a different TMap than AssetTypeMap. Possibly an
`AssetTypeInfos` cache TArray that's separate from the data we walked.

**The wrapper chain is more involved than expected.** Slot 131 is a
config-driven path that EXTRACTS flags from PrimaryAssetTypesToScan entries
and processes them through slot 132. Calling slot 131 directly requires
constructing an entry-shaped struct (28-byte stride, partial overlap with
FPrimaryAssetTypeInfo). Calling slot 132 directly requires already knowing
how the flag bits get computed.

Neither matches UE's vanilla `ScanPathsForPrimaryAssets(Type, TArray<FString>,
UClass*, ...)` signature cleanly — Loki has WRAPPED the standard scan path
with its own filtering/registration logic, and the vanilla scan virtual may
not be directly on this vtable in the form we'd expect.

### Honest assessment — Route 2's fix is multi-session work

The DIAGNOSTIC for Route 2 succeeded: we now know
- Both Mission and MissionPool have configured scan paths
- Mission's scan runs at startup; MissionPool's doesn't
- The vtable virtual that processes scan entries (slot 131) is identified
- It internally calls slot 132 with extracted flags

### Final negative result on AddDynamicAsset route (2026-06-29)

Built `tools/sigbypass-mod/regen-registrations.ps1` — a pipeline that runs
`usmapdump nameid` against the live game to resolve all 48 needed FName
indices (16 PrimaryAssetNames + 16 PackageNames + 16 _C class names) at
their CURRENT-RUN values, patches `registration_shim.cpp`'s `kRegistrations`
table in place, and rebuilds the DLL.

Re-injected. All 16 calls returned cleanly with the up-to-date FName
indices. External read of MissionPool's AssetMap data ptr (still at
0x16AFC503620) shows our new FName 0x004AF6C3 (= current
`DA_MissionPoolArmoryOnboarding`) present in the bytes — registration
write-path confirmed working with correct FName IDs.

**Modal STILL renders empty.** Zero new Loki.log AssetManager warnings, zero
ChangeBundleState activity for our IDs, no category buttons created in the
modal — identical to all prior runs with stale FNames.

**Definitive conclusion: AddDynamicAsset is NOT the mechanism that drives
the Missions modal**, regardless of whether the registrations have correct
or stale FName IDs. The modal queries a path that bypasses
`AssetTypeMap[MissionPool].AssetMap` entirely.

This rules out Route 1 (AddDynamicAsset-based shim) as a viable fix path.
The remaining options narrow:

- Route 2 proper (call ScanPathsForPrimaryAssets-equivalent vtable slot 131
  with a synthesized entry struct) — still 2-3 sessions of careful work,
  requires reverse-engineering the entry layout + flag bits.
- Route 3 (in-memory FAssetRegistry injection) — bypass AssetManager
  entirely, inject FAssetData entries directly into the AR singleton. AR
  anchors known from prior recon (+0x79D5DF0 / +0x79D5B40).
- Route 4 (NEW): hook into the modal's actual data path. Find what
  WBP_UI_MissionModalCategory's `BindToMissions` function reads from, then
  inject at that layer. Requires Blueprint VM decompilation.

### Route 3 attempted: FAssetRegistry singleton hunt — also hits a wall

Tried to locate the live `UAssetRegistryImpl` singleton via the standard
CDO+vtable+findptr chain:

1. Found `Default__AssetRegistryImpl` FName id 0x005BB216 → CDO @ 0x16AC83F63B0.
2. CDO vtable = +0x79D5328.
3. `findptr` on that vtable → ONLY ONE HIT (the CDO itself). **No live
   UAssetRegistryImpl instance exists.**

Tried `Default__AssetRegistry` (the abstract base) — found CDO with vtable
+0x76EF750. findptr returned 10 hits, but all are flagged 0x31 (CDO). These
are 10 subclass CDOs sharing the base vtable, not live instances.

Confirmed log anchors are correct:
- "FAssetRegistry took %0.4f seconds" @ +0x79D5DF0, log struct @ +0x79D5DD0,
  unique LEA @ +0x1FD8DBE (deep inside the timing-emit function).
- "Premade AssetRegistry loaded from '%s'" @ +0x79D5B40, log struct @
  +0x79D5B20, unique LEA @ +0x1FF5113. Function accesses `[rdi+0x38]` (file
  path FString.Data) and writes a byte at `[rdi+0x301]` — meaning `this` (the
  AR object) is at least 0x302 bytes.

So the active runtime AR DOES exist (it logged at startup), but it's NOT a
UAssetRegistryImpl OR UAssetRegistry UObject — at least not findable via the
standard CDO+vtable scan. Likely it's an FAssetRegistryImpl (struct, not
UObject) accessed via the IAssetRegistry module interface. UE5 sometimes
splits the C++ FAssetRegistryImpl from the UAssetRegistryImpl UObject
wrapper.

### Strategic concern: would Route 3 even work?

Even if we find FAssetRegistryImpl + figure out how to inject FAssetData
entries (substantial work — FAssetData layout decode + hash bucket updates
+ tag store rebuild), the question remains: **does UMissionsModel's
population path actually query IAssetRegistry?**

We have no evidence either way. UMissionsModel's population (via
`OnLocalMissionsInitialized` and `OnPSMissionsUpdated` events) could be
driven by:
- An IAssetRegistry::GetAssetsByClass query (Route 3 would help)
- A LokiAssetManager call into AssetTypeMap (Route 3 wouldn't help — we
  already tested via AddDynamicAsset and it doesn't move the modal)
- A separately-loaded config or hardcoded list (Route 3 wouldn't help)

Without confirming the source, Route 3's significant engineering investment
could be wasted.

### Option A executed 2026-06-29 — UProgressionManager owns the populated model

Did `findptr` on both UMissionsModel instances + decoded their outer classes:

| Model | State | Owner | Ptr-to-model field offset |
|-------|-------|-------|----------------------------|
| #1 @ 0x16B77E50100 | EMPTY | `UEndOfGameModel` | outer+0x580 |
| #2 @ 0x16B7C654A80 | POPULATED (42 entries @ +0x120) | **`UProgressionManager`** | outer+0x3B8 |

`UProgressionManager` (decoded from CDO `Default__ProgressionManager` at id
0x006B32C8, block 107 offset 0x6590) is the LIVE production-progression
tracking system. Its UMissionsModel instance HAS DATA. The populator code
path EXISTS and RUNS — it's just operating on the UProgressionManager-owned
model, not the UEndOfGameModel-owned one.

**The modal's `GetMissionsModel()` returns the EndOfGameModel-owned empty
instance** (we proved this via shim — registering MissionPool entries had
no effect on what the modal renders).

The WBP recon earlier showed the category widget calls both:
- `CallFunc_GetMissionsModel_ReturnValue` (returns the empty model #1)
- `CallFunc_GetProgressionManager_ReturnValue` (could reach model #2 via
  `ProgressionManager->MissionsModel` field at offset 0x3B8)

So the modal HAS access to UProgressionManager directly. But the model it
queries via `GetMissionsModel()` is the WRONG one for menu-state rendering.

### Two paths from here

1. **Reroute `GetMissionsModel()` to return UProgressionManager's model.**
   Find the function's implementation; patch it (or swap an outer chain
   pointer) so the modal queries model #2. This makes the modal see populated
   data — but the data shape is "progress tracking" entries, not the pool/
   mission catalog the modal probably expects to render.

2. **Run the same populator code on model #1.** Find the function in
   UProgressionManager that populates ITS UMissionsModel; call the same
   function with model #1 as the target. This populates model #1 (which the
   modal already queries) with the right data shape.

Route (2) is cleaner but requires finding the populator function in
UProgressionManager. The populator likely writes to known offsets within
UMissionsModel — and we have both an empty and populated instance to
byte-diff for finding the right write target.

### Revised recommendation

Before continuing Route 3, run a smaller diagnostic: trace
UMissionsModel's population code by finding what mutates the empty TMaps
inside it (the ones at +0x130/+0x180/+0x1C4 with HashSize=128/FirstFree=-1).
Even if we can't easily decode the field layout, finding a single
WRITE-XREF to one of those addresses would reveal the populator function.

Or: pivot to Route 4 — Blueprint VM decompilation of
`WBP_UI_MissionModalCategory_C::BindToMissions`. The actual data binding
inside the widget tells us authoritatively what data source to populate.

### The ENGINEERING TASK to actually call this from a shim requires:
- Constructing a 28-byte entry struct matching FPrimaryAssetTypeInfo's
  on-disk layout (FName Type + 8 bytes class info + Directories TArray
  header + flags) — currently approximate, needs validation
- Constructing the matching FName + flags buffer for the slot-131 call
- Potentially recovering the global config bytes that the wrapper compares
  against
- Testing on a stable game state without crashing

This is genuinely 2-3 sessions of careful work — comparable in scope to the
original AddDynamicAsset shim development.

**The diagnostic chain is COMPLETE** — we know what's wrong, where the fix
needs to go, and approximately how to invoke it. The fix itself is a
separate engineering effort.

### Next route — RE the UI's actual enumeration source

Given hypothesis 1's strong support, the productive next pursuit shifts to
**finding what data source the Missions modal / Hunters grid actually reads**.
Candidates (in order of likely productivity):

1. **IAssetRegistry direct query**. The widget likely calls
   `IAssetRegistry::GetAssetsByClass(LokiDataAsset_MissionPool)` or
   `GetAssetsByClass(LokiDataAsset_Mission)` to enumerate. AssetRegistry
   anchors from prior recon: "FAssetRegistry took" at +0x79D5DF0 (unique LEA
   at +0x1FD8DBE), "Premade AssetRegistry loaded from" at +0x79D5B40.
   In-memory FAssetRegistry patch (Approach C) would directly add AssetData
   entries to where the widget actually looks.
2. **Direct asset enumeration via `FAssetData[]` walk of an internal Loki
   manifest cache**. Loki may have its own per-type cache populated during
   init (separate from UAssetManager's). Discoverable by tracing what
   `WBP_UI_MissionModal_C` binds against. Substantial — Blueprint VM bytecode
   inspection.
3. **A LokiDataAsset_Mission registration path**. Different from
   AddDynamicAsset — perhaps a custom `LokiAssetManager::RegisterLokiAsset`
   or similar that updates BOTH UAssetManager state AND Loki's own caches.
   Findable by string-anchoring "LokiDataAsset" within the LokiAssetManager.cpp
   range and tracing what functions touch it.

The UI kill criterion is now the OFFICIAL diagnosis. AddDynamicAsset route is
done with respect to registration — it works, it persists, it just doesn't
move the UI.

### CRITICAL: FName ComparisonIndex is NOT stable across launches (2026-06-28 late)

Discovered during the persistence-probe attempt: per-launch FName indices DRIFT
for any name added to the pool AFTER engine init's earliest phase. Verified by
running `nameid` against two distinct game sessions and comparing.

**Stable across launches** (block 1 — engine-init core names):
- `Mission`     = 0x000162B8 (block 1, offset 0xC570) ✓ same both runs
- `MissionPool` = 0x00016F06 (block 1, offset 0xDE0C) ✓ same both runs
- `Hero`        = 0x0001A568 (block 1, offset 0x14AD0) ✓ same both runs
- All 13 PrimaryAssetType FNames stable (live in blocks 1, 94, 98)

**Drifts per launch** (blocks 6+ — cooked asset names added during AR.bin load):
| Name | Run 1 | Run 2 |
|---|---|---|
| `DA_MissionPoolDailyChallenge` | 0x0013D7DA | 0x00148086 |
| `DA_MissionPoolDailyEasy` | 0x0029D2DA | 0x002A7E5A |
| `DA_MissionPool_Tournament` | 0x00148033 | 0x001529AC |
| `DA_MissionPool_Tournament_C` | 0x00074446 | 0x0007EB5F |
| `/Game/Loki/...DA_MissionPool_Tournament` | 0x00243D04 | 0x0023E81E AND 0x0024E81E (2 hits!) |
| `LokiAssetManager` (singleton's NamePrivate) | 0x00586413 | 0x0029F49F |

This means **the 16 per-asset FName indices baked into
`registration_shim.cpp::kRegistrations` are valid ONLY for the session they
were extracted from.** Subsequent launches register entries under whatever
junk string happens to live at those indices in the new run's pool. The TYPE
key (MissionPool=0x00016F06) is stable, so we always add entries to the right
TMap bucket, but with wrong sub-keys.

**Why the drift:** UE 5.4's FNamePool grows by appending entries as code paths
register them. The order depends on engine init ordering, async loading
schedule, GC behavior, and any non-deterministic startup variance (network
timing, file IO order). Block 1's names get registered during the same
deterministic compile-time init each launch; later blocks fill from cooked
AR.bin in arbitrary order.

**Implications for the shim:**

- **Option A (right fix):** make the shim do RUNTIME lookup against the live
  NamePool — port `nameid`'s pool walker into the shim, look up each needed
  string at shim init time, build the kRegistrations table from runtime
  indices. ~2-3 hours of shim work.
- **Option B (smaller test):** restrict the test to TYPE-only registrations
  (e.g., create a fake PrimaryAssetType entry and see if the UI shows
  ANYTHING) — but Mission/MissionPool types may already exist in the manifest
  consumer's silent-failure list, so this might not surface as a clean test.
- **Option C (external):** dump AssetTypeMap externally via
  ReadProcessMemory after the shim runs, see how many MissionPool sub-entries
  ended up there — regardless of names, count of 16 means writes landed.
  Doesn't validate semantic correctness but proves the write path works.
- **Option D (accept partial):** keep baked indices, run the shim on whatever
  launch we care about, do the UI test immediately, accept that the
  registered entries have garbage names (UI might still render category tabs
  based on TYPE registration alone).

### UI test executed 2026-06-28 evening — Missions modal still empty

Opened the Missions modal after 3 successful registration runs (48 total
AddDynamicAsset calls across 16 MissionPool IDs). Result:

- Modal opens cleanly, title "MISSIONS" renders.
- Body is **completely empty** — no category tabs, no mission cards. (Baseline
  per prior PROBE was "5 empty category tabs render, no missions"; current state
  is even more empty, no tabs.)
- Closing + reopening doesn't change the state.
- Game is **alive and stable** through 3 inject cycles + the UI test — no crash,
  main menu intact, all category buttons (HUNTERS / ARMORY / PASSES /
  CUSTOMIZATION / STORE / CAREER / MISSIONS) still clickable.

### Diagnosis — three competing hypotheses

1. **UI kill criterion fired (per MISSION PROBE #2 prediction).** Modal
   enumerates via a DIFFERENT mechanism than `UAssetManager::RegisteredPrimaryAssets`
   — most likely a direct `IAssetRegistry::GetAssetsByClass(LokiDataAsset_MissionPool)`
   query. Our entries are in LokiAssetManager's TMap but the modal never reads it.
   **Route closes at the UI layer.** Remaining open routes: (a) RE
   `WBP_UI_MissionModal_C` blueprint data binding; (b) in-memory FAssetRegistry
   patch (Approach C — add AssetData entries where the widget actually looks).

2. **Registration didn't persist** (despite clean returns). LokiAssetManager's
   override of AddDynamicAsset might early-return without touching AssetTypeMap,
   making each of our 16 calls a silent no-op. The 3rd run's deliberately-wrong-path
   variant did NOT produce a `"AddDynamicAsset on %s called with conflicting AssetId %s"`
   warning in Loki.log — consistent EITHER with "didn't persist" OR with "log
   filter suppresses that warning category" (LogAssetManager.Warning fired
   twice on initial menu load, so the category isn't globally suppressed —
   tilts the evidence toward "didn't persist").

3. **Registration persisted but assets not loaded.** UAssetManager's
   AddDynamicAsset only REGISTERS the asset path; it doesn't async-load the
   actual `.uasset`. The Missions modal may need the loaded asset's data
   (Icon texture, MaxActive, GrantCount, etc. — visible in
   `tools/extractor/out/catalog/da/DA_MissionPoolDailyChallenge.json`) to render
   anything. Calling `ChangeBundleStateForPrimaryAssets` on our 16 IDs after
   registration might trigger the load → repopulate modal. (Loki.log shows
   ZERO ChangeBundleState activity for our IDs after registration — they're
   registered but never queried/loaded.)

### Next-session work order to disambiguate

In priority order:

1. **Programmatic persistence proof via a different path.** Find one of:
   - `UAssetManager::GetPrimaryAssetData(FPrimaryAssetId, FAssetData&)` — virtual,
     should also be in the LokiAssetManager vtable. Call it for one of our
     registered IDs; non-null return = registration persisted.
   - `UAssetManager::GetPrimaryAssetIdList(FName Type, TArray<FPrimaryAssetId>&)`
     — exposed via AngelScript bind (per prior recon). Returns all registered
     IDs of a type. After our shim runs, calling this for `MissionPool` should
     return ≥16 entries.
   Either disambiguates hypothesis 2 from 1 & 3.

2. **Trigger asset load via `ChangeBundleStateForPrimaryAssets` or `AsyncLoadPrimaryAssets`.**
   Both are virtuals on UAssetManager — find their vtable slots, build a
   follow-up call in the shim that runs after registration. If the modal
   populates after load, hypothesis 3 is the cause and the route is open
   (just needed the load step). If still empty, hypothesis 1 stands.

3. **If hypotheses 1 & 3 both ruled out and registration confirmed persistent:**
   the kill criterion is real. Pivot routes:
   - **RE `WBP_UI_MissionModal_C`** to identify the actual data source the
     widget binds against. Substantial — Blueprint VM bytecode in cooked
     assets, no decompiler runs against shipping pak chunks.
   - **In-memory FAssetRegistry patch** (Approach C above). Find the live
     FAssetRegistry singleton (anchors at +0x79D5DF0, +0x79D5B40); inject
     FAssetData entries directly. Modal queries AR → sees our entries.

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

### Route 1 sub-path 3 smoke test — NEGATIVE (2026-06-29)

Built `tools/usmapdump poke <proc> <addr> <hex-bytes>` (first write-capable
subcommand — opens with VM_WRITE|VM_OPERATION|VM_READ, BEFORE/PAYLOAD/AFTER +
verify). Used it to alias mm2's 3 populated TArray headers (+0x120..+0x14F,
48 bytes) into mm1. Game survived the write cleanly; user opened Missions
modal; **modal STILL renders empty.** Restored mm1's zeros.

Per the kill criterion documented in the next-session prompt: this fires
"the modal might be guarded by an additional condition" — but the analysis
goes further than that. Tail of Loki.log around modal open reveals two
significant findings:

1. **The 5 categories are HARDCODED, not iterated from Season.**
   LogUIActionRouter consistently lists exactly these 5 child widgets when
   the modal opens:
   - `MissionModalCategory_Dailies_1`
   - `MissionModalCategory_Weekly_1`
   - `MissionModalCategory_Seasonal_1`
   - `MissionModalCategory_Onboarding_1`
   - `MissionModalCategory_PCBang_1`

   This INVALIDATES the prior session's hypothesis ("No DA_Season cooked →
   modal can't iterate Season.MissionPools → 0 categories"). The modal
   creates the categories regardless of Season state. The categories then
   each render based on their own data lookup (per-pool missions), and that
   lookup is what comes up empty.

2. **6 `DateTime in bad format (year 0)` LogScript Blueprint warnings fire
   right before the modal open**, lines 11821-11826 of Loki.log. One per
   category? Or per a different per-something logic. Whatever's computing
   these DateTimes (mission GrantedAt? season end? refresh-cycle?) hits
   zero values and silently produces empty rows.

### Schema research — property names confirmed in NamePool

`usmapdump nameid` batch lookup found these property/function names live in
the NamePool of this build:

| Name | FName id | Notes |
|------|----------|-------|
| `MissionPoolIDs` | 0x0064D7B8 | block 100, off 0x1AF70 — property name |
| `MissionPoolAssets` | 0x0064E8E7 | block 100, off 0x1D1CE — TMap value field |
| `MissionPoolAssets_Key` | 0x0064E8F1 | block 100, off 0x1D1E2 — TMap key companion |
| `BindToMissions` | 0x007B4871 | block 123, off 0x90E2 — function name |
| `Categories` | 0x00006468 | generic; not necessarily the modal's |

The MissionPoolAssets_Key companion confirms `MissionPoolAssets` is a TMap
field (UE5's reflection emits a `_Key` FProperty alongside each TMap value
FProperty).

`MissionsModel` (plural, the container) schema extracted via
`extractor schema MissionsModel` returns 8 unknown fields (`?`) — usmap was
generated against a build with stripped property names for this class. So
we cannot directly read off field offsets.

### Direct FProperty findptr — 2 hits for MissionPoolIDs

`findptr` on the FName qword `0x0000000000064D7B8` (FName CmpIdx +
Number=0) returns **exactly 2 hits**: 0x16AECEDDCA0 and 0x16AECEDDD20.
Both have this prefix:

```
+0x00: FName(MissionPoolIDs)              // 8 bytes
+0x08: 0x45 (= 69)                        // 4 bytes — possibly ClassInternalIndex of owner
+0x0C: 0                                  // 4 bytes
+0x10: 0x01 (ArrayDim)                    // 4 bytes
+0x14: 0x10 (= 16, ElementSize)           // 4 bytes ← sizeof(FPrimaryAssetId)
+0x18-0x1F: EPropertyFlags                // differs between the 2 hits
+0x60: ptr ~0x7FF666DFAA30 (.rdata)       // looks like a vtable ptr
+0x78: ptr to neighboring FProperty       // linked-list "Next"
```

**CAUTION — half-wrong reading.** The 0x10 at +0x14 is `ElementSize`
(`sizeof(FPrimaryAssetId)=16`), NOT `Offset_Internal`. The actual
Offset_Internal is somewhere later in this FProperty layout — we don't yet
know exactly where. Peeking the FProperty's +0x60 (`0x7FF666DFAA30`) showed
a chain of 8 distinct ptrs into .rdata — looks like a vtable, not a single
UClass ptr. So the owner-discovery anchor needs more work.

Peek of `[UProgressionManager + 0x10] = 0x16AC4957A30` shows:

```
+0x10: F1 D5 00 00 00 00 00 00   ← InternalIndex 0xD5F1 (uint32 in UObject hdr)
+0x18: 80 6C FE CD 6A 01 00 00   ← ClassPrivate 0x016ACDFE6C80
+0x20: 5F 0B 59 00 6A FB FF 7F   ← NamePrivate
+0x28: 80 7D 90 FC 6A 01 00 00   ← Outer 0x016AFC907D80
```

UProgressionManager's +0x10 is part of the UObject header — definitely
NOT a TArray. So MissionPoolIDs is NOT at +0x10 of UProgressionManager
either. The prior recon's claim that MissionPoolIDs is on
`ALokiPlayerState` may still be the right owner (no live instance at
menu — so MissionPoolIDs naturally empty there).

### Updated mental model (2026-06-29 mid-session)

```
WBP_UI_MissionModal_C::Construct():
  -> creates 5 HARDCODED category widgets (Dailies/Weekly/Seasonal/Onboarding/PCBang)
  -> NO Season iteration — categories are wired statically
                            ↓
Each WBP_UI_MissionModalCategory::Construct():
  -> CallFunc_GetMissionsModel_ReturnValue       ← returns mm1 (empty) — proven RED HERRING
  -> CallFunc_GetProgressionManager_ReturnValue  ← live instance exists
  -> BindToMissions(...)                         ← reads FROM somewhere
  -> If lookup returns 0 entries → render empty (zero size)
                            ↓
DateTime warnings:
  -> 6 Script warnings ("DateTime in bad format (year 0)") right before modal open
  -> Possibly per-category (5) + 1 modal-level, or 6 sub-checks
  -> All zero → silent empty rendering
```

The smoke test definitively rules out the `mm1.+0x120` TArrays as the
modal's data source. The categories ARE created; their per-pool data
lookup is what fails.

### Concrete next-session work

The path forward branches by what we want to learn next. In rough order of
productivity-per-session-cost:

1. **Decompile WBP_UI_MissionModalCategory_C::BindToMissions** (Blueprint
   VM bytecode in the cooked .uasset). This is the authoritative source for
   what data the categories read. Substantial — requires CUE4Parse BP VM
   support OR external uasset extraction + bytecode reading.

2. **Find the owning UClass for MissionPoolIDs FProperty** — disasm a
   small area starting from one of the 2 FProperty entries
   (0x16AECEDDCA0 / 0x16AECEDDD20). Walk the FField chain to find the
   parent UClass. Read its name FName. That definitively answers "where
   does MissionPoolIDs live."

3. **Investigate the 6 DateTime warnings** — `Select-String` in Loki.log
   around modal open might show which Blueprint widget/function emits
   them. UE5 Script warnings usually log the calling context.

4. **Decode UProgressionManager's full layout** by walking its UClass
   property chain (the same approach as #2 but for a class we already have
   a live instance of). Would tell us all 11 fields' offsets — including
   whether MissionsModel is at +0x3B8 (per prior recon) and if there's a
   different field on UProgressionManager that holds the modal's data.

### What we now KNOW vs. ASSUME

KNOW:
- mm1 (UEndOfGameModel-owned) and mm2 (UProgressionManager-owned) are real
  but **the modal doesn't directly query either's +0x120 TArrays**.
- 5 categories are hardcoded and DO get created when the modal opens.
- `MissionPoolIDs`, `MissionPoolAssets`, `MissionPoolAssets_Key`,
  `BindToMissions` all exist as pooled FNames in this build.
- Exactly 2 FProperty entries for `MissionPoolIDs` exist, ElementSize=16.
- UProgressionManager+0x10 is UObject header (ClassPrivate), not a property.

ASSUME (still to verify):
- The owning class for MissionPoolIDs is ALokiPlayerState (per prior
  recon — needs FProperty owner walk to confirm).
- The 6 DateTime warnings are tied to per-category logic.
- Some "live" data source on UProgressionManager or a subsystem (not
  ALokiPlayerState, since no instance at menu) is what feeds the modal's
  per-category data.

### Plan A DONE — empirical FProperty layout + DateTime source (2026-06-29)

96 `LogScript Warning: DateTime in bad format (year 0)` warnings total in
the live session log, **in clusters of exactly 6 per modal-open** (16 opens
× 6 = 96). The format string lives ONLY in heap (UE shipping build
stripped it from .rdata), so no xref anchor for it directly. Instead
identified via UE source reading: `UKismetMathLibrary::MakeDateTime` is
the function that emits this exact warning when BP code calls "Make Date
Time" with all-zero inputs. The UFunction `MakeDateTime` (id 0x00035AD3)
and `CallFunc_MakeDateTime_ReturnValue` (id 0x007A1DEA) both exist as
pooled FNames — definitive proof a Blueprint calls Make Date Time.

`usmapdump nameid` batch found per-category DateTime fields:

| FName | id | Owner offset | Type |
|-------|----|--------------|------|
| `NextWeeklyRefreshTime` | 0x00627B86 | 0x38 | FDateTime |
| `NextDailiesRefreshTime` | 0x00627B92 | 0x30 | FDateTime |

ONLY Weekly and Dailies have explicit refresh-time fields — Seasonal /
Onboarding / PCBang do not. So the "6 warnings per modal = 5 categories +
1 modal" mapping is **wrong**. The 6 warnings come from somewhere else
(possibly the Make Date Time node is called for multiple uses per category
read — e.g., parse + format + display), or there's a generic per-mission
GrantedAt read iterating 6 missions, or something else.

**Empirical FProperty layout** derived from peek of 4 adjacent entries:

```
+0x00 (8): FName NamePrivate
+0x08 (4): InternalIndex 0x45 (consistent — could be owner-UClass index
                                 or FFieldClass index, not yet confirmed)
+0x0C (4): unknown (often 0)
+0x10 (4): int32 ArrayDim
+0x14 (4): int32 ElementSize ← matches type sizes (8=FDateTime,
                                16=FPrimaryAssetId, 0x28=TMap header)
+0x18 (8): EPropertyFlags
+0x20 (4): unknown (often 0)
+0x24 (4): int32 Offset_Internal ← empirically verified: 0x30
                                    for NextDailies, 0x38 for NextWeekly
+0x28..0x4F: zeros / sparse
+0x50 (8): owner UObject* heap ptr
+0x60 (8): vtable-ish .rdata ptr (FFieldClass*?) — shared across FProperty
                                                    instances of same type
+0x68 (8): another .rdata ptr (shared)
+0x70 (8): heap ptr to neighboring FProperty
+0x78 (8): heap ptr to next FProperty in chain
```

Total stride **0x80 bytes per FProperty**.

Note: layout does NOT match vanilla UE5.4 `FField`/`FProperty` from
public Engine source (which has FName at +0x20, not +0x00). Loki has
either customized the layout OR these entries are a different reflection
structure (FCachedProperty? FFieldData?). Doesn't change the conclusion —
the per-entry fields decode consistently.

**MissionPoolIDs re-examined with the corrected schema:**
- Entry 1 @0x16AECEDDCA0: ElementSize=0x10, Offset_Internal=0 (suspicious
  — offset 0 means it's the first field of its owning USTRUCT, or the
  FName/InternalIndex parse is off for this entry)
- Entry 2 @0x16AECEDDD20: ElementSize=0x10, Offset_Internal=0x10

The +0x80 spacing pattern is identical to the NextRefreshTime chain. So
MissionPoolIDs has two FProperty entries possibly representing two
classes that both define a `MissionPoolIDs` field (e.g., maybe the
modal's per-category widget has its OWN MissionPoolIDs subset?).

**Anchor for Plan B**: the per-category data binding goes through
`BindToMissions` (FName id 0x007B4871). That's the next thing to track.

### Plan B DONE — BindToMissions identified as BP UFunction (2026-06-29)

`findptr` on the BindToMissions FName id (0x007B4871) returns 3 distinct
aligned hits, including one at heap address `0x16B98E02E20` (= 0x20 into a
UObject — the NamePrivate offset). Peek of the UObject at `0x16B98E02E00`
shows the standard UE5.4 UObject + UStruct + UFunction layout:

```
0x16B98E02E00  (= BindToMissions UFunction)
  +0x00: vtable          0x7FF666DCEB60  (RVA 0x76FEB60, .rdata UFunction vtable)
  +0x0C: ObjectFlags     0x00280001
  +0x18: ClassPrivate    0x016AB8B7B000  (UFunction's UClass*)
  +0x20: NamePrivate     FName(BindToMissions) + 0
  +0x28: Outer           0x016B98C2E930  (the owning class)
  +0x50: Children        0x016B98DF9C80
  +0x60: PropertiesSize  0x98 (152 bytes — the function's stack frame)
  +0x64: MinAlignment    0x08
  +0x68: ChildProperties 0x016B98C2E4A0  (FProperty linked list — params + locals)
  +0x70: Script.Num=0x470 (1136), Script.Max=0x490 (1168)
  +0x78: Script.Data     0x016B98DF9C80
```

The Outer of BindToMissions is **`WBP_UI_MissionModalCategory_C`** —
verified by reverse-looking up the Outer's NamePrivate FName id (0x0047678A
= block 71, off 0xCF14) via `nameid` substring search:

```
[WBP_UI_MissionModalCategory_C] block=71  off=0xCF14   id=0x0047678A
                                          "WBP_UI_MissionModalCategory_C"
```

So **BindToMissions is a Blueprint-compiled UFunction belonging to the
category widget class itself.** The 1136 bytes of bytecode at 0x016B98DF9C80
contain the actual data-binding logic. To know what data the modal categories
read, that bytecode needs to be decompiled (UE BP VM bytecode).

Related discovered names (all in NamePool):

| FName | id | Notes |
|-------|----|-------|
| `WBP_UI_MissionModalCategory_C` | 0x0047678A | the class itself |
| `Default__WBP_UI_MissionModalCategory_C` | 0x007B4933 | CDO |
| `ExecuteUbergraph_WBP_UI_MissionModalCategory` | 0x007B48C2 | event graph bytecode |
| `ExecuteUbergraph_WBP_UI_MissionModalCategoryButton` | 0x007A1E21 | sibling category-button BP |
| `ExecuteUbergraph_WBP_UI_MissionModal_MissionEntry` | 0x007B4725 | per-mission entry BP |
| `ExecuteUbergraph_WBP_UI_MissionModal` | 0x007B4FE0 | the modal's own event graph |

**Concrete handles for next-session BP decompile work**:
- BindToMissions UFunction: 0x16B98E02E00 (Script at +0x78 = 0x016B98DF9C80, 1136 bytes)
- Parent class UClass: 0x16B98C2E930
- ChildProperties linked list head: 0x016B98C2E4A0 (walk these for parameter signature)

The CDO of `WBP_UI_MissionModalCategory_C` will reveal the class's default
property values; its UClass at 0x16B98C2E930 has property metadata for all
member fields. Walking that gives us the full per-category data shape, which
combined with the BP bytecode tells us authoritatively where the modal
sources its per-category data.

### Plan C DONE — MissionPoolIDs owner = LokiPlayerState_Missions (no live instance at menu)

`usmapdump nameid` for `Default__LokiPlayerState*` returned **5 distinct
sub-CDOs**:

| CDO Name | FName id |
|----------|----------|
| `Default__LokiPlayerState` | 0x006B2304 |
| `Default__LokiPlayerStateArmoryRewardComponent` | 0x006B2325 |
| `Default__LokiPlayerStatePawnComponent` | 0x006B233D |
| `Default__LokiPlayerState_HeroAffiliated` | 0x006B2351 |
| **`Default__LokiPlayerState_Missions`** | **0x006B2366** |

The last one — `LokiPlayerState_Missions` — is the **dedicated missions
sub-class** on the player state. Almost certainly the owning class for the
MissionPoolIDs FProperty (matches the "missions, on player state" picture
from prior recon, but more specific).

CDO at `0x16AC8BD2250` (ObjectFlags=0x31, RF_Public|RF_ClassDefaultObject).
Its UClass at `0x016ACDFB7400`. Vtable `0x7FF668109150`.

**findptr on that vtable returns ONLY ONE HIT — just the CDO itself. No
live instance.** This matches the prior session's "ALokiPlayerState only
spawns in matches, not at menu" finding, extended to its sub-classes.

So MissionPoolIDs (TArray<FPrimaryAssetId>) on LokiPlayerState_Missions is
ALWAYS empty at the menu — because there is no instance to populate.

### Combined picture from Plans A+B+C

```
WBP_UI_MissionModal_C::Construct():
  -> creates 5 HARDCODED category widgets (Dailies/Weekly/Seasonal/Onboarding/PCBang)

Each WBP_UI_MissionModalCategory_C widget:
  -> calls BindToMissions UFunction (BP, 1136 bytes bytecode @ 0x016B98DF9C80)
  -> BindToMissions internally accesses some data source(s)
       - GetMissionsModel() returns mm1 (UMissionsModel @ 0x16B77E50100, empty)
       - GetProgressionManager() returns live UProgressionManager @ 0x16AC4957A20
       - Possibly tries to read MissionPoolIDs from LokiPlayerState_Missions
         (no live instance at menu → naturally empty)
  -> Per category, also calls Make Date Time with zero inputs → 1 of the
     6 "DateTime in bad format" warnings per modal open

Where the data SHOULD come from (best current guess):
  -> UMissionsModel has 8 fields. 3 are empty TMaps at +0x30 / +0x80 / +0xD0,
     3 are TArrays at +0x120 / +0x130 / +0x140 (populated only on mm2).
  -> One of the TMaps is almost certainly MissionPoolAssets
     (TMap<FPrimaryAssetId, X>, where X is per-pool aggregated mission data).
  -> Both models have these TMaps empty.
  -> Populating one of the TMaps with our 16 cooked MissionPool entries
     would likely move the modal — but the VALUE TYPE of the TMap is
     unknown without BP bytecode decompile or property-walk of UMissionsModel.
```

### What the 3 plans collectively prove

KNOW NOW (post Plans A+B+C):
- Categories (5) are hardcoded in modal — every open creates exactly these 5
- BindToMissions is BP-compiled on WBP_UI_MissionModalCategory_C
- DateTime warnings come from `UKismetMathLibrary::MakeDateTime` being
  called with zero inputs — 6 per modal open from BP code
- MissionPoolIDs lives on LokiPlayerState_Missions, no live instance at menu
- mm1's +0x120-+0x14F TArrays are NOT the modal's read source (smoke test
  proved it)
- mm1 and mm2 differ ONLY in those 3 TArrays + the +0x160-0x17F hash bytes

NEXT-SESSION ROUTES (now better-anchored):

1. **Decompile BindToMissions BP bytecode** — 1136 bytes at 0x016B98DF9C80.
   CUE4Parse has BP VM bytecode disassembler support. This is the
   authoritative way to know what data BindToMissions reads.

2. **Walk WBP_UI_MissionModalCategory_C class properties** — find what fields
   the per-category widget itself has (e.g., does it have its own
   `MissionPool` field that's set per-instance? Each of the 5 categories
   might have a hardcoded pool reference).

3. **Identify UMissionsModel's 3 TMaps by name** — search for FProperty
   entries with `MissionPoolAssets` FName id (0x0064E8E7). Find their
   offsets within UMissionsModel. If one is at +0x30 / +0x80 / +0xD0, we
   know which TMap to populate.

4. **Populate UMissionsModel.MissionPoolAssets** — once the TMap value
   type is known, smoke-test by writing 16 entries via `usmapdump poke`
   into the TMap's internal hash structure.

### NEXT — bpdump tool + per-category pool wiring (2026-06-29)

New tool: `tools/extractor/extractor` subcommand `bpdump`:
- `bpdump <asset-substr> <fn-name>` — find UFunction, attempt BP bytecode
  walk (KismetExpression[]); CUE4Parse 1.2.2 returns NULL for ScriptBytecode
  on this build's IoPackage format, so the bytecode walk doesn't produce
  output. The tool's actual value is its summary modes:
- `bpdump <asset-substr> *` — emit all UFunctions + their ChildProperties
  signature (param/local type list). Names stripped but types remain.
- `bpdump <asset-substr> @props` — emit every UObject export's serialized
  property values, recursing into ArrayProperty.Value.Properties.

Running it on `WBP_UI_MissionModal.uasset`:

**Per-category PoolAsset wiring** (the missing piece — each category widget
has its own TArray<TSubclassOf<...>>):

| Category | PoolAsset classes |
|----------|-------------------|
| Dailies | `DA_MissionPoolDailyEasy_C`, `DailyChallenge_C`, `DailyEasy_Planbee_C`, `DailyChallenge_Planbee_C` |
| Weekly | `DA_MissionPoolWeekly_C`, `WeeklyChallenge_C`, `Weekly_Planbee_C`, `WeeklyChallenge_Planbee_C` |
| Seasonal | `DA_MissionPool_Tournament_C` |
| Onboarding | `DA_MissionPoolOnboardingPlanbee_C`, `DA_MissionPoolOnboarding_C` |
| PCBang | `DA_MissionPoolDailyPCB_C`, `DA_MissionPoolDailyPCB_Armory_C` |
| ArmoryTest (hidden) | `DA_MissionPoolArmoryOnboarding_C` |

All 13 unique pool classes match what we already registered via
AddDynamicAsset shim. So the registration was on-target but the
**categories don't query AssetTypeMap** — they query something else.

**The modal CDO has `DynamicMissionPools (ArrayProperty)` with 36 baked
struct entries** in `Default__WBP_UI_MissionModal_C`. The struct
elements' field contents not yet expanded (FStructFallback recursion fix
TBD), but their EXISTENCE is significant: the modal class itself has
baked pool-config data, not just runtime-discovered.

**Other modal-level fields/functions discovered**:
- `OnMissionsModelUpdated` — modal listens for MissionsModel changes
- `OnManifestUpdated` — modal listens for content manifest updates
- `Ubergraph` has 89 local variables (huge event graph)
- 7 hardcoded category instances total (5 visible + 2 hidden ArmoryTest/Config)

**Per-category UFunctions** (12 on `WBP_UI_MissionModalCategory_C`):
- `BindToMissions` — 20 properties (FUNC_BlueprintCallable, FUNC_BlueprintEvent)
- `CreateAssetsForPools` — 10 properties incl. FClassProperty
- `UpdatePoolAssets` — 1 FArrayProperty (the assets array)
- `UpdateMissionPoolTimer` — 10 properties (FStructProperty likely the FDateTime)
- `UpdateMetaMission` — 27 properties (huge — meta-mission update)
- `OnChildrenCountChanged` — 1 FIntProperty
- `OnInitialized`, `Construct`, `OnUpdated`, `BP_GetDesiredFocusTarget`,
  `BndEvt__*_OnClaimed_*`, `ExecuteUbergraph_*`

Widget tree under each category: `VerticalBox -> ScrollBox ->
MissionsContainer_v2 (WBP_UI_MissionContainer_v2)` — the container that
actually renders the missions.

### Concrete actionable fix path (post bpdump session)

1. **Find live WBP_UI_MissionModal_C widget instance in memory** — opens
   each time user clicks Missions. Its DynamicMissionPools field is at
   some offset > 0 (need to find).
2. **Check if DynamicMissionPools has 36 entries at runtime** — if yes,
   wiring is intact, blocker is per-entry mission data. If 0/empty,
   CDO defaults aren't propagating and that's the deeper bug.
3. **Decode a DynamicMissionPool struct entry** (improve bpdump struct
   recursion or read raw bytes from the live CDO). Likely fields:
   FName/FClass pool ref + TArray of mission entries + DateTime fields.
4. **For each empty category**, populate via WriteProcessMemory if data
   path can be replicated.

Cooked content has 16 MissionPool .uassets — exactly 13 are referenced by
categories + 3 are unused (likely deprecated or test-only). The complete
list per `tools/extractor/out/catalog/da_index.csv`:
- All 4 Dailies-category pools (Easy, Challenge, Easy_Planbee, Challenge_Planbee)
- All 4 Weekly-category pools
- 1 Seasonal: DA_MissionPool_Tournament
- 2 Onboarding pools
- 2 PCBang pools
- 1 ArmoryOnboarding (used by ArmoryTest, hidden)
- 1 ArmoryDaily (PCBang variant — DA_MissionPoolDailyPCB_Armory)
- 1 HunterMissions (UNUSED by any category)
- 1 TutorialMaps (UNUSED by any category)

So 14 pools used + 2 unused = 16 cooked.

### D1-D4 (2026-06-29) — DynamicMissionPools decoded: 36 SeasonalArmory entries baked into CDO

Walked the live runtime to inspect what the modal actually has at runtime:

1. **Live modal instance found**: `WBP_UI_MissionModal_C_2147458383` at
   `0x16B8E267480` (NamePrivate qword `0x7FFF9D5000117FAC` — CmpIdx
   0x00117FAC = "WBP_UI_MissionModal_C" base, Number 0x7FFF9D50). Outer
   at +0x28 = `0x016B88B0EC00`. Vtable + class match CDO at
   `0x16B987CE2F0`.

2. **DynamicMissionPools field offset**: walked the FProperty chain for
   FName id 0x007B4FD5 (DynamicMissionPools). 2 entries returned (the
   FArrayProperty + the FStructProperty inner). The Inner FProperty has
   Offset_Internal = **0x4F0 (1264)** in the widget class. Each element
   is **16 bytes** (FStructProperty ElementSize=0x10).

3. **DynamicMissionPools populated**: at runtime, the TArray at
   `[modal + 0x4F0]` has **Num=36, Max=36** with Data ptr
   `0x016BF4C95080`. The CDO has the SAME 36 entries at
   `0x016B6552E080`. So the wiring DEFAULTS DID propagate from CDO to
   the live instance. The 36 entries are pre-baked, not runtime-populated.

4. **Entry layout — each is FPrimaryAssetId** (16 bytes = two FNames):
   - Type FName = MissionPool (CmpIdx=0x00016F06, Number=0) for EVERY entry
   - Name FName = SeasonalArmory mission name, Number = 2 / 3 / 4

   Decoded the 12 unique Name FNames (each appearing 3× with Number 2/3/4):
   - `SeasonalArmory_AcademyResearch`  (FName 0x007B50F1)
   - `SeasonalArmory_Bloodshed`        (0x007B5101)
   - `SeasonalArmory_FelixFamous`      (0x007B510E)
   - `SeasonalArmory_HuntSoulborn`     (0x007B511C)
   - `SeasonalArmory_Kobayashi`        (0x007B512B)
   - `SeasonalArmory_ProtectHavenshard` (0x007B5138)
   - `SeasonalArmory_ProveYourWorth`   (0x007B5149)
   - `SeasonalArmory_RisenEmpire`      (0x007B5159)
   - `SeasonalArmory_ScoutTheBreach`   (0x007B5167)
   - `SeasonalArmory_Skysharks`        (0x007B5177)
   - `SeasonalArmory_SubdueScavbay`    (0x007B5184)
   - `SeasonalArmory_WinterDance`      (0x007B5193)

5. **CRITICAL CROSS-CATEGORY INSIGHT**: DynamicMissionPools contains
   ONLY SeasonalArmory entries (12 missions × 3 difficulty/index variants
   = 36). It does NOT contain entries for Daily / Weekly / Onboarding /
   PCBang category pools. So:
   - All 5 categories filter their per-category PoolAsset against
     DynamicMissionPools' 36 entries
   - Daily, Weekly, Onboarding, PCBang filters find ZERO matches
     (DynamicMissionPools has no Daily/Weekly/etc. entries)
   - Seasonal filter looks for DA_MissionPool_Tournament_C class match
     but entries reference SeasonalArmory_X_N — different FNames
   - ALL 5 categories render empty for different reasons

   This explains why our earlier AddDynamicAsset shim (which registered
   the 16 BASE pool names like `MissionPool:DA_MissionPoolDailyEasy`)
   didn't move the modal — it modified the AssetTypeMap registration but
   NOT the DynamicMissionPools array the modal actually iterates.

6. **D4 smoke test**: poked first DynamicMissionPools entry from
   `MissionPool:SeasonalArmory_ProveYourWorth_1` →
   `MissionPool:DA_MissionPoolDailyEasy` (FName 0x002A7E5A, Number=0).
   Write succeeded; user re-opened modal; **result pending** as of doc
   update.

### Concrete fix candidates (post-smoke-test)

If smoke test SUCCEEDS (Dailies tab shows 1 entry):
- The fix is to APPEND ~30+ more entries to DynamicMissionPools, one per
  Daily/Weekly/Onboarding/PCBang pool that we want rendered
- Each entry: `{Type=MissionPool, Name=DA_MissionPool<XYZ>}` matching the
  category's PoolAsset BlueprintGeneratedClasses
- For Seasonal, swap the existing entries to use the
  `DA_MissionPool_Tournament` name instead of SeasonalArmory_*
- Implementation: extend `registration_shim.cpp` to poke
  DynamicMissionPools at runtime, OR direct WriteProcessMemory poke
- Caveat: TArray growth requires allocating a new buffer. For Num→48
  (current 36 + 12 new), Max=36 means we need to reallocate or
  in-place-replace existing entries

If smoke test FAILS (Dailies still empty):
- The lookup chain needs more than just the FPrimaryAssetId match
- Likely requires the asset to be REGISTERED in UAssetManager's
  primary asset table (UAssetManager::GetPrimaryAssetData succeeds)
- Or requires the asset to be LOADED (asset object exists, not just
  registered)
- Need to register the specific entry's full FSoftObjectPath + load it

Next session — depending on smoke test outcome — implement either the
poke-based fix or the deeper registration + load chain.

### D4 SMOKE TEST RESULT: NEGATIVE (2026-06-29)

Poked 5 DynamicMissionPools entries (0-4) with category-matching pool refs:
- [0] `MissionPool:DA_MissionPoolDailyEasy` (FName 0x002A7E5A, Number=0)
- [1] `MissionPool:DA_MissionPoolDailyChallenge` (FName 0x00148086)
- [2] `MissionPool:DA_MissionPoolWeekly` (FName 0x00268463)
- [3] `MissionPool:DA_MissionPoolOnboarding` (FName 0x0025D3CE)
- [4] `MissionPool:DA_MissionPool_Tournament` (FName 0x001529AC)

User closed + reopened modal. **All 5 categories STILL empty** — modal
rendered identically to before. Pokes were verified post-write, in-place.

**DEFINITIVE: DynamicMissionPools is NOT the modal's data source for
per-category rendering.** The 36 SeasonalArmory entries are present but
the modal doesn't iterate them for category content.

Restored all 5 entries to their original SeasonalArmory values.

### Next data-source candidates (post-D4)

The remaining candidates for the modal's per-category data source:

A. **`MissionPoolAssets` TMap** — FName 0x0064E8E7 confirmed in NamePool +
   `_Key` companion (FName 0x0064E8F1) proves it's a TMap. FProperty
   findptr returned 2 hits:
   - @0x16AC7CB9680: full TMap FMapProperty, ElementSize=0x50,
     **Offset_Internal=0x1C0 (448)** in some owning class
   - @0x16AECF18FA0: Value FProperty (FObjectProperty?), ElementSize=0x08
     (= sizeof UObject*), Offset 0x10
   - And the _Key FProperty: ElementSize=0x10 (= sizeof FPrimaryAssetId)

   So MissionPoolAssets is `TMap<FPrimaryAssetId, UObject*>` at offset
   0x1C0 of its owning class. **Owner class NOT YET IDENTIFIED** — checked
   UProgressionManager+0x1C0 = empty TMap (zeros). Could be on
   `LokiPlayerState_Missions` (no live instance at menu) OR on some
   other class we haven't enumerated.

B. **Per-category widget's runtime state** — each
   `WBP_UI_MissionModalCategory_C` instance has its own UpdatePoolAssets,
   CreateAssetsForPools, BindToMissions UFunctions. These manage per-
   category state directly. Maybe each category populates its own widget
   based on a different lookup.

C. **A subsystem function** — e.g. `LokiMissionSubsystem::GetMissionsForPool(class)`
   called per category. Need string anchor / vtable walk.

D. **Loading-state gate** — modal might render empty until
   `OnMissionsModelUpdated` fires. With server disconnect logged
   (LogMessenger heartbeat fail) + WS bouncing 571MB → 7548MB → 6672MB,
   the data load might be failing/pending. Modal stays in "loading"
   state forever.

### Honest assessment

The diagnostic story so far:
- We know exactly WHICH WIDGETS (5 categories) are created
- We know WHICH POOL CLASSES each category references (from BP defaults)
- We know what's in the LIVE modal's DynamicMissionPools (36 entries,
  all SeasonalArmory)
- We've PROVEN the modal doesn't render based on DynamicMissionPools
- We've identified MissionPoolAssets TMap as a strong candidate but
  haven't found its owning class instance yet

Without BP bytecode decompilation (CUE4Parse 1.2.2 doesn't support this
build's IoPackage format), we're constrained to runtime memory inspection.
That's slow but tractable.

Next concrete steps:
1. Find MissionPoolAssets owning class via FProperty back-walk
2. Check if any live instance has populated MissionPoolAssets TMap
3. If empty everywhere, the lookup is failing at a deeper layer
   (registration → load → bind chain)
4. Consider deeper inspection of OnMissionsModelUpdated / OnManifestUpdated
   to see what triggers re-render

### E1-E3 (2026-06-29) — FModel JSON export DECODES the modal's lookup chain

CUE4Parse 1.2.2 STILL can't deserialize BP bytecode for this build's IoPackage.
BUT FModel exports the asset with FULL property NAMES (our `bpdump` showed
"?" because reflection couldn't find the name field — FModel has it).

User exported `WBP_UI_MissionModalCategory.uasset` via FModel
right-click → Save Package Properties (.json) →
`G:\git\Supervive Revival Project\Output\Exports\Loki\Content\Loki\Core\Missions\WBP_UI_MissionModalCategory.json`
(56KB / 1671 lines). Saved a copy to `docs/exports/` for git tracking.

**The data flow is now FULLY DECODED via BP local variable names** (UE BP
compiler generates predictable names like `CallFunc_<FunctionName>_ReturnValue`):

WBP_UI_MissionModalCategory_C class fields:
  PoolAsset           TArray<TSubclassOf<LokiDataAsset_MissionPool>>  -- pre-baked BP defaults
  HeaderName          TextProperty                                     -- category label
  CategoryIcon        PaperSprite                                      -- icon
  CategoryIconTexture Texture2D
  PoolIds             TSet<FPrimaryAssetId>  -- RUNTIME-COMPUTED from PoolAsset

BindToMissions(...) — local vars reveal the algorithm:
  - Loop through MissionsContainer_v2's children (CallFunc_GetAllChildren)
  - For each child, DynamicCast to WBP_UI_Mission_Container
  - Iterate PoolAsset[] (the pre-baked class refs)
  - For each pool class: GetPrimaryAssetIdFromClass(class) -> FPrimaryAssetId
  - Get MissionsModel via GetMissionsModel()
  - Get ProgressionManager via GetProgressionManager()
  - Create delegate bindings (K2Node_CreateDelegate)

UpdateMetaMission(...) — THE LOOKUP, by BP local var names:
  - IsValidPrimaryAssetId  -> validates each ID
  - GetMissionsModel       -> mm1 or mm2?
  - **GetClaimableMissionModel_ReturnValue**  <- LOOKUP #1
  - **GetActiveMissionModel_ReturnValue**     <- LOOKUP #2
  - IsValid -> bool check on returned mission

CreateAssetsForPools(...) — populates the per-pool container widgets:
  - Iterates PoolAsset[]
  - CallFunc_Create_ReturnValue          -- creates WBP_UI_Mission_Container
  - CallFunc_AddChildToVerticalBox_ReturnValue  -- adds to MissionsContainer_v2

UpdatePoolAssets(TArray<TSubclassOf<LokiDataAsset_MissionPool>> Pools)
  -- the param IS the PoolAsset[] array, name confirmed: "Pools"

### THE LOOKUP CHAIN — end-to-end

```
WBP_UI_MissionModal::Construct
  -> for each category {Dailies, Weekly, Seasonal, Onboarding, PCBang}:
       category.PoolAsset = pre-baked TArray (from CDO)
       category.CreateAssetsForPools(category.PoolAsset)
         -> for each pool class P in PoolAsset:
              fpaid = GetPrimaryAssetIdFromClass(P)
                -- e.g. MissionPool:DA_MissionPoolDailyEasy
              container = Create WBP_UI_Mission_Container
              container.BindToMissions(...)
                -> for each pool class P:
                     fpaid = GetPrimaryAssetIdFromClass(P)
                     model = GetMissionsModel()         -- mm1 (empty)
                     activeMission = model.GetActiveMissionModel(fpaid)
                     claimMission  = model.GetClaimableMissionModel(fpaid)
                     if (IsValid(activeMission) OR IsValid(claimMission)):
                       render UI for this mission
                     else: empty
```

### E3 — Native function addresses identified

| Function | FName id | UFunction obj | Func native ptr |
|----------|----------|---------------|-----------------|
| GetActiveMissionModel | 0x0058FEFF | 0x16AC8904A90 | 0x7FF664B75A20 (RVA +0x54A5A20) |
| GetClaimableMissionModel | 0x0058FF0B | 0x16AC8904B80 | (immediately after, +0xF0) |
| GetMissionsModel | 0x00590BBE | (sibling) | (TBD) |
| GetProgressionManager | 0x00590BC7 | (sibling) | (TBD) |
| GetPrimaryAssetIdFromClass | 0x000374D8 | (UAssetManager method) | (TBD) |
| IsValidPrimaryAssetId | 0x000376A3 | (UAssetManager method) | (TBD) |

UFunction at 0x16AC8904A90 has Outer = 0x016ACDFE1F00, whose NamePrivate
CmpIdx is 0x0058FEC9 — matches the UMissionsModel UClass name
(mm1/mm2 NamePrivate had low bytes 0x58FEC9). **DEFINITIVE: these are
native methods on UMissionsModel.**

Disasm of native Func at 0x7FF664B75A20 shows a standard UHT-generated exec
thunk pattern (read FPrimaryAssetId from FFrame, call inner impl, write
result). The actual impl is called at **0x7FF664DB5E30 (RVA +0x56E5E30)** —
next session: disasm that to identify which TArray/TMap on UMissionsModel
these methods iterate.

### The fix is now well-scoped

Once we know which field GetActiveMissionModel reads from inside UMissionsModel,
we can populate THAT field via `usmapdump poke`. With our existing pool
registrations and DynamicMissionPools data intact, the chain should resolve
end-to-end and the categories should render.

Candidate target fields on UMissionsModel:
- 3 empty TMaps at +0x30 / +0x80 / +0xD0 (one likely MissionPoolAssets)
- 3 TArrays at +0x120 / +0x130 / +0x140 (populated only on mm2)
- The hash-data region at +0x160

If GetActiveMissionModel iterates a TArray<UMissionModel*> looking for one
whose `PoolId` field matches the input, that TArray is the populate target.
If it does a TMap lookup keyed by FPrimaryAssetId, that TMap is the target.

Disasm of 0x7FF664DB5E30 will answer which.

### F1-F3 (2026-06-29 late) — Root cause finally landed: NO UMissionModel instances exist

Disasm of helper 0x7FF664DBA410 (the function called by GetActiveMissionModel
inner impl 0x7FF664DB5E30) reveals the FULL data structure:

```
UMissionsModel + 0x30 = TSparseArray/TSet of entries
  Each entry: 32-byte stride
  Entry[+0x10] = UMissionModel*  (pointer to mission UObject)

UMissionModel + 0x40, +0x48 = FPrimaryAssetId (PoolId)
UMissionModel + 0xB8, +0xB9  = byte flags (active/claimable bool checks)
```

The helper:
1. Iterates TSparseArray at this+0x30 using TBitArray.AllocationFlags
2. For each allocated entry: read UMissionModel* at +0x10
3. Compare missionObj+0x40,+0x48 against input FPrimaryAssetId (16 bytes)
4. If match: append to output TArray<UMissionModel*>
5. Caller (GetActive/GetClaimable) then filters by flag at +0xB8 / +0xB9

**Verified mm1 AND mm2 BOTH have empty TMap at +0x30** — even the
"populated" mm2 has zeros except for the HashSize=0x80 / FirstFreeIndex=-1
sentinels. So GetActiveMissionModel/GetClaimableMissionModel ALWAYS
return null regardless of which UMissionsModel the modal queries.

**Definitive root cause**: NO UMissionModel UObjects exist anywhere in
the process. `findptr` on UMissionModel CDO vtable (0x7FF66817DC10)
returns ONLY the CDO at 0x16AC8BFA4E0 — NO live instances.

Confirmation FNames found in NamePool (all native):
- `MissionModel` (id 0x0058FE9D)
- `CreateMissionModelFromFinalProgress` (0x0058FEE1) — the factory function
- `OnPSMissionsUpdated` (0x0058FF4F) — event fired when server sends mission data
- `OnLocalMissionsInitialized` (0x0065754A) — local init event

**The chain that's broken**:
```
Server sends mission list (we don't serve)
  -> Client's PlayerState/MissionsModel receives data
  -> OnPSMissionsUpdated fires
  -> Each mission becomes UMissionModel via CreateMissionModelFromFinalProgress
  -> Stored in UMissionsModel.TMap at +0x30
  -> GetActiveMissionModel/GetClaimableMissionModel can find them
  -> Modal renders
```

Without the server-side mission delivery, the entire chain stalls at
the first step. No HTTP `/missions` paths in the binary (likely delivered
via WebSocket messenger).

### The realistic fix paths

1. **Server-side mission delivery in `ags`** — implement whatever
   message/endpoint the client expects to trigger `OnPSMissionsUpdated`.
   Likely a WebSocket push message after login.
   Scope: 1-2 sessions of network capture analysis + server impl.

2. **Client-side shim that fabricates UMissionModel objects** — call
   `CreateMissionModelFromFinalProgress` via APC with synthetic args,
   populate the TMap manually. Substantial — needs:
   - Address of `CreateMissionModelFromFinalProgress` UFunction
   - Synthetic input data (mission ID, pool ID, flags, etc.)
   - TMap insertion (UE5 TMap requires hash recompute on insert)

3. **Accept the limitation** — modal stays empty at the menu. The rest
   of the menu works.

The diagnostic phase is DEFINITIVELY complete. We know:
- The exact data structure
- The exact field offsets
- The exact function chain
- The exact missing piece (UMissionModel UObjects from the server)

The fix is purely engineering scope, with two clear paths above.

### G1-G2 — Server-side delivery probe: HTTP path is NOT the mechanism (2026-06-29)

Tried enriching `PUT /progression/players/{id}/mission` response with a full
MissionData payload including `Pools: TMap<FPrimaryAssetId, PoolEntry>`,
`NewMissionTime`, `MillisUntilNewMission`, and per-pool fields matching the
MissionData FName cluster in NamePool block 96. User restarted the game; the
first PUT after login (04:30:46) received our enriched response.

**RESULT: NEGATIVE.**
- Modal renders identically empty post-restart.
- DateTime "year 0" warnings CONTINUE firing in Loki.log AFTER our enriched
  response. If our `NewMissionTime` value were being consumed those warnings
  would stop. They don't — meaning the response payload is parsed cleanly
  (no Deserialization failure) but NOT read into UMissionsModel.
- ZERO `LogPlatformMissions` entries in Loki.log — there is no Loki
  PlatformService-style mission manager that fetches via HTTP at login
  (compare: `LogPlatformInventory`, `LogPlatformStorefront` ARE logged).
- ZERO LogJson / LokiPlatformQuery warnings on our `/mission` endpoint.

Searched binary for HTTP mission paths: only `/mission`, `/mission/`, and
`/mission/rewards/claim`. NO `/missions/list` or similar GET-list path
exists. Searched for `UpdateMissions` / `RefreshMissions` functions: 0 hits
in the binary's exported wstrings.

**Architectural conclusion**: missions are NOT delivered via HTTP. The only
mechanism that populates UMissionsModel is `OnPSMissionsUpdated`, which
fires from **UE Network Replication on the LokiPlayerState_Missions
actor**. That actor exists only during gameplay (CDO-only at menu,
confirmed via findptr both pre- and post-restart).

The original architecture: missions get rolled by a real backend on a
schedule (daily/weekly cron). When a player connects, a UE dedicated
server holds their PlayerState with mission data; the data replicates
to the client on session join. The Missions modal reads from
UMissionsModel, which is populated by these replication events.

**Implications**: implementing the mission flow requires either:
1. A UE 5.4 dedicated server build that holds player session + replicates
   missions to the client. MASSIVE scope — would require the original
   game's server code or a custom impl of LokiPlayerState_Missions
   replication.
2. An in-process shim that constructs UMissionModel UObjects via
   NewObject<>() and inserts them into the TSet at UMissionsModel+0x30.
   Substantial — UE TSet/UObject manipulation externally is non-trivial
   (bit-array allocation flags, hash table, GUObjectArray entries all
   must be properly maintained).
3. Accept the limitation — modal stays empty; rest of menu works.

### Validates the user's hypothesis

The user's intuition that "the menu blocker is server-side" is CORRECT at
the architectural level. Missions, hero ownership, store offers, and the
cosmetics browser all expect data delivered via mechanisms (PlayerState
replication, asset registration via cooked manifests) that require server
infrastructure or content-pipeline work the original devs controlled.
Without that infrastructure, these systems will remain empty regardless of
HTTP response shapes.

The 5 categories DO get created. The lookup chain IS intact. The pool
references ARE wired in BP defaults. The blocker is at one specific point:
**no UMissionModel UObjects exist in the process because none were created
via the only mechanism the engine supports** (PlayerState replication of
mission data, requiring a UE dedicated server).
