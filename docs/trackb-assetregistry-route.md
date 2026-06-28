# Track B — AssetRegistry repack route

The Missions modal, Hunters grid, Store, and Cosmetics are all empty because
LokiAssetManager (a UAssetManager subclass) registers primary assets ONLY from
the content-service manifest's 11 named maps and never runs the standard
config-driven directory scan. So baked primary assets — `LokiDataAsset_Mission`,
`LokiDataAsset_MissionPool`, `BP_HeroAsset_*`, `BP_StoreOffer_*`, items,
cosmetic bundles — never register, and the UI receives nothing to display.

Last session's native-shim route reached the live game thread via QueueUserAPC
but crashed in `__report_gsfailure` (stack-cookie) inside the scan function
even with empty config arrays. Further diagnosis would need a kernel debugger
attached to the shipping process. **Not pursuing — closed route.**

This route: **modify `Loki/AssetRegistry.bin` so the primary-asset
registrations land during the game's NORMAL startup**. No injection. Just a
data-file change. Smallest viable proof = one daily mission visible in the
Missions modal after a relaunch.

## File format (UE5.4, verified against CUE4Parse source)

`AssetRegistry.bin` is a standalone serialized `FAssetRegistryState`. With
`FAssetRegistryVersionType >= AddedDependencyFlags` (current shipping build),
the layout is:

1. **Header** — `FAssetRegistryVersion.TrySerializeVersion(Ar, out Version)`
   then `bFilterEditorOnlyData : bool` (since `AddedHeader`).
2. **NameMap** — `FNameEntrySerialized.LoadNameBatch(Ar)` (UE batched names:
   hashes block + per-entry lengths + UTF8/UTF16 string payloads).
3. **Tags FStore** (since `FixedTags`) — 11 nums header, then Texts +
   NumberlessNames + Names + (Numberless)ExportPaths + AnsiStrings +
   WideStrings + Numbered/Numberless pairs, framed by `BEGIN_MAGIC 0x12345679`
   / `END_MAGIC 0x87654321`. Aligned to 16 bytes (since
   `MemoryMappedTagDataStore`).
4. **`FAssetData[]`** — int32 length, then for each entry:
   - `PackagePath : FName`
   - `AssetClass : FTopLevelAssetPath` (two FNames: `PackageName + AssetName`,
     since `ClassPaths`) — pre-`ClassPaths` builds wrote a single FName.
   - `PackageName : FName`
   - `AssetName : FName`
   - `OptionalOuterPath : FName` (since `RemoveAssetPathFNames`, **skipped
     when `bFilterEditorOnlyData` is true** — typical for cooked builds, so
     usually absent).
   - **Tags+Bundles size header** — `ulong` packed: high bit (1<<63) =
     `bHasNumberlessKeys`; bits [32..47] = `Num` (pair count); low 32 bits =
     `PairBegin` (index into FStore's NumberedPairs / NumberlessPairs).
     **The actual K=V pairs are NOT inline** — they live in the FStore.
   - `FAssetBundleData` — int32 length, then per bundle:
     `BundleName : FName` + `BundleAssets : FSoftObjectPath[]` (each is one
     `FTopLevelAssetPath` + `FString SubPathString`).
   - `ChunkIDs : int32[]`
   - `PackageFlags : uint32` (EPackageFlags)
5. **Dependency block** — `int64 sectionSize`, `int32 numDependsNodes`,
   then per-node serialization (preallocate first, then `SerializeLoad`).
6. **`FAssetPackageData[]`**

### FName cell encoding (asset-data section only)

```
uint32 index;
if (index & 0x80000000) {          // AssetRegistryNumberedNameBit
    index -= 0x80000000;
    uint32 number;
}
return new FName(NameMap[index], number);
```

So an FName cell is 4 or 8 bytes on the wire. This is what makes surgical
in-place patches feasible — but a full repacker would have to track the
length delta of every FName field if any new strings need to enter NameMap.

## Tooling — `tools/extractor` subcommands

All in `tools/extractor/extractor/Program.cs`. Run from
`tools/extractor/extractor` via `& "$env:ProgramFiles\dotnet\dotnet.exe" run
-c Release -- <subcommand> ...`.

### Read-only diagnostics (no paks/usmap/Oodle needed for `assetregistry`)

| Subcommand | Purpose |
|---|---|
| `assetregistry stats` | Class histogram + tag-key histogram. **Smoking gun**: if `PrimaryAssetType` / `PrimaryAssetName` appear in the tag-key list, the cooker already baked the metadata onto FAssetData entries — meaning the data IS in the registry and the only question is whether the runtime consults it. |
| `assetregistry classes` | Sorted list of every unique `AssetClass` string — grep-friendly. |
| `assetregistry inspect <needle>` | Full per-entry snapshot of every FAssetData matching `needle` across PackageName/PackagePath/AssetClass/AssetName. |
| `assetregistry candidates <needle>` | Same shape as inspect but matches ONLY on `AssetClass`. |
| `assetregistry namemap` | Dump the NameMap as `index : name` lines — needed to look up FName indices when authoring patches. |
| `wherefile <pathNeedle>` | Reports which container (.pak / IoStore .ucas) backs each matching virtual path. Uses the full CUE4Parse provider, so needs Oodle. **Used to confirm AR.bin lives in a legacy .pak, not IoStore — which determined the writer format.** |

Default `ar.bin` path: `tools/extractor/out/AssetRegistry.bin`. Pass an
explicit path as `args[2]` to point at any other extracted bin.

### Write tooling

| Subcommand | Purpose |
|---|---|
| `assetregistry apply-patch --target <PkgNeedle>[:<AssetExact>] --to <Pkg>:<Asset> [--out <path>]` | Surgical 8-byte FName-cell flip of the AssetClass FTopLevelAssetPath on every matching entry. Walker mirrors CUE4Parse's reader byte-for-byte through the FAssetData array; cross-checks alignment via PackageName text. File length preserved. |
| `mkpak <inputFile> <virtualPath> <outputPak>` | Emit a UE legacy pak v11 containing one uncompressed, unencrypted file at `<virtualPath>`. Mirrors CUE4Parse `PakFileReader` format including the 221-byte footer (`OffsetsToTry.Size8a` — 5 compression-method slots, "Oodle" + 4 empty). Uses the ENCODED FPakEntry form (12 bytes for uncompressed < 4GB entry: bitfield `0xE0000000` + uint32 offset + uint32 size) — CUE4Parse 1.2.2 calls the byte\* ctor unconditionally for every dir-index entry, so non-encoded entries cause AV. |
| `peekpak <pakPath>` | Mount a pak directly via `PakFileReader`, print MountPoint + every file's path/size + extracted-bytes SHA1. Round-trip verification before deployment. |

## Diagnostic findings (2026-06-28)

`assetregistry stats` on the cooked 36 MB `Loki/AssetRegistry.bin`:

- 103,841 FAssetData entries, 191,396 NameMap entries, 98 unique AssetClass strings.
- **`PrimaryAssetType` and `PrimaryAssetName` are present on 16,158 entries each.**
  Mission family: `PrimaryAssetType="Mission"` on 660 entries, `"MissionPool"` on 32.
  Same shape for Hero / StoreOffer / Cosmetic / Emote / PlayerTitle families.
- Every primary-asset entry's AssetClass is stock UE `Blueprint` /
  `BlueprintGeneratedClass` (the actual class hides in `NativeParentClass` =
  `/Script/Loki.LokiDataAsset_MissionPool` etc.).
- NameMap contains every Loki class FName needed for class-flip patches:
  `LokiDataAsset_Mission`=190688, `LokiDataAsset_MissionPool`=190690,
  `LokiDataAsset_StoreOffer`=190717, `/Script/Loki`=1162, etc.

**Verdict: PATH A** — the cook baked everything. The patch is surgical 8-byte
overwrites of FName cells, file length preserved, no FStore rebuild needed.

## Patch tool — validated end-to-end

`assetregistry apply-patch` proven correct on the live `AssetRegistry.bin`.
Test patches landed via:

```ps1
cd tools\extractor\extractor
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry apply-patch `
    out\AssetRegistry.bin `
    --target DA_MissionPoolDailyChallenge `
    --to /Script/Loki:LokiDataAsset_MissionPool `
    --out out\AssetRegistry.stage1.bin

& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry apply-patch `
    out\AssetRegistry.stage1.bin `
    --target /Game/Loki/Core/Missions/Armory/ArmoryDailies/DA_Mission_ `
    --to /Script/Loki:LokiDataAsset_Mission `
    --out out\AssetRegistry.stage2.bin
```

Stage 2 contained 16 entries flipped (4 pool + 12 daily-mission), file length
preserved at 36,505,474 bytes. CUE4Parse re-inspect confirms the new AssetClass
values resolve correctly. **Tool works. Deployment is the bottleneck.**

## Deployment — two routes tried, both currently dead

### Route 1: drop the patched bin at a loose-file path — IGNORED by UE

The original plan assumed `Loki\AssetRegistry.bin` was a loose file in the
install; it isn't. The cooked AR.bin lives inside `pakchunk0-WindowsClient.pak`
(legacy pak format, confirmed via `wherefile`). Dropping the patched bin at
both `Loki\AssetRegistry.bin` and `Loki\Content\AssetRegistry.bin` produced:

- UE logs `LogAssetRegistry: Premade AssetRegistry loaded from
  '../../../Loki/AssetRegistry.bin'` — but this is just the virtual UFS path,
  not the data source.
- Every observable log metric (`Invalid Primary Asset` count, GameplayCue
  warnings, MissionModal categories) matched the pre-patch baseline EXACTLY.

Confirmed via **truncate kill-test**: overwriting both loose paths with 32
bytes of `0xDEADBEEF` garbage and relaunching — game booted normally with no
`HasBadVersionNumber` / `LowLevelFatal`, `FAssetRegistry took 0.0008 seconds
to start up` (same as a clean run). **Pak data wins over loose drops at this
path in shipping mode.**

### Route 2: build a mod pak with higher-priority chunk name — BLOCKED BY SIGNING

Wrote a UE pak v11 writer (`mkpak`), wrapped the patched AR.bin in
`pakchunk999-WindowsClient_P.pak` (the `_P` suffix is the standard UE patch-
priority convention), dropped it in `Loki\Content\Paks\`. Relaunch result:

```
LogPakFile: Display: Found Pak file ...pakchunk999-WindowsClient_P.pak attempting to mount.
LogPakFile: Display: Mounting pak file ...pakchunk999-WindowsClient_P.pak.
LogPakFile: Warning: Couldn't find pak signature file '...pakchunk999-WindowsClient_P.pak'
LogPakFile: Warning: Unable to create pak "...pakchunk999-WindowsClient_P.pak" handle
LogPakFile: Warning: Failed to mount pak "...pakchunk999-WindowsClient_P.pak", pak is invalid.
```

All 16 cooked paks ship with corresponding `.sig` files (RSA-signed SHA256
hashes of each pak chunk). The engine **requires** a valid `.sig` to mount
any pak. Without the developer's private key we can't generate a passing
signature. Static search of the on-disk exe for bypass strings
(`bRequireSignedPak`, `SkipPakSig`, `VerifyPakSignature`, etc.) finds
nothing — **the exe is packed**, so the relevant strings only exist in the
running process's unpacked memory (per prior native-shim RE: module RVAs
become stable once unpacked at process load).

## Signature-bypass research (option 1, next attempt)

Three options to unblock Route 2, ranked by effort:

1. **Find a signature-bypass CVar in unpacked memory** via `tools/usmapdump`
   (RPM + xref + strings infrastructure already built). If UE has a runtime
   flag like `Pak.bRequireSignedFile` somewhere, flipping it in memory before
   the mount check fires would let unsigned paks load. Procedure:
   - Use `tools/usmapdump strings <proc> <substr>` to find narrow-char and
     wide-char occurrences of `Couldn't find pak signature file` (the exact
     log message) in unpacked memory.
   - `tools/usmapdump xref <proc> <rva>` to find the code that emits it.
   - Walk back to the call site, identify any `mov reg, [rip+disp]` slot
     that holds a bool/flag the function reads; that's the candidate CVar.
   - Patch the slot or shim a one-time write before pak mount fires.
2. **Binary-patch `FPakFile::LoadSignatureFile`** call site to skip the
   check entirely. Same machinery, different target. Probably 1-3 byte
   patch at a stable module RVA.
3. **Hook the pak mount path** with a manual-mapped DLL that
   intercepts `FPakFile::Initializer` before signature check. Most
   complex; lowest priority.

## Kill criteria

- `assetregistry stats` shows **no** primary-asset-suggestive class entries
  for Mission / MissionPool / Hero / StoreOffer → cook stripped the metadata,
  route can't work without a much bigger edit. ✅ NOT FIRED — see Diagnostic
  findings above; 16,158 entries carry these tags.
- A one-mission patch deploys but `LogAssetManager` STILL warns "Invalid
  Primary Asset Type" → `LokiAssetManager` never consults the AR for primary
  asset registration; route is logically dead even with a working deployment.
  ⏳ UNTESTABLE until pak signing is bypassed. The loose-file Test 1 result
  (zero log differential) is consistent with this prediction but isn't
  conclusive because the pak shadowed the loose file.
- A patched mission appears in the Missions modal → scale to other types.

## Status (2026-06-28)

- ✅ Diagnostic tooling (`assetregistry stats|classes|inspect|candidates|namemap`,
  `wherefile`) — implemented and proven.
- ✅ Patch tool (`assetregistry apply-patch`) — implemented, round-trip
  validated, file length preserved, CUE4Parse re-parses cleanly.
- ✅ Mod-pak writer (`mkpak`) — implemented, round-trip validated via
  `peekpak`. SHA1 of extracted bytes matches source for both a tiny test
  file and the real 36 MB patched AR.bin.
- ⛔ **Loose-file deployment** — proven inert (pak shadows it).
- ⛔ **Mod-pak deployment** — blocked by pak signature requirement.
- ⏳ **NEXT: signature-bypass research** via `tools/usmapdump` against the
  live process. Per the three-option ranking above. If option 1 lands a
  bypass, drop the mod pak again and we finally test the route's kill
  criterion; if it doesn't, options 2 and 3 are progressively more invasive
  but mechanically known-feasible.
