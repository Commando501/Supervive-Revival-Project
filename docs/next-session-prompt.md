# Next session kickoff — Milestone 3 Track B (sig-bypass flag hunt, option 3)

> Paste the fenced block below into a new Claude Code session to continue.
> The memory file
> `C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\memory\supervive-milestone3-trackb-status.md`
> is auto-loaded; this prompt is a focused starting kit for the next concrete step.

```
We're continuing the SUPERVIVE Revival project on branch
claude/assetregistry-primary-assets-w7pljz. The AssetRegistry repack route has
working end-to-end tooling but is blocked at pak signing. Last session proved
deploying a mod pak requires bypassing the engine's signature check, and the
obvious approach (inject + WriteProcessMemory patch of
FPakSignatureFile::Load at module RVA 0x2047EE0) doesn't work because the
shipping exe's packer commits .text pages on-demand via a page-fault handler
— the function executes the same atomic moment its bytes appear, no
observable window for a co-resident patcher to interpose. Full empirical
analysis and the three remaining options are documented in
docs/trackb-assetregistry-route.md; the memory file
supervive-milestone3-trackb-status.md has the full chronology.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status                # should be clean (cert/log dirty is normal)
  git log --oneline -8      # last commit "Update trackb docs..."
  # Then read:
  #   docs/trackb-assetregistry-route.md  (canonical state)
  #   docs/trackb-notes.md "Update 2026-06-28 (later)" section
  # (the memory file is already in your context)

THE PLAN: option 3 — hunt for a sig-bypass flag/CVar in unpacked memory.
Cheapest probe (2 sessions for a definitive yes/no), highest ceiling. If a
flag is found and is stored in early-committed data memory, we can flip it
via WriteProcessMemory before pak mount with no race against the packer.

Common UE pak-signing config keys/strings to hunt with tools/usmapdump
strings and wstrings against the running game:
- bRequireSignedPak (UE source uses this in FPakPlatformFile)
- RequireSignedPak
- SignedPak
- Pak.SkipSignatureCheck (CVar name in some forks)
- Pak.SignatureCheck
- GetPakSigningKeysDelegate
- FPakSignatureFile (class name, may appear in RTTI / debug strings)
- [Core.System] (ini section header for some signing settings)

Procedure for each hit:
  1. usmapdump wstrings "SUPERVIVE-Win64-Shipping.exe" "<needle>" and
     usmapdump strings ... — find narrow + wide variants.
  2. For each in-module hit: usmapdump findptr to find the pointer slot
     holding its address (UE often references string literals via pointer
     tables in .rdata).
  3. usmapdump xrefstr against the pointer slot's address — find rip-rel
     LEA instructions loading it.
  4. usmapdump disasm around each xref — identify the reading function.
  5. In the reading function, look for the bool/byte slot that gets SET
     based on the config value: typically a `mov byte ptr [rip+disp], 1`
     instruction nearby. That slot is our candidate flag.
  6. findptr against that slot's RVA to find any pointer tables. If the
     slot is in .data or .rdata, its containing page should commit early
     at process startup → no race to patch.

If a flag is found and the page is early-committed, the bypass is one
external WriteProcessMemory call before launching the game (or after a
brief poll). Sig load function will return success → mod pak mounts →
patched Loki/AssetRegistry.bin is read → we can finally test the route's
kill criterion.

TOOLING (all already built and committed; rebuild on demand):
- tools/extractor — read/write AR.bin: assetregistry stats|classes|
  inspect|candidates|namemap|apply-patch, wherefile, mkpak, peekpak.
- tools/usmapdump — live-process recon via RPM: info, names, objects,
  extract, strings, wstrings, xrefstr, findptr, callxref, peek, disasm.
  Build with `go build -trimpath -o usmapdump.exe .` from tools/usmapdump.
- tools/inject — DLL injection: mmap (manual map, bypasses CIG), launch
  (CreateProcess SUSPENDED + mmap + Resume), watch-now, probe, diag.
  Build with `go build -trimpath -o inject.exe .`.
- tools/sigbypass-mod/main.cpp — UE4SS-style C++ DLL skeleton that
  patches FPakSignatureFile::Load to return success. Build with
  `clang++ -shared -O2 main.cpp -o main.dll -lkernel32`. (DLL is
  .gitignored; rebuild when needed.) Race scripts: race.ps1 and
  race-suspended.ps1.

KEY RVAs (all stable per build, module base + RVA each launch — only ASLR
base moves):
- L"Couldn't find pak signature file" (in-module string): +0x79E17F0
- UE log-record struct for above: +0x79E17C8
- FPakSignatureFile::Load entry: +0x2047EE0
- FPakSignatureFile::Load direct callers (E8 disp32 sites): +0x2036560
  (FPakFile ctor) and +0x2056624
- LokiAssetManager UClass vtable: +0x888CB78 (per prior native-shim RE)
- UAssetManager::ScanPrimaryAssetTypesFromConfig: +0x34D0807 (prior RE)
- GGameThreadId slot: +0x9D49158 (prior RE)

DO NOT RE-ATTEMPT (all proven dead in prior sessions):
- UE4SS-based deployment (proxy DLL dwmapi.dll never loads — the shipping
  exe's import directory is stripped; only preloader.dll is imported,
  which is the packer's bootstrap).
- Loose-file Loki\AssetRegistry.bin drop (proven inert via truncate
  kill-test — pak shadows it; game booted normally with 32 bytes of
  0xDEADBEEF at the loose path).
- Sig-bypass via injected DLL + WriteProcessMemory of
  FPakSignatureFile::Load entry — the patch lands ~50ms after the function
  executes because the packer commits and executes atomically. See full
  race timeline in docs/trackb-assetregistry-route.md.
- Borrowed .sig file (engine validates content, not just presence).
- Modifying inside an existing .ucas pak (signature would invalidate).

LAUNCH:
Requires elevated shell. configs/launch-redirect.ps1 auto-builds the Go
server, sets up hosts file + cert override, launches the game.
Intermittent hosts-file race; retry after killing ags + brief wait.
Loki.log overwritten per launch at
%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log.

KILL CRITERION FOR OPTION 3:
- No sig-bypass-related strings found in unpacked memory → option 3 is
  dead, move to option 1 (hook FPakPlatformFile::Mount + force AR
  reload).
- Flag found but its containing page is also lazy-committed → race
  problem returns, option 3 likely dead, move to option 1.
- Flag found, page is early-committed, but flipping it doesn't change
  pak mount behavior → flag doesn't actually gate signing; keep hunting
  other candidates or move on.

THE DEEPER CONCERN, REGARDLESS OF OPTION 3 OUTCOME:
Even with a working sig-bypass and mod pak mounted, the route's own kill
criterion may fire — Test 1's zero-differential analysis strongly hinted
that LokiAssetManager doesn't query AR for primary asset registration at
all (it registers only from the content-service manifest per prior RE).
If that's the actual blocker, no deployment fix helps — we'd need to RE
LokiAssetManager directly and patch its registration logic. That's a
separate parallel investigation worth keeping in mind even while
pursuing the deployment fix.

WHAT'S READY TO DEPLOY THE INSTANT A SIG-BYPASS IS FOUND:
- tools/extractor/out/AssetRegistry.stage2.bin (36 MB, 16 patched entries:
  4 DA_MissionPoolDailyChallenge + 12 DA_Mission_ArmoryDaily_* flipped to
  LokiDataAsset_MissionPool / LokiDataAsset_Mission).
- tools/extractor/out/pakchunk999-WindowsClient_P.pak (single-file mod
  pak wrapping the stage2 AR.bin; round-trip-validated via peekpak).
- Drop the pak into <GameRoot>\Loki\Content\Paks\ once sig-bypass is in
  place; relaunch via launch-redirect.ps1; watch Loki.log for
  pakchunk999_P mount success + Mission entries in the modal.

NEW-SESSION CONSTRAINTS:
- Continue on branch claude/assetregistry-primary-assets-w7pljz. Commit
  + push each working step. Memory file is the canonical state record —
  update with every meaningful finding.
- The user's shell is elevated (admin); no UAC prompts needed.
- Build the Go server (separate, mostly untouched on this route) with:
    cd server
    & "$env:ProgramFiles\Go\bin\go.exe" build -o ags.exe ./cmd/ags
- The capture-log pair: docs\capture.log (HTTP ground truth, requests
  Claude's server sees) and Loki.log (client side, UTC, overwritten per
  launch). Cross-check both whenever a relaunch changes behavior.
```

## Quick verification commands (run before starting option 3)

```pwsh
cd "G:\git\Supervive Revival Project\tools\extractor\extractor"
& "$env:ProgramFiles\dotnet\dotnet.exe" build -c Release

cd "G:\git\Supervive Revival Project\tools\usmapdump"
& "$env:ProgramFiles\Go\bin\go.exe" build -trimpath -o usmapdump.exe .

cd "G:\git\Supervive Revival Project\tools\inject"
& "$env:ProgramFiles\Go\bin\go.exe" build -trimpath -o inject.exe .

cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
clang++ -shared -O2 main.cpp -o main.dll -lkernel32

# Launch (need elevated shell)
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1                    # full launch
.\configs\launch-redirect.ps1 -NoLaunch          # just env setup
.\configs\launch-redirect.ps1 -Revert            # undo hosts + cert
```

## The three options (ranked for the new session)

1. **Sig-bypass flag hunt (option 3 in last session's analysis)** —
   PURSUE FIRST. 2 sessions for a yes/no. Cheap; high ceiling.
2. **Hook FPakPlatformFile::Mount + force AR reload** — 3-4 sessions.
   Mechanically known-feasible (we have injection + APC infrastructure
   from the prior native-shim work). If option 1 lands, no need for this.
3. **Hook the packer's page-fault handler** — last resort. 4-6 sessions,
   high variance, fragile.

If all three fail: the route is closed at the engineering level. The
fallback is parallel investigation of LokiAssetManager's primary-asset
registration code (the route's own kill criterion) — a different problem
entirely, but the only way to actually unblock missions / hunters / store
/ cosmetics if AR repack truly can't move the needle.
