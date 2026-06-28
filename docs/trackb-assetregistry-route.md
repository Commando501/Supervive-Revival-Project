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

## Tooling — `tools/extractor` `assetregistry` subcommands

Implemented this session. Standalone reader — no paks, no `.usmap`, no Oodle.
Run from `tools/extractor/extractor`:

| Subcommand | Purpose |
|---|---|
| `assetregistry stats` | Class histogram + tag-key histogram. **Smoking-gun output**: if `PrimaryAssetType` / `PrimaryAssetName` appear in the tag-key list, the cooker already baked the metadata onto FAssetData entries — meaning the data IS in the registry and the runtime is the only thing not consulting it. If those keys are absent, the cooker stripped them and the route shifts to "add the tags ourselves". |
| `assetregistry classes` | Sorted list of every unique `AssetClass` string — grep-friendly. |
| `assetregistry inspect <needle>` | Full per-entry snapshot of every FAssetData matching `needle` across PackageName/PackagePath/AssetClass/AssetName. |
| `assetregistry candidates <needle>` | Same shape as inspect but matches ONLY on `AssetClass`. Output is the input for a future surgical-patch step. |
| `assetregistry namemap` | Dump the NameMap as `index : name` lines — needed to look up FName indices when authoring patches. |

Default `ar.bin` path: `tools/extractor/out/AssetRegistry.bin`. Pass an
explicit path as the second arg to point at the live game-install file
(`Loki/AssetRegistry.bin`) instead.

## Host-side workflow

```ps1
# Once: extract the cooked AssetRegistry.bin out of the pak. (User has already
# done this — file lives at tools/extractor/out/AssetRegistry.bin, 36 MB.)

# 1. Read what's actually in the registry. THE diagnostic step — look for
#    PrimaryAssetType / PrimaryAssetName in the tag-key histogram, count entries
#    per primary-asset-suggestive class, scan for LokiDataAsset_Mission etc.
cd tools\extractor\extractor
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry stats
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry classes
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry candidates LokiDataAsset_Mission
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry inspect DA_MissionPoolDailyChallenge

# 2. Decide which entries to flip (next session, after reading step 1's output):
#    pick ONE daily-mission FAssetData. Confirm its current AssetClass + tags.
#    Identify the FName index of the desired class (LokiDataAsset_Mission or
#    similar) in the NameMap dump.

# 3. (Future) Run the patch tool — writes a modified bin alongside the original.

# 4. Back up the live AssetRegistry.bin, drop the modified one in place:
Copy-Item "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\AssetRegistry.bin" `
          "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\AssetRegistry.bin.bak" -Force
Copy-Item tools\extractor\out\AssetRegistry.patched.bin `
          "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\AssetRegistry.bin" -Force

# 5. Relaunch via configs/launch-redirect.ps1 (elevated). Watch:
#    - %LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log — LogAssetManager / LogProgression*
#    - Did "Invalid Primary Asset Type :  ChangeBundleStateForPrimaryAssets failed" clear?
#    - Did OnLocalMissionsInitialized fire?
#    - Open the Missions modal — does ONE mission appear?
```

## Kill criteria

- If `assetregistry stats` shows **no** primary-asset-suggestive class entries
  for Mission / MissionPool / Hero / StoreOffer — the cook is publishing
  zero of the expected baked types and this route can't work without a
  significantly bigger edit. Revisit the manifest-injection approach instead.
- If a one-mission patch lands but `LogAssetManager` STILL warns "Invalid
  Primary Asset Type", it confirms LokiAssetManager's bypass is total — it
  truly never consults AssetRegistry, regardless of what's in it. Route is
  closed; revisit the original native-shim plan with a different injection
  point (e.g., hooking the manifest fetch), not the GS-cookie-crashing
  primary-asset-scan call.
- If the patch lands and a daily mission DOES appear in the Missions modal,
  scale up: a similar patch for Hero / MissionPool / StoreOffer entries.

## Status (2026-06-28)

- ✅ Read-only `assetregistry` subcommands (stats, classes, inspect,
  candidates, namemap) — implemented this session in
  `tools/extractor/extractor/Program.cs`. Untested in this remote container
  (no .NET SDK available); the user runs them on their Windows box.
- ⏳ **Next step (this session or next):** user runs the four diagnostic
  commands above; outputs land in `tools/extractor/out/`. Findings either
  confirm the cook baked PrimaryAssetType tags (path A — flip one entry's
  class or tags to trigger registration), or it stripped them (path B —
  the patch needs to ADD tags, growing the FStore).
- ⏸️ Write path (`assetregistry apply-patch`) is intentionally deferred
  until path A vs B is known — the implementation differs by an order of
  magnitude (surgical 4-byte in-place vs. full FStore repack).
