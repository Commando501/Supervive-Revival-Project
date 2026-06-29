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

**Approach A — Find AddDynamicAsset and call it directly.** UE source has:
```cpp
virtual void UAssetManager::AddDynamicAsset(
    const FPrimaryAssetId& AssetId,
    const FSoftObjectPath& AssetPath,
    const TArray<FName>& Bundles
);
```
This is a virtual method in UAssetManager. It SHOULD be in our vtable dump. To
identify:
1. Search the live process for `"AddDynamicAsset"` ANSI/wide string (likely emitted
   by an UE_LOG inside the function or a TRACE scope name).
2. xrefstr the string addr to find the LEA + enclosing function.
3. Match the function's RVA to one of our 128 vtable slots — that slot index is
   AddDynamicAsset's vtable position.

Then build a shim that:
1. Finds LokiAssetManager singleton (proven mechanism from prior `scan_shim`).
2. Calls vtable[slot] with crafted args:
   - FPrimaryAssetId: 16 bytes, (FName Type, FName Name)
   - FSoftObjectPath: 24 bytes, (FTopLevelAssetPath + FString SubPath)
   - TArray<FName>: 16 bytes (Data ptr, Num, Max)
3. Loop over all 16 missions + 25 heroes + 25 hero cosmetics bundles + N
   store offers etc.

If AddDynamicAsset doesn't have stack-cookie / engine-state preconditions like
ScanPrimaryAssetTypesFromConfig did, it should work cleanly.

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
