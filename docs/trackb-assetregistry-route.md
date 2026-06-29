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

## Signature-bypass attempt (option 1) — proven mechanism, ROUTE STILL BLOCKED

Built `tools/sigbypass-mod/` + `tools/inject` `launch`/`watch-now` subcommands
and ran the full chain end to end. **Patch lands correctly but ~50ms too late**
because the shipping exe's packer commits .text pages on demand via a page-fault
handler — the function's bytes only appear at the EXACT MOMENT the engine first
calls it, with no observable window between "appear" and "execute" from outside
the kernel.

### What works

- **UE4SS recon**: UE4SS is installed (`Loki\Binaries\Win64\ue4ss\` with
  `UE4SS.dll`, configs, multiple existing mods) but the dwmapi.dll proxy NEVER
  loads — the shipping exe's import directory is stripped (RVA=0); it imports
  only `preloader.dll` (the packer bootstrap). All UE4SS-based deployment is
  dead in this build.
- **Live-process RE** (`tools/usmapdump` strings/wstrings/xrefstr/findptr/
  callxref/peek/disasm): located the full pak-sig warning chain.
  - L"Couldn't find pak signature file" @ in-module RVA 0x79E17F0.
  - UE log-record struct (str ptr + file ptr + line + verbosity) @ +0x79E17C8.
  - Unique LEA loading the log struct into `rdx` @ +0x204836D.
  - Enclosing function (`FPakSignatureFile::Load`) entry @ +0x2047EE0
    (standard MSVC big-function prologue
    `40 55 53 41 54 41 55 41 56 41 57 48 8D 6C 24 F8`).
  - Direct callers via `callxref`: +0x2036560 (FPakFile ctor) and +0x2056624.
  - Both callers invoke the sig-load function UNCONDITIONALLY — no preceding
    `cmp/jz` gate that could be flipped.
- **Patch mechanism** (`tools/sigbypass-mod/main.cpp`): UE4SS-style C++ DLL
  that `VirtualProtect`s the page and overwrites the prologue with
  `B0 01 C3 90 90 ...` (`mov al, 1; ret` + NOP pad). Build with
  `clang++ -shared -O2 main.cpp -o main.dll -lkernel32`.
- **Injection** (`tools/inject` `mmap`): manual-mapping bypasses CIG, runs
  DllMain, sets up .pdata. ACG is OFF (`inject probe` confirms RWX alloc OK)
  so `WriteProcessMemory` + `VirtualProtectEx` work freely.
- **Suspended launch** (`tools/inject launch`): `CreateProcessW` with
  `CREATE_SUSPENDED` → manual-map inject while main thread paused →
  `ResumeThread(main)`. Tested end-to-end via
  `tools/sigbypass-mod/race-suspended.ps1`.

### Two correctness gotchas discovered (documented for future RE)

1. **Clang `__try/__except` hangs in manual-mapped DLL** when an AV fires —
   the SEH chain isn't set up the way Windows expects despite `.pdata` being
   registered. Workaround: use `VirtualQuery` to gate reads on
   `MEM_COMMIT` + readable protection instead of `__try`'ing them.
2. **DllMain MUST spawn a worker (not block in-line)** under `CREATE_SUSPENDED`.
   A synchronous spin in DllMain prevents `inject launch` from returning to
   `ResumeThread(main)` — the packer (which runs on main) never executes →
   prologue never appears → deadlock.

### Why the patch still doesn't work — empirical race timeline

```
T+0    ResumeThread(main); packer starts.
T+5ms  Packer unpacks .text near WinMain; engine init begins.
T+50ms Pak mount loop reaches pakchunk999_P; calls FPakSignatureFile::Load.
T+50ms CPU faults at +0x2047EE0; packer commits the page atomically;
       function executes with ORIGINAL bytes; returns failure.
T+51ms Pak rejected ("Couldn't find pak signature file → Failed to mount").
T+235ms Our worker thread finally sees the page as MEM_COMMIT + readable;
       VirtualProtect + memcpy; marker confirms `B0 01 C3 90 90 ...` is in
       place — but the function won't be called again, so the patch has zero
       observable effect.
```

Page commit and function execution are atomic from the engine's perspective.
There's no software-visible window for a co-resident patcher to interpose.

## Three remaining options — status

### Option 3 (flag hunt in unpacked memory) — CLOSED 2026-06-28

Ran the full live-process sweep against the shipping game at the main menu.
Substrate proven healthy by control probes (`peek +0x79E17F0` returns the
known wide string; `wstrings "LogPakFile"` and `wstrings "Couldn't find pak
signature file"` both hit at expected RVAs with two heap copies each).

Sweep across 13 candidate flag/CVar strings — **0 hits**:
- `Pak.SkipSignatureCheck`, `Pak.SignatureCheck`, `RequireSignedPak`,
  `bRequireSignedPak`, `SignedPak`, `GetPakSigningKeys`, `FPakSignatureFile`,
  `[Core.System]`, `Pak.RsaPublicKey`, `Pak.AlwaysVerify`, `bSigningEnforced`,
  `EPakSignatureCheckResult`, `AllowUnsigned`, `PakSigning` — all wide+narrow.

Sanity controls — **also 0 hits**:
- `Pak.MountReadOrderPriority` (vanilla UE CVar registered in
  `FPakPlatformFile::FPakPlatformFile`).
- `FAutoConsoleVariable` (the CVar registry class name itself).

The pak-related log strings exist in unpacked memory, but the CVar/flag name
strings do not — this build has its CVar registrations stripped (shipping-
build optimization). Even if a flag existed in this code path it would not be
findable via string search, and the standard `bRequireSignedPak` UE source
identifier produces zero ANSI or wide hits in the running module.

Deeper disasm of both callers of `FPakSignatureFile::Load` confirms prior
analysis: no caller-level bool/byte gate, return value treated as a struct
pointer and field-copied. Caller #2 (+0x2056624) has nearby conditionals but
they trace to **command-line parse-once sentinels and UE log-verbosity gates**
(the LEAs at +0x2056547 and +0x2056569 load the `CachePerPak`/`NewTrimCache`
wide strings in the same `.rdata` cluster as the sig warning) — not signing.

Any remaining gating logic lives inside the load function's failure path or
in a downstream consumer of the returned struct, both inside packer-managed
pages with the same atomic commit-and-execute property that defeated the
entry-point patch.

**Verdict: there is no string-named pak-signing flag to find in this exe.**
Option 3 in its original "find a flag, flip via WPM" form is impossible.

### Option 1 — next pursuit (live recon landed 2026-06-28)

**Hook `FPakPlatformFile::Mount` + call it from our worker AFTER patching**.
Mount the mod pak at RUNTIME instead of relying on startup mount. With the
sig-load function patched at the moment we trigger the call, the runtime
mount succeeds — and the AR reload happens FOR FREE via UE's delegate chain
(`FCoreDelegates::OnPakFileMounted2.Broadcast` → AR listener →
`ScanPathsSynchronous` on the new pak's paths). So we do NOT need a
separate AR-reload entry; one Mount call covers both halves.

**RVAs landed via live recon (stable across launches — only ASLR base
moves):**
- `FPakSignatureFile::Load` entry (sig-bypass patch target): **+0x2047EE0**
  — patch to `B0 01 C3` (`mov al, 1; ret`).
- `FPakPlatformFile::Mount` wrapper (2-arg public API): **+0x204FFD0** —
  constructs empty FString mountpoint, calls impl with 3 args. Simpler to
  invoke from the shim.
- `FPakPlatformFile::Mount` impl (3-arg, full body): **+0x2050020** — MSVC
  big-function prologue (sub rsp 0x120, security cookie at [rbp-0x10]).
  Args: rcx=this, rdx=pakName, r8=mountpoint FString*.
- Internal mount helper containing the OnPakFileMounted2 broadcast +
  timing UE_LOG: **+0x204F130** — 9-register-save prologue, 0x478 frame,
  cookie at [rbp+0x340]. Called from Mount impl. Confirms the delegate
  fires inside the mount path.
- `GGameThreadId` slot (for APC targeting): **+0x9D49158** (existing).

**Vtable + singleton-finder LANDED 2026-06-28** (second live run):
- `FPakPlatformFile::Initialize` entry: module-RVA **+0x204AAD0**. Verified
  twice: TRACE-name xref at +0x79E4FC8 AND UE_LOG format string at +0x79E4DF8
  reads literally "Initializing PakPlatformFile" (the message Initialize
  emits at entry).
- **FPakPlatformFile vtable A starts at module-RVA +0x79E0C78.** Slot 0 =
  deleting destructor at +0x203AE10. Dtor frees exactly **0x268 (616) bytes**
  — `sizeof(FPakPlatformFile)`, definitive class identification. Slot 11 at
  +0x79E0CD0 holds Initialize at +0x204AAD0.
- FPakPlatformFile vtable B (multiple-inheritance second base) at +0x79E0C80.
- Object layout: `+0x00` vtable A, `+0x08` refcount (uint32, observed 1 or 2),
  `+0x10` vtable B, `+0x18` Inner IPlatformFile ptr, `+0x20..` per-instance
  fields. Instance size 0x268; array stride 0x280.
- **10 instances** in heap (contiguous array). UE 5.4 vanilla has single
  inheritance + singleton — this build's MI + array pattern is a Loki-specific
  extension. Any of the 10 works for a Mount call (Mount is non-virtual, all
  instances share the global `FCoreDelegates::OnPakFileMounted2.Broadcast`).
- Singleton-finder: scan committed `MEM_PRIVATE` regions for a qword equal to
  `module_base + 0x79E0C78`. Validate hits via `[+0x08]` (small ref count) and
  `[+0x10] == module_base + 0x79E0C80`. Take the first match.

**Mount ABI nailed down 2026-06-28 (deeper disasm of wrapper + impl):**
- Wrapper at +0x204FFD0 = `bool Mount(FPakPlatformFile* this, const wchar_t*
  mountDirectory)`. NOT a single-pak mount — it's a directory-scan-and-mount-all.
  The wrapper constructs an FString from the wide literal at module-RVA
  +0x76DC9C0, which decodes to **`L"*.pak"`** (wildcard mask). Passes
  `(this, dir, &maskFString)` to impl.
- Impl at +0x2050020 = `bool Mount(this, mountDir, FString* fileMask)`. Allocates
  a `TArray<FString>` at [rsp+0x38]/[rsp+0x40], calls FindFiles-equivalent at
  +0x2044430, then per-match emits "Mounting pak file %s." (the LEA at +0x20502D1
  we anchored) and runs per-pak mount work inline.

**Shim implication:** call wrapper with a fresh subdirectory containing only
our mod pak (e.g. `Loki/Content/Mods/`). The default "*.pak" mask finds it
without re-triggering mount on the 16 cooked paks. Alternative: chase the
per-pak inner mount called from impl's loop body if directory isolation
turns out unwieldy.

**Worker thread plan (initial — superseded by shim execution findings below):**
1. Inject DLL early (CREATE_SUSPENDED + manual-map, proven mechanism).
2. Worker polls for `.text` page commit at +0x2047EE0.
3. Patch sig-load entry to `B0 01 C3`.
4. Resolve FPakPlatformFile singleton via vtable scan.
5. `QueueUserAPC` on the game thread (TID from +0x9D49158) → APC body calls
   `Mount(singleton, pakPath)`.
6. Mount's success path fires OnPakFileMounted2 → AR auto-reloads.
7. Open the Missions modal → check whether the AR class flips actually
   trigger primary-asset registration (the route's REAL kill criterion).

### Shim execution 2026-06-28 — what we learned by actually running it

Built `tools/sigbypass-mod/mount_shim.cpp` end to end and ran 4 iterations.
Several pillars of the plan held; one fell over and exposed that Loki's pak
architecture is **not the vanilla UE single-singleton model**.

**Pillars confirmed:**
- Sig-bypass `B0 01 C3` patch at `+0x2047EE0` lands cleanly when applied
  from a worker thread that waits for the `.text` page to commit
  (~115k spin iterations / ~1.1s wall time of `MEM_COMMIT` check polling).
- Manual-mapped DLL + CREATE_SUSPENDED inject + ResumeThread proven for
  this binary (`tools/inject launch`).
- `GGameThreadId` slot at +0x9D49158 reliably contains the engine main
  thread ID (~190ms after `ResumeThread`).
- Singleton-finder scan for `qword == module_base + 0x79E0C78` is fast
  (~15k regions, ~few hundred ms) and produces consistent results across
  launches.

**Pillars broken:**

1. **Patching sig-load EARLY (from worker) crashes the game later.** The
   patched function returns success without filling the FPakSignatureFile
   struct. Cooked paks ALL have real `.sig` files so the original code
   would have populated chunk hashes etc. Returning empty-struct leaves
   downstream chunk-verification code reading zero-valued hashes, which
   eventually trips an AV elsewhere. **Mitigation:** delay the patch
   until AFTER the cooked-pak mount loop completes — apply it from the
   APC body, not the worker. Verified this works (cooked paks mount
   normally, patch lands later).

2. **The 16 vtable-A holders are NOT singletons.** Across three game
   launches, the scan consistently finds **16 instances** of an object
   whose first qword is `module_base + 0x79E0C78`. Their layout looks
   FPakPlatformFile-like at first glance (vtable A at +0, second-base
   vtable B at +0x10) but:
   - `+0x08` is a small integer (1 or 2), NOT a heap pointer. In vanilla
     UE this would be `IPlatformFile* LowerLevel`. Reading it as a ptr
     and calling through it (which `Mount` does at its inner
     `mov rcx, [rcx+0x8]; call ...` site) causes an immediate AV.
   - `+0x18` IS a heap pointer (per-instance data), and consecutive
     instances' `+0x18` ptrs are spaced 0x480 bytes apart in a second
     array — suggesting they're per-pak data structs.
   - The 16 instances are contiguous in heap with a 0x280-byte stride.
   - **16 matches the number of cooked .pak files** (pakchunk0 +
     pakchunk0_s1..s15). They are *per-pak* objects, not singletons.

   So either: (a) MSVC ICF folded `FPakPlatformFile::Initialize` and
   `FPakFile::Initialize` into the same function body, and the vtable
   we found is FPakFile's; or (b) Loki actually has 16 FPakPlatformFile
   instances in a custom per-chunk architecture. Either way, the
   "find the singleton, call its Mount" plan doesn't apply.

3. **APC dispatch isn't reliable in early-init game state.** When login
   fails (no hosts redirect, real backend rejects), the game thread sits
   in non-alertable HTTP retry loops and our APC never fires (3+ minutes
   observed). With successful login the alertable waits (Vivox / UI tick)
   do happen and APCs fire within ~30s — but this dependency is fragile.
   **Mitigation:** run pure-read diagnostics (singleton scan, reference
   scan) directly from the worker thread; only put state-mutating calls
   (patch + Mount) inside the APC.

**Reference scan from per-pak wrapper #1 (`0x...CE00`) — 30 hits.**
The most informative hit was at `0x2490E3D76F8` with `prev2 =
0x249624ED080` (= wrapper #2). Peeking around it revealed:

```
0x...7600  BB D6 / 1D D7 / 1E D7 / ... / 2A D7    ← 15 uint32 chunk sub-IDs (0xD6BB,
0x...7630  28 D7 / 29 D7 / 2A D7 / 49 02            0xD71D..0xD72A in 16-bit range)
0x...7640  [3, wrapper #12 (0x249624EE980)]        ← 16-byte entries, REVERSE order
0x...7650  [3, wrapper #11]
0x...7660  [3, wrapper #10]
...
0x...76F0  [3, wrapper #1 (0x249624ECE00)]         ← our anchor
0x...7700  [module ptr 0x7FF667B76168, 0, ...]     ← sentinel
```

12 wrappers visible in this region (#1-#12). 4 more (#13-#16) presumably
in adjacent blocks not captured. Each entry is `(uint64 tag=3, void* ptr)`.

The active TArray header pointing at this region lives at `0x2492FA12778`
with `Num=15, Max=64` — but it points at `0x2490E3D7600` (the uint32
sub-ID array, not the wrapper-ptr region). So this is a **per-chunk
metadata block, not a `PakFiles` TArray**.

Peeking the broader context at `0x2492FA126XX` shows the container is an
**array of per-chunk blocks**, each ~0x50 bytes with multiple TArrays
inside (chunk_id, sub_IDs TArray, wrapper-ptrs region, more TArrays).
This is custom Loki architecture; vanilla UE has nothing analogous.

**Module sentinel at +0x84A6168:** referenced ONLY at `0x...7700` (the
slot after the wrapper-pointer region). Not a vtable.

**Where this leaves option 1:**
- "Call Mount on the singleton" doesn't apply — there's no singleton in
  the expected form.
- The actual "add a pak" function in this build likely takes different
  args and uses a different `this` shape. We'd need to find it via
  recon of one of the OTHER pak-mount log strings (e.g., "Successfully
  mounted deferred pak file") and disasm the function emitting it.
- Even if we found the right call, the route's deeper kill criterion
  (LokiAssetManager not querying AR for primary-asset registration)
  might still fire, voiding the whole effort.

**Sub-option: in-memory AR patch (not yet tried).** Instead of mounting
a new pak, find the loaded `FAssetRegistry` singleton and patch its
in-memory `FAssetData` entries directly (same 16 class flips as on
disk). Anchors exist: `"FAssetRegistry took"` wide string at module-RVA
+0x79D5DF0 with unique LEA at +0x1FD8DBE; `"Premade AssetRegistry
loaded from"` at +0x79D5B40. No sig-bypass needed, no Mount needed. Same
deeper-kill-criterion risk.

**Reusable tooling shipped:** `tools/sigbypass-mod/mount_shim.cpp` (full
worker + APC framework with marker logging, vtable scan, ref scan, safety
checks) + `race-mount-suspended.ps1` orchestrator. Patches and infrastructure
will apply to any future approach in this architecture.

### Mount call-graph mapping 2026-06-28 (deeper, post-architecture-finding)

After confirming the 16-instance per-pak architecture, traced the actual
call graph for mount-related functions via `callxref`. The picture is more
complex than initial guesses:

**`+0x204FFD0` (Mount wrapper, 2-arg) — DEAD IN THIS BUILD.**
- `callxref` returns 0 direct callers.
- `findptr` returns 0 references anywhere (no vtable slot, no fn-ptr table).
- The wrapper exists in `.text` but is never invoked. Either ICF-survivor
  dead code, or only ever called via inlined paths that got optimized out.

**`+0x2050020` (Mount impl, 3-arg) — called by 2 sites:**
- `+0x204FFFC` (inside the dead wrapper above — never reached).
- **`+0x204B2E5` — inside `FPakPlatformFile::Initialize` (+0x204AAD0)**, at
  offset +0x815 into the function. So **Initialize is the actual mount
  entry**: during engine init it iterates the cooked-pak directory and
  calls Mount impl once per pak. This produces the 16 per-pak FPakFile
  instances we observed.

**`+0x204F130` (internal mount helper with OnPakFileMounted2 broadcast)
— called by 4 sites:**
- `+0x205031E` (inside Mount impl, expected).
- `+0x2055A5B` (inside the deferred-mount handler at +0x2055950).
- **`+0x204979C` (NEW) — inside `FPakPlatformFile::Initialize` near the
  start (~0xCCC bytes in), separate from the Mount-impl call at +0x204B2E5.**
- **`+0x204E6F7` (NEW) — unknown function, worth disasming.**

So Initialize calls BOTH the internal mount helper (+0x204F130) AT ONE
POINT and Mount impl (+0x2050020) AT ANOTHER POINT. Likely a two-phase
init: first phase registers something then loops mount-impl per pak.

**`+0x2055950` ("Successfully mounted deferred pak file" emitter).**
- `callxref` returns 0 direct callers.
- `findptr` returns 1 heap hit at `0x15A3A9E35D0` (no module hits).
- Context at that heap slot (peeked at +/-0x20 bytes) shows a **48-byte
  entry pattern**: `(code_ptr, padding, uint32_id, heap_ptr, code_ptr,
  padding)`. Looks like a TFunction/delegate dispatch table holding queued
  deferred-mount jobs.
- Engine creates a deferred-mount job → wraps it in a TFunction →
  stores in this dispatch table → later dispatcher fires the TFunction
  which calls +0x2055950 → which calls +0x204F130 (the internal mount
  helper) → which adds the FPakFile to the singleton's pak registry +
  fires the OnPakFileMounted2 delegate.

**Practical implication: the master singleton ISN'T findable via any
direct vtable scan in this build.** The 16 per-pak instances DO have
vtable A (with Initialize at slot 11), but no DIFFERENT object holds
the same vtable A. So either:
- (a) The master FPakPlatformFile has a different vtable than vtable A,
  but its Initialize was ICF-folded to share the same +0x204AAD0 code
  address. To find it we'd need to scan for objects whose vtable[+0x58]
  (slot 11) equals +0x204AAD0, regardless of vtable base. New scanner.
- (b) The master is found via a global pointer in module `.data`. To find
  it: scan code for `mov rcx, [rip+disp32]; call qword [rcx + 0x58]` —
  the load+invoke-Initialize pattern — and resolve `disp32` to a `.data`
  slot, then read the slot's contents. New tooling, but tractable.
- (c) The master is constructed but not held in any field — it's an
  inline member of some larger struct. Would require deeper struct
  walking.

**Three remaining sub-options for option 1, ranked by tractability:**

1. **Enqueue to the deferred-mount dispatch table** (1-2 sessions). We
   know the table is at heap `0x15A3A9E35D0` (in one launch — heap addresses
   vary). We'd need to:
   - Find the table dynamically (scan for code that LEAs into the table
     region — the table itself probably has a known marker).
   - Construct a deferred-mount job entry (48 bytes with our pak path).
   - Append to the table.
   - Let the engine's natural dispatch fire our entry on the right thread.

2. **Find master via "mov rcx, [rip+disp]; call qword [rcx+0x58]" pattern
   scan** (2-3 sessions). New `usmapdump` subcommand to scan for that
   specific 13-byte instruction sequence in `.text`, extract the `disp32`,
   resolve to `.data` slot, read singleton ptr.

3. **In-memory FAssetRegistry patch (alternative route)** (2-3 sessions).
   Skip Mount entirely. Find the loaded `FAssetRegistry` singleton and
   patch its `FAssetData` entries directly. Anchors: `"FAssetRegistry took"`
   wide @+0x79D5DF0 (unique LEA at +0x1FD8DBE), `"Premade AssetRegistry
   loaded from"` @+0x79D5B40. Same downstream-kill-criterion risk as Mount
   approach.

**ALL THREE share the SAME kill criterion** at the end: even if successful,
LokiAssetManager may not consult AR for primary asset registration (per
prior MISSION PROBE #2 analysis), making the whole effort produce zero
behavior change.

### Slot-11 vtable scanner — ICF hypothesis FALSIFIED 2026-06-28

Built `tools/usmapdump vtslot <proc> <slot> <fnAddr>` to scan committed
memory for ANY vtable whose specified slot holds a target function. This
would find ICF-folded vtables (different classes sharing the same code
address for a method).

Ran `vtslot SUPERVIVE-Win64-Shipping.exe 11 0x7FF66171AAD0` (looking for
any vtable with +0x204AAD0 = "FPakPlatformFile::Initialize" code address
at slot 11). **Result: exactly 3 hits, all with IDENTICAL slot contents
slot 0 through slot 11** — meaning they're THE SAME vtable, just appearing
in module .rdata + two heap-cached copies. No separate vtable shares the
slot value.

**Conclusion: ICF folding is NOT the explanation. There is exactly ONE
class with `Initialize` at slot 11, and the 16 per-pak instances ARE
that class.** No "master" FPakPlatformFile exists in a different class
elsewhere.

**Architectural verdict:** this build appears to use a per-chunk
FPakPlatformFile architecture where each cooked .pak chunk gets its
own standalone FPakPlatformFile-like instance. The `+0x08` small int
is likely a chunk index, not `IPlatformFile* LowerLevel`. There is no
master "PakFiles registry" — each instance manages exactly one .pak.

Implications:
- The 2-arg Mount wrapper is dead code because there's no master to
  invoke it on.
- Mount impl is only ever called by `FPakPlatformFile::Initialize`
  during engine startup, once per cooked pak chunk.
- **There is no runtime path to add a NEW pak in this architecture.**
  The engine assumes pak chunks are immutable after init.

To add a runtime pak in this design, one would need to:
1. Heap-allocate a new 0x268-byte FPakPlatformFile-shaped object.
2. Hand-initialize all its fields (chunk index, internal data ptr at
   +0x18 with 0x480 bytes of per-pak state, vtable pointers).
3. Invoke `Initialize` on it (or its mount logic).
4. Insert into whatever container `FPlatformFileManager` uses to hold
   the 16 chunk instances (currently unknown structure).
5. Fire `OnPakFileMounted2` to notify FAssetRegistry.

This is a multi-week reverse-engineering effort with significant
construction-of-engine-state complexity. Combined with the route's
own kill criterion (LokiAssetManager not querying AR for primary
asset registration regardless), **this entire option-1 pursuit is
effectively closed.**

The reusable tooling (mount_shim, vtslot scanner, sigbypass tooling)
stands as documented infrastructure for any future approach that
might revisit this from a different angle.

### Option 2 — last resort

**Hook the packer's page-fault handler**. Intercept after it unpacks our
function's page, apply the 3-byte patch BEFORE returning to the original
faulting instruction. Probably a user-mode vectored exception handler
we'd register before the packer's. Requires understanding the packer's
handler layout (the `runtime.dll` + `preloader.dll` + packer0..42 sections
in the shipping exe). High variance, fragile.

## Kill criteria

- `assetregistry stats` shows **no** primary-asset-suggestive class entries
  for Mission / MissionPool / Hero / StoreOffer → cook stripped the metadata,
  route can't work without a much bigger edit. ✅ NOT FIRED — see Diagnostic
  findings above; 16,158 entries carry these tags.
- A one-mission patch deploys but `LogAssetManager` STILL warns "Invalid
  Primary Asset Type" → `LokiAssetManager` never consults the AR for primary
  asset registration; route is logically dead even with a working deployment.
  ⏳ STILL UNTESTABLE — deployment is blocked at the pak-signing layer, which
  is below the layer we want to test. The loose-file Test 1 result (zero log
  differential) is consistent with this prediction but isn't conclusive
  because the pak shadowed the loose file.
- A patched mission appears in the Missions modal → scale to other types.

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
- ⛔ **Sig-bypass via inject + WPM** — patch lands correctly but ~50ms after
  the function has already returned. Packer's lazy page-commit + execute is
  atomic from our perspective; can't interpose.
- ⛔ **Sig-bypass flag hunt (option 3)** — 13 candidates + 3 sanity controls
  all 0 hits. CVar name strings stripped from this shipping build; no flag
  to find. Closed 2026-06-28.
- ✅ Reusable RE tooling: `tools/usmapdump` (strings/wstrings/xrefstr/findptr/
  callxref/peek/disasm), `tools/inject` (mmap/launch/watch-now/probe/diag),
  `tools/sigbypass-mod/main.cpp` (UE4SS-style C++ patch DLL skeleton).
- ⏳ Option 1 (hook `FPakPlatformFile::Mount` + force AR reload) is the
  recommended next pursuit. 3-4 sessions. Option 2 (page-fault handler hook)
  is last resort.
