# Next session kickoff — Milestone 3 / LokiAssetManager direct-registration route

> Paste the fenced block below into a new Claude Code session to continue.
> The memory file
> `C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\memory\supervive-milestone3-trackb-status.md`
> is auto-loaded; this prompt is a focused starting kit for the next concrete step.

```
We're continuing the SUPERVIVE Revival project on branch
claude/assetregistry-primary-assets-w7pljz. The full AR-repack route (loose-file,
mod-pak + sig-bypass, then runtime FPakPlatformFile::Mount) has been pursued to
exhaustion and is documented as closed at the architectural level in
docs/trackb-assetregistry-route.md (Loki uses per-chunk FPakPlatformFile design,
no master singleton exists, no runtime add-pak path).

The user has chosen to PIVOT to RE'ing LokiAssetManager directly. Goal: bypass
LokiAssetManager's manifest-only registration limit by calling the underlying
UAssetManager registration methods (specifically AddDynamicAsset, virtual on
UAssetManager) directly from a shim with our own crafted FPrimaryAssetId +
FSoftObjectPath + TArray<FName> data for the 16 missions + 25 heroes + 25
cosmetics bundles etc.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status                  # cert/log dirty is normal
  git log --oneline -10        # confirm last commit "usmapdump vtslot..."
  # Then read:
  #   docs/lokiassetmanager-vtable-dump.md  (★ this session's primary output)
  #   docs/hero-roster-attempts.md          (full context on what's been tried)
  #   docs/trackb-assetregistry-route.md    (option-1 closure analysis)
  # (memory file is already in your context)

THE PLAN: identify UAssetManager::AddDynamicAsset's RVA + vtable slot, then
build a shim that calls it directly to register our primary assets.

★ KEY DATA FROM PRIOR RE (all stable per build):
- module size: 0xA9E1000 (~170 MB), base 0x7FF65F6D0000 (ASLR happens to repeat
  this base reliably; treat as not-stable in general, derive from module info).
- LokiAssetManager UClass vtable: module-RVA **0x888CB78**.
  - 79 unique fn ptrs in 128 slots.
  - Slot 47 (RVA 0x12CC100): 8-reg-save prologue, likely StartInitialLoading.
  - Slots 88-127 ALL in RVA range 0x34Axxxx-0x34Dxxxx — the LokiAssetManager.cpp
    compilation unit (where ScanPrimaryAssetTypesFromConfig at +0x34D0807 also
    lives, as a non-virtual helper).
- UAssetManager::ScanPrimaryAssetTypesFromConfig: +0x34D0807. Called externally
  via APC reaches the game thread but crashes at __report_gsfailure
  (stack cookie / engine-state precondition). Not viable for direct invocation.
- GGameThreadId slot: module-RVA **0x9D49158** (uint32 holding main TID).
- Manifest consumer keys registered type by MAP NAME only, ignoring per-entry
  PrimaryAssetType (verified via Mission Probe #2). So manifest can ONLY carry
  the 11 named types: Heroes, Items, Emotes, PlayerTitles, HeroCosmeticsBundles,
  StoreOffers, SlotCosmetics, Minions, GameAugments, Equipment, Powers. Missions
  and MissionPools have NO map → unregisterable via manifest.
- AngelScript bindings (Loki/Script/Binds.Cache) expose only:
  AsyncLoadPrimaryAssets, GetLokiDataAsset, GetPrimaryAssetIdList,
  PrimaryAssetIDFromString, path getters. NO scan/register trigger.
  Scripts are precompiled (.Cache, no source, no shipping compiler) so
  script-side modification isn't viable.

CONCRETE NEXT STEPS:

1. **Find AddDynamicAsset's RVA.** UE source has UAssetManager::AddDynamicAsset
   as a virtual method. Try string anchors:
     usmapdump strings  SUPERVIVE-Win64-Shipping.exe "AddDynamicAsset" 5
     usmapdump wstrings SUPERVIVE-Win64-Shipping.exe "AddDynamicAsset" 5
   If found in-module, xrefstr against the log struct (typically -0x20 from
   string) to find the function's UE_LOG site. Walk back to MSVC prologue.

   Fallback if no string anchor: AddDynamicAsset is short (~50 lines in UE
   source). Look for the function via the call graph — anything that adds an
   entry to the AssetTypeMap or RegisteredPrimaryAssets array.

2. **Match RVA to vtable slot.** Cross-reference the AddDynamicAsset RVA against
   docs/lokiassetmanager-vtable-dump.md. If found at slot N, that's the vtable
   slot for the direct call.

   If NOT found in our 128-slot dump, extend the dump:
     usmapdump vtdump SUPERVIVE-Win64-Shipping.exe 0x7FF6XXXFCB78 256

   (Compute the abs addr live from current module base.)

3. **If AddDynamicAsset turns out to be NON-virtual** (called directly within
   UAssetManager), we can still call it by absolute RVA without going through
   a vtable. Just need the entry RVA.

4. **Find LokiAssetManager singleton** (proven mechanism from earlier RE):
   scan committed MEM_PRIVATE for an object whose [+0] == module_base+0x888CB78
   AND [+0x0C]&0x10==0 (excludes CDO). Take the first hit.

5. **Build the shim** — extend tools/sigbypass-mod/mount_shim.cpp or write a new
   file `tools/sigbypass-mod/registration_shim.cpp`. The shim should:
   - Find the singleton via vtable-A scan (above).
   - Construct an FPrimaryAssetId for each asset to register. Layout (from UE
     source): struct { FName PrimaryAssetType; FName PrimaryAssetName; } = 16
     bytes. Each FName is 8 bytes (uint32 ComparisonIndex + uint32 Number).
     Need to construct FNames for our types ("Mission", "MissionPool", "Hero",
     etc.) and names (per-asset). FName construction requires the NamePool,
     which usmapdump can locate via `names` command — but constructing new
     FNames live requires calling FName::FName(TCHAR*), itself a function we'd
     need to find.
   - **EASIER**: use existing FNames already in the pool. All our type/name
     strings (Mission, MissionPool, DA_Mission_*, Hero, etc.) are ALREADY in
     the NamePool because they're cooked asset names. Just look up their FName
     IDs via the existing `usmapdump names` + ID lookup machinery.
   - Construct an FSoftObjectPath: (FTopLevelAssetPath + FString SubPath). The
     FTopLevelAssetPath is 2 FNames (PackageName + AssetName).
   - Construct an empty TArray<FName> for Bundles.
   - Invoke AddDynamicAsset(singleton, &id, &path, &bundles).
   - Queue via APC on game thread (proven: TID from GGameThreadId slot at
     +0x9D49158).

6. **Verify** — relaunch + sign in + open Missions modal. Look for the
   `Invalid Primary Asset Type` warnings going away + new `ChangeBundleState`
   activity for the registered IDs + visible mission entries.

KILL CRITERIA:
- AddDynamicAsset isn't findable via string anchors AND isn't recognizable in
  the vtable dump's unique slots → fall back to disassembling each LokiAsset
  Manager-region slot (88-127) individually to identify by behavior. Slow but
  tractable.
- AddDynamicAsset crashes when called from worker/APC (like
  ScanPrimaryAssetTypesFromConfig did) → try ScanPathForPrimaryAssets or
  RegisterSpecificPrimaryAsset as alternatives. If all crash, the engine-state
  precondition issue is endemic to UAssetManager methods in this build's RE
  context. Pivot to in-memory FAssetRegistry patch (Approach C in
  docs/lokiassetmanager-vtable-dump.md).
- Registration succeeds + IDs appear in AssetManager state but the UI STILL
  doesn't show entries → the UI enumeration uses a DIFFERENT mechanism than
  UAssetManager's RegisteredPrimaryAssets. Would need to RE the UI's
  enumeration code (e.g., WBP_UI_MissionModal_C's data binding). Substantial.

TOOLING (all built + committed; relaunch tools as needed):
- tools/usmapdump — full RE toolkit: info, names, objects, strings, wstrings,
  xrefstr, callxref, findptr, peek, disasm, vtslot, vtdump, threads,
  findgametid, assetmgr. Build: `go build -trimpath -o usmapdump.exe .`
- tools/inject — manual-map injection: mmap, launch, watch-now, probe, diag.
  Build: `go build -trimpath -o inject.exe .`
- tools/sigbypass-mod/mount_shim.cpp — reusable worker+APC+marker framework.
  Build: `clang++ -shared -O2 mount_shim.cpp -o mount_shim.dll -lkernel32`.
- tools/sigbypass-mod/race-mount-suspended.ps1 — full launch orchestrator
  (sets env + suspended-launches + injects). Reusable as template.
- docs/mount-shim-marker.txt — diagnostic output (overwritten per run).

LAUNCH SEQUENCE:
- Steam MUST be running first (else Auth Failure 14005).
- From elevated PowerShell:
    cd "G:\git\Supervive Revival Project"
    .\tools\sigbypass-mod\race-mount-suspended.ps1
  (This is the proven sequence; auto-handles env + suspended launch + DLL
  inject + marker tail. Works without sign-in for pure recon.)

CONSTRAINTS:
- Continue on branch claude/assetregistry-primary-assets-w7pljz.
- Commit + push each meaningful step.
- Memory file is the canonical state record — update with every concrete
  finding (in-process addresses are NOT stable across launches, only RVAs).
- Game tends to crash 5-15 minutes into a session with the shim active;
  budget for 2-3 relaunches per major exploration.
- Address probes that are pure reads (no mutations) can run external via
  usmapdump — much safer than in-process shim work for diagnostics.

LARGER CONTEXT REMINDER:
Even successful registration via AddDynamicAsset may not surface anything in
the UI. The Mission Probe #2 (2026-06-28) analysis suggests the UI's missions/
heroes/store/cosmetics widgets enumerate via a path that bypasses
RegisteredPrimaryAssets entirely — querying the AssetRegistry directly,
maybe filtering by AssetClass. If that's true, calling AddDynamicAsset adds
entries to UAssetManager's internal state but doesn't help.

In that case the route closes at the UI layer, and the only remaining
avenues would be: (a) RE the WBP_UI_*_C blueprint widgets directly to
understand their data source; (b) in-memory FAssetRegistry patch to add the
AssetData entries to where the widgets actually look. Both substantial.

This is documented up-front so we don't sink time into AddDynamicAsset
without acknowledging the downstream kill-criterion risk.
```

## Quick verification commands (run at session start)

```pwsh
cd "G:\git\Supervive Revival Project"
git log --oneline -10

# Confirm tooling is built:
cd tools\usmapdump
"$env:ProgramFiles\Go\bin\go.exe" build -trimpath -o usmapdump.exe .
cd ..\inject
"$env:ProgramFiles\Go\bin\go.exe" build -trimpath -o inject.exe .
cd ..\sigbypass-mod
clang++ -shared -O2 mount_shim.cpp -o mount_shim.dll -lkernel32

# Launch (need elevated shell):
cd "G:\git\Supervive Revival Project"
.\tools\sigbypass-mod\race-mount-suspended.ps1
```

## Recap of where we are (commit history this branch)

```
45ce682 usmapdump vtslot: ICF hypothesis falsified; option 1 architecturally closed
25d1b86 Mount call-graph: Initialize is the actual entry; wrapper is dead code
24f1c68 Option-1 shim execution: per-pak architecture vs. singleton model
ce2898d Option-1 shim: mount_shim.cpp + race-mount-suspended.ps1
bb3850f Mount ABI corrected: wrapper takes dir + *.pak mask, not single pak file
ca60a00 Option-1 vtable identification: FPakPlatformFile singleton-finder ready
33b83eb Option-1 live recon: Mount + AR-reload anchors landed
c3109a4 Close option 3 (sig-bypass flag hunt): no CVar strings in this build
```

Plus the new commit landing this session (LokiAssetManager vtable dump + analysis).
