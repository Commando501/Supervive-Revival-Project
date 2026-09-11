# Session 43 pickup prompt — the hero grid is a TIMING problem now, not a mystery

Repo: `G:\git\Supervive Revival Project` — branch `dedicated-server-stub`.
Copy this whole file into a fresh Claude session's first message.

## TL;DR of where we are

Session 42 was a breakthrough session that **overturned the ~20-session
misdiagnosis** and built a **working fix at the AssetManager layer** — but hit a
last-mile **timing wall** so the ALL HUNTERS grid is still visually empty.

What is now PROVEN (all from live-process reads + a working injected payload):

1. **The dedicated-server-stub path was a detour for this goal.** The NORMAL
   client (no stub) reaches a rendered main menu fine — **no D3D12 crash**. That
   crash is specific to the dedicated-server-stub path (client-as-netclient). The
   plain client already sits at the (empty) menu. So we do NOT need the stub to
   reach/populate the menu.
2. **The old root cause was WRONG.** The live LokiAssetManager has **30
   primary-asset types registered** in its AssetTypeMap, INCLUDING every grid type
   (Hero, Mission, MissionPool, StoreOffer, HeroCosmeticsBundle, Emote,
   PlayerTitle, Item, LobbyPlatform, SlotCosmetics, ...). The scan is NOT bypassed;
   the manager DOES consult the AssetRegistry.
3. **The in-game AssetRegistry is FULL** — 103,841 FAssetData entries (= the baked
   `AssetRegistry.bin` count), including all 25 heroes ALREADY correctly tagged
   (`NativeParentClass=/Script/Loki.LokiHeroAsset`, `PrimaryAssetType=Hero`,
   `PrimaryAssetName=<Hero>`). So the AR content is right; no AR-patch is needed.
4. **The real root cause:** LokiAssetManager registers each type's *Info* (from the
   `PrimaryAssetTypesToScan` config, which HAS all 32 types) but **never runs the
   directory-scan/AR-query that fills each type's per-type AssetMap** — it relies on
   the sparse content-service manifest (ags, ~1175 assets) instead. So every
   per-type AssetMap is empty → `GetPrimaryAssetIdList(Hero)` returns 0 → empty grid.
5. **The fix WORKS at the AssetManager layer.** `tools/sigbypass-mod/scan_shim.cpp`
   (injected into the live game, non-elevated `inject mmap`, no anti-cheat
   interaction) calls `UAssetManager::ScanPathsForPrimaryAssets` on the game thread
   for all 30 types → **Hero AssetMap goes 0 → 25**, every type registers, NO crash.
   Repeatable.

## The remaining wall (this is Session 43's target)

**Populating the AssetManager does NOT populate the grid, because of TIMING.**

- The menu builds its hero catalog **at menu-load** — `ChangeBundleStateForPrimaryAssets`
  fires ONCE at LVL_LobbyV2 load (and fails: "failed to find NameData", because the
  per-type AssetMaps aren't populated yet).
- Opening the HUNTERS screen does **NO** re-query (zero AssetManager/enumeration log
  activity) — it just displays the catalog built once at menu-load and cached.
- So a **post-menu** scan is too late: the empty catalog is already built. Verified
  end-to-end this session — scanned (Hero=25) BEFORE opening HUNTERS the first time,
  opened it, grid STILL empty (zoom-confirmed: header + role-filter icons, zero tiles).
- The enumeration functions (`GetPrimaryAssetIdList`, `GetPrimaryAssetDataList`,
  `ChangeBundleStateForPrimaryAssets`, ...) are all STOCK/inherited (verified via
  vtable diff), so the catalog WOULD contain 25 heroes IF the types were registered
  BEFORE menu-load's ChangeBundleState.

**The fix must make the scan run in the window AFTER `StartInitialLoading` registers
the types but BEFORE menu-load builds the catalog.**

We tried EARLY injection (`inject watch-now`, mmap at process start; the shim polls
for the populated AssetTypeMap then scans). The shim found the manager (typemap
num=30) but the game **CRASHED** (Sentry crashpad) before the scan APC fired, during
hero GameplayCue loading (ShieldBot.Dash / Flash / Hook / HookGuy.Charge) +
InvalidateAllWidgets. The scan APC never fired ([apc] FIRING absent), so the scan did
NOT cause it — it's the game's own early-init fragility, likely aggravated by
manual-mapping into the still-unpacking process. NOT anti-cheat, NOT a scan crash.

## Read these first, in order

1. `CLAUDE.md` — project rules, launch gotchas, DO-NOT list.
2. `memory/supervive-hero-roster-blocker.md` — top of file has the ⚠️ OVERTURNED
   root-cause note + the full Session 42 Step 4→9 chain. This is the living log.
3. `docs/session-42-step9-grid-timing.txt` — **THE key doc.** The timing wall, the
   early-injection crash, and the three paths forward.
4. `docs/session-42-step8-FIX-WORKS.txt` — the AssetManager-level proof (Hero 0→25);
   read WITH the step-9 caveat (AssetManager populated ≠ grid populated).
5. `docs/session-42-step7-payload-design.txt` — the pinned scan address + all the
   offsets + the finalized payload logic.
6. `docs/session-42-step6-typemap-BREAKTHROUGH.txt` — the diagnosis-overturning reads
   (30 types registered, AR full 103,841, entries already tagged).
7. Supporting: `docs/session-42-step1..5-*.txt` (crash reframe, IoStore-dead, recon).

Auto-loaded memory already in context:
- `supervive-hero-roster-blocker.md` — Session 42 chain on top.
- `supervive-rpc-signature-solved.md` — ServerVerifyViewTarget (stub-path only now).

## Ground-truth offsets (this build; STABLE across launches — ASLR moves base only)

- `UAssetManager::ScanPathsForPrimaryAssets` = module **RVA +0x34CF9F0** (verified via
  vtable diff of UObject vs UAssetManager CDO vtables + disasm; it's the 1st new
  UAssetManager virtual, vtable slot 88, and LokiAssetManager INHERITS it — stock).
  Sibling `ScanPathForPrimaryAssets` (singular) = +0x34CF880.
- `LokiAssetManager` vtable = **RVA +0x888CB78** (VA base+0x888CB78 = 0x7FF68B30CB78
  in the S42 run). ⚠️ Earlier docs had a digit-drop typo "+0x88CB78" — WRONG, cost one
  inject iteration. It is **+0x888CB78**.
- `GGameThreadId` slot = **RVA +0x9D49158** (uint32; nonzero once engine thread runs).
- `AssetTypeMap` = **manager + 0x478** (TMap<FName, TSharedRef<FPrimaryAssetTypeData>>,
  30 entries, element stride 0x20: key FName @+0x00, value.obj (the
  FPrimaryAssetTypeData*) @+0x08). The CDO's typemap is num=0; the real singleton's is
  num=30 — that's how scan_shim picks the singleton.
- `FPrimaryAssetTypeData` layout: Type FName @+0x00, BaseClass UClass* @+0x30,
  scan-paths TArray<FString> @+0x70, **populated AssetMap @+0x178** (NOT +0x88 — that
  was a wrong guess; +0x88 is an unrelated empty field).
- Hero specifics: FName id **0x1A568**, BaseClass `/Script/Loki.LokiHeroAsset`
  (LokiHeroAsset UClass, name id 0x268F02), scan dirs `/Game/Loki/Characters/Heroes` +
  `/Game/Skunkworks/Characters/Heroes`.
- In-game AssetRegistry: `UAssetRegistryImpl` CDO holds the registry inline; asset map
  at CDO+0x38/+0x58 had Num=103,841. (Find CDO via `Default__AssetRegistryImpl`
  name id 0x5BB388.)
- **Re-find the manager singleton each launch** via `findptr` on the LokiAssetManager
  UClass (the non-CDO vtable-match), OR let scan_shim's vtable scan do it. Heap
  addresses from S42 (manager 0x1C6E6EBEE90, etc.) are per-ASLR — do NOT reuse.

## The working payload

`tools/sigbypass-mod/scan_shim.cpp` (+ `scan_shim.dll`, gitignored — rebuild it):
- Worker thread + game-thread APC framework (adapted from `mount_shim.cpp`).
- Polls `ScanForManager` (up to ~120s) for the singleton with a populated AssetTypeMap
  (num>0) — timing-robust so it works injected early OR late.
- On the game thread, iterates the 30-entry AssetTypeMap and per type calls
  `(+0x34CF9F0)(manager, *(td+0), td+0x70, *(td+0x30), /*bHasBP*/1, /*editorOnly*/0,
  /*forceSync*/1)` — args read straight from each type's Info block, constructs nothing.
- Marker log at `docs/scan-shim-marker.txt`.
- Build: `clang++ -shared -O2 scan_shim.cpp -o scan_shim.dll -lkernel32`
  (clang++ at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\...\usr\bin`).

## Session 43 plan (priority order)

### Path 1 (recommended): STABLE early injection into the pre-menu-load window
The scan must run after `StartInitialLoading` registers the types but before menu-load's
`ChangeBundleStateForPrimaryAssets` builds the catalog. `watch-now` (immediate mmap) is
too early and crashes the unpacking process. Options:
- **Fold the scan into `browse_hook.dll`** (`tools/sigbypass-mod/browse_hook.cpp`) —
  its early injection is PROVEN stable on the dedicated-server path (sessions 35-41).
  Add the same worker+APC+scan logic; it already survives early injection.
- OR use `inject watch <name> <dll> <RVAhex> <expectedHex>` gated on an init milestone
  (wait for a specific function's bytes to appear) so injection lands later than
  watch-now but before menu-load.
- OR delay scan_shim's worker start until a later init marker (e.g., poll for the
  AssetRegistry to reach 103,841 entries, or for a specific engine-init global).
Success = menu-load `ChangeBundleStateForPrimaryAssets` SUCCEEDS → catalog built WITH 25
heroes → grid shows hunters.

### Path 2: trigger a catalog REBUILD after a post-menu scan (avoids early injection)
Post-menu scan works cleanly. If we can force the menu to rebuild its hero catalog
(re-run the menu-load path that fires `ChangeBundleStateForPrimaryAssets`), the rebuild
would read the now-populated AssetMaps. Needs RE of the catalog-build trigger and a way
to re-invoke it (a level/menu reload, or calling the build function via injection).
Watch for: what fires `ChangeBundleStateForPrimaryAssets` at menu-load, and whether a
map reload (return to login → back to lobby) re-runs it.

### Path 3: confirm early-init crash cause
If early injection keeps crashing, confirm it's early-mmap fragility vs a genuine
hero-content-load crash (the game loading all 25 heroes' content at once). A stable
early injection (Path 1 via browse_hook) that survives would settle this.

### Strategic note to raise with the user
The AssetManager fix is real and the diagnosis is finally correct — this is now a
tractable timing/injection problem, not a mystery. But it IS still injection-based
(not a clean data-file fix), so any "populated grid" is a runtime mod that must be
re-injected each launch. If the user wants persistence, the end state is
browse_hook-with-scan injected every launch (or via the existing launch tooling).

## The live test cycle (Session 42, refined — memorize)

Steam must be running first (else Auth Failure 14005). Hosts file must have the two
SUPERVIVE-REVIVAL entries (accounts.projectloki + client-config, both 127.0.0.1). ags
backend on :8080 (HTTP) + :443 (HTTPS). Do NOT run `launch-redirect.ps1` (wiped hosts
in S31/S37). Certs/hosts were intact and login worked all through S42.

```powershell
# 0. Kill just the game (leave Steam + ags running)
Get-Process 'SUPERVIVE-Win64-Shipping',inject,crashpad_handler -EA SilentlyContinue | Stop-Process -Force

# 1. (Path 1) Start early injection BEFORE launching the client:
#    tools/inject watch-now SUPERVIVE-Win64-Shipping.exe <dll>   (too early — crashed in S42)
#    tools/inject watch     SUPERVIVE-Win64-Shipping.exe <dll> <RVAhex> <expectedHex>  (gated, later)
#    — or fold scan into browse_hook and inject that.
#    (Post-menu test instead: launch first, wait for stable menu, then `inject mmap <PID> <dll>`.)

# 2. Launch the NORMAL client (NO stub, NO positional 127.0.0.1:7777) via a .bat:
#    contents below. (This is launch-recon.bat — recreate in scratchpad.)
```

`launch-recon.bat` (normal client — the redirects only; NO stub URL):
```bat
@echo off
set EXE="G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
set AB=/Script/AccelByteUe4Sdk.AccelByteSettings
set LOKI=/Script/Loki.LokiGameProjectSettings
set LOCAL=http://localhost:8080
start "" %EXE% ^
  "-ini:Engine:[%AB%]:BaseUrl=%LOCAL%" ^
  "-ini:Engine:[%AB%]:IamServerUrl=%LOCAL%/iam" ^
  "-ini:Engine:[%AB%]:PlatformServerUrl=%LOCAL%/platform" ^
  "-ini:Engine:[%AB%]:BasicServerUrl=%LOCAL%/basic" ^
  "-ini:Engine:[%AB%]:LobbyServerUrl=ws://localhost:8080/lobby/" ^
  "-ini:Engine:[%LOKI%]:ProdPostAuthURL=%LOCAL%" ^
  "-ini:Engine:[%LOKI%]:ProdClientConfigURL=%LOCAL%" ^
  "-ini:Game:[%LOKI%]:ProdPostAuthURL=%LOCAL%" ^
  "-ini:Game:[%LOKI%]:ProdClientConfigURL=%LOCAL%" ^
  -log
```

Client log (READ for results): `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`
Scan-shim marker: `docs/scan-shim-marker.txt`

### Tooling notes
- `inject mmap <PID> <dll>` = manual-map into a RUNNING process — **non-elevated, no
  UAC needed** (confirmed S42). `watch-now`/`watch`/`launch` for early injection.
- `usmapdump` (read-only RPM, non-elevated): `nameid`, `objects`, `findptr`, `peek`,
  `disasm`, `vtdump`, `vtslot`, `strings`, `wstrings`. Used for all the RE above.
- Python `minidump` pkg + `capstone` installed. RPM readers (ctypes ReadProcessMemory
  + FNamePool resolver at `&Blocks[0]`) are far better than `usmapdump peek` for
  structural walks — recreate them in scratchpad (they're simple; see the S42 docs for
  the FName resolver and the AssetTypeMap/AssetMap offsets).
- The packer decrypts `.rdata` strings to HEAP only — string→function xref is dead;
  use vtable diffs (base CDO vtables) + disasm for function ID, not string xref.

## Computer-use for visual verification
The user can grant computer-use to screenshot the grid. Gotchas from S42:
- The game window is owned by process `supervive-win64-shipping.exe` — request access
  to that basename (not "SUPERVIVE"/Steam) or the screenshot masks the window.
- A transient Windows `Textinputhost` overlay intermittently steals frontmost and
  blocks clicks; retry, or add it to the allowlist.
- HUNTERS is the left-nav "HUNTERS" item; zoom the grid region (~[250,195,660,630]) to
  confirm tiles vs empty.

## What NOT to do
- Don't re-derive the root cause — it's settled (AR full, manager doesn't scan it into
  per-type AssetMaps; grid catalog built at menu-load). Don't reopen the backend /
  IoStore mod-pak / AR-patch routes — all dead or unnecessary (AR is already correct).
- Don't call `ScanPrimaryAssetTypesFromConfig` — documented `__report_gsfailure`
  crasher. Use `ScanPathsForPrimaryAssets` (+0x34CF9F0) — proven safe.
- Don't use `+0x88CB78` for the LokiAssetManager vtable — it's `+0x888CB78`.
- Don't propose C++-exception-using injection payloads (packer VEH kills them).
- Don't run `launch-redirect.ps1` (wiped hosts before).
- Don't assume post-menu scanning will fill the grid — it won't (timing wall). The scan
  must precede menu-load's catalog build.

## Wrap-up expectations
- Write a `docs/session-43-*.txt` evidence log.
- Update `memory/supervive-hero-roster-blocker.md` (top entry).
- Commit as you go (small single-purpose commits; the user commits per session).
- If early injection keeps crashing, say so plainly and give options rather than grind.

Good luck. The diagnosis is DONE and the AssetManager fix WORKS — this is the last
mile: get the scan to run before the menu builds its hero catalog.
