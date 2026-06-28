# Next session kickoff — AssetRegistry.bin repack route

Use the fenced block below as the opening message of a new Claude Code session.

---

```
Read C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\memory\supervive-milestone3-trackb-status.md and docs/next-session-prompt.md first. We're picking up the AssetRegistry.bin repack route to unblock missions/hunters/store/cosmetics in SUPERVIVE. The native shim route was exhausted last session and is not to be re-attempted.

Brief summary of where we are:
- LokiAssetManager (custom UAssetManager subclass) registers primary assets ONLY from the content-service manifest's 11 named maps and never runs the standard config-driven directory scan. So baked primary assets (Mission, MissionPool, Hero, StoreOffer, Item, ...) never register — same single root cause behind the empty Missions modal, Hunters grid, Store, and Cosmetics.
- The cooked Loki/AssetRegistry.bin (36 MB, extracted to tools/extractor/out/AssetRegistry.bin) DOES contain every asset with its full class info and path. Grep confirms DA_MissionPoolDailyChallenge, LokiDataAsset_MissionPool, LokiDataAsset_Mission, BP_HeroAsset_Assault, etc.
- The native scan-call shim was built end-to-end in tools/inject/shim/scan_shim.cpp and got as far as running on the real game thread via QueueUserAPC — but the scan function crashes with __report_gsfailure (stack-cookie) even with empty config arrays. Further diagnosis requires an attached kernel debugger. Do NOT pursue.

This session's goal: modify AssetRegistry.bin so the missing primary-asset registrations happen during the game's NORMAL startup — no injection, just a data-file change. Smallest viable proof: get one daily mission to appear in the Missions modal after a relaunch.

Start by:
1. Reading the trackb-status memory file for full context.
2. Checking what AssetRegistry parsing already exists in tools/extractor/extractor/ (it's CUE4Parse-based; that library can already read AssetRegistry).
3. Inspecting the file format — version, header, where FAssetData entries live, and what tag/field marks an entry as a primary asset of a given type.

The full plan, file paths to read, constraints, and how-to-test instructions are in docs/next-session-prompt.md — read that document fully before starting work.

Game install is at G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\. Back up Loki\AssetRegistry.bin before any write to it. The launch script configs/launch-redirect.ps1 requires admin (the shell here is already elevated; no UAC needed). Memory file is the canonical state record — update it as findings land.
```

---

## Detailed reference for the next session (Claude: read this in full before starting)

### Why this approach

The full root-cause analysis from the prior session: SUPERVIVE's `Loki/AssetRegistry.bin` already contains every asset with its full class and path. UE5's standard `UAssetManager::ScanPathsForPrimaryAssets` matches assets to primary-asset types by directory + base class (NOT by a baked tag). So the data needed to register every primary asset is PRESENT in the registry. The blocker is that the game's custom `LokiAssetManager` registers primary assets ONLY from the content-service manifest's 11 named maps and NEVER runs the standard config-driven directory scan. The native shim approach to trigger that scan at runtime got as far as running on the real game thread via APC but the scan function itself crashes with a stack-cookie failure pattern — uncatchable without a kernel debugger.

The repack route sidesteps the runtime problem entirely. If we can encode the missing primary-asset registrations directly into `AssetRegistry.bin`, the game picks them up during its NORMAL startup — same code path that already works for the 11 manifest-driven types. No injection. No shim. Just a data file change.

### Confirmed facts (DO NOT re-verify; treat as ground truth)

- `AssetManagerClassName=/Script/Loki.LokiAssetManager` in `Loki/Config/DefaultEngine.ini`.
- `[/Script/Engine.AssetManagerSettings]` in `Loki/Config/DefaultGame.ini` declares the right `PrimaryAssetTypesToScan` entries (Hero/Mission/MissionPool/Item/Emote/StoreOffer/etc.) with `bShouldManagerDetermineTypeAndName=True`. So in stock UE this would Just Work; the override skips it.
- `ContentServiceContentManifest` has exactly 11 maps: Heroes, Items, Emotes, PlayerTitles, HeroCosmeticsBundles, StoreOffers, SlotCosmetics, Minions, GameAugments, Equipment, Powers. No mission map. Schema dump at `tools/extractor/out/schema_ContentServiceContentManifest.txt`.
- `ContentServicePrimaryAsset` schema: `{Str PrimaryAssetType, PrimaryAssetName, AssetPath, Status; Bool IsDefault}` (flat strings + one bool). Schema dump at `tools/extractor/out/schema_ContentServicePrimaryAsset.txt`.
- The manifest CONSUMER keys the registered PrimaryAssetType off the MAP NAME, not each entry's PrimaryAssetType field. This was confirmed by two probes from inside `handleContentManifest` in `server/internal/menu/menu.go`.

### What to do

1. **Read what already exists.** Walk `tools/extractor/extractor/` — it's a .NET 9 CUE4Parse-based tool. CUE4Parse has full `FAssetRegistryState` parsing. Check whether it can already deserialize `AssetRegistry.bin`. If yes, our path is: load the file via CUE4Parse, inspect the structure, modify entries in-memory, re-serialize. If not, we'll need to either extend CUE4Parse usage or write our own parser in Go (parallel to `tools/usmapdump`).

2. **Understand the format.** UE5 `FAssetRegistryState::Serialize` writes:
   - `FAssetRegistryHeader` (magic + version + flags + sub-counts)
   - Name table
   - Tag table (FAssetData tag map keys)
   - `TArray<FAssetData>` — each entry has `ObjectPath`, `PackagePath`, `AssetClass`, `Tags` map, `ChunkIDs`, `PackageFlags`. The `Tags` are FName→FString.
   - `TArray<FDependsNode>` — dependency graph
   - `TArray<FAssetPackageData>` — package-level metadata
   The header magic is `0x35DB1E54` ("hash of asset registry" or similar) in some versions; the actual constant lives in UE source.

3. **Confirm the registration mechanism.** Two competing hypotheses to test:
   - **(A) Tag-based**: a specific tag on `FAssetData` (e.g. `"PrimaryAssetType"`) makes the asset register as a primary asset of that type, regardless of the directory walk. Test by reading existing manifest-registered assets in the registry — if they have such a tag, this is the path.
   - **(B) Directory-walk-only**: primary-asset registration ONLY happens via the `PrimaryAssetTypesToScan` directory walk + per-asset `GetPrimaryAssetId()` call at runtime. In that case, the bin alone isn't enough; we'd need to verify whether the override actually skips the directory walk or whether it's running but finding nothing. We can test by checking whether ANY primary asset (e.g. a Hero) is registered via the directory walk in the current game session — if Hunters grid renders even without the manifest registering them, the walk IS running and we have a different problem.

4. **Round-trip first.** Build a parser that reads `tools/extractor/out/AssetRegistry.bin`, fully deserializes, then re-serializes to a different file. Hash-compare. This proves we understand the format completely before we modify anything.

5. **Smallest viable mutation.** Add the minimum to make ONE asset (e.g. `DA_MissionPoolDailyChallenge`) register as a `MissionPool` primary asset. Write to a copy. Replace the install's `Loki/AssetRegistry.bin` (BACK UP FIRST — there's only one copy at `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\AssetRegistry.bin`). Launch via `configs/launch-redirect.ps1`. Open the Missions modal. Read `%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log` for `LogAssetManager` lines. Success = no "Invalid Primary Asset Id MissionPool:DA_MissionPoolDailyChallenge" error AND the modal shows the daily mission.

### Files / locations you'll need

- `tools/extractor/out/AssetRegistry.bin` — safe working copy
- `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\AssetRegistry.bin` — game install (BACK UP BEFORE TOUCHING)
- `tools/extractor/extractor/` — CUE4Parse-based extractor
- `tools/extractor/out/DefaultGame.ini` — full `PrimaryAssetTypesToScan` registry
- `tools/extractor/out/catalog/da/DA_MissionPool*.json` — all 16 mission pool assets dumped
- `tools/extractor/out/catalog/da/DA_Mission_*.json` — ~330 mission assets dumped
- `tools/extractor/mappings.usmap` — usmap if structured access needed
- `tools/inject/shim/scan_shim.cpp` — abandoned native shim, keep, do not touch
- Memory: `C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\memory\supervive-milestone3-trackb-status.md`

### Constraints

- Always back up `AssetRegistry.bin` before replacing the install copy. There's no second source.
- `configs/launch-redirect.ps1` requires admin; the elevated PowerShell tool in this session can run it directly. The hosts file briefly locks (Defender scanning); just wait ~15s and retry.
- After each game crash, ports 8080/443 sometimes stay bound; killing `ags.exe`/`go.exe` + a brief wait clears them.
- Each test cycle = ~1 minute (launch + reach menu + open modal + close).

### If you hit a wall

Save findings to the trackb-status memory file before pivoting. The most likely thing wrong with this plan is hypothesis (A) above — the manifest-driven path may use a totally different mechanism than `FAssetData` tagging, in which case the next-best path is to RE the manifest consumer's code path inside `LokiAssetManager` (RVA-relative, addresses already partially documented in memory) to learn what data structure it actually populates, then synthesize equivalent state directly via either a tiny VirtualProtect+memcpy from a SECOND shim attempt, OR by understanding what file the manifest gets persisted to and modifying THAT instead of `AssetRegistry.bin`.
