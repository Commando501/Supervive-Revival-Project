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
