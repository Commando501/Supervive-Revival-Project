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

**Worker thread plan:**
1. Inject DLL early (CREATE_SUSPENDED + manual-map, proven mechanism).
2. Worker polls for `.text` page commit at +0x2047EE0.
3. Patch sig-load entry to `B0 01 C3`.
4. Resolve FPakPlatformFile singleton via vtable scan.
5. `QueueUserAPC` on the game thread (TID from +0x9D49158) → APC body calls
   `Mount(singleton, pakPath)`.
6. Mount's success path fires OnPakFileMounted2 → AR auto-reloads.
7. Open the Missions modal → check whether the AR class flips actually
   trigger primary-asset registration (the route's REAL kill criterion).

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
