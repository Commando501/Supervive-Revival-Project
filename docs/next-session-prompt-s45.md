# Session 45 pickup — the hero grid DATA PATH is solved; the wall is now the hero-content-load CRASH

Repo: `G:\git\Supervive Revival Project` — branch `dedicated-server-stub`.
Copy this whole file into a fresh Claude session's first message.

## TL;DR of where we are

Sessions 43–44 **overturned the "empty grid = AssetManager registration" framing** and
proved something bigger: **the empty ALL HUNTERS grid and the long-standing D3D12/render
crash are the SAME wall.** The empty grid was *masking* the crash. We now make the grid's
data path work end-to-end — and the instant the heroes actually resolve and load, the
client crashes loading their content. That crash is the remaining blocker, and it is now
**reproducible on command** (a big upgrade from the intermittent version).

What is PROVEN (live-process reads, injected payloads, vtable-slot traces, backend fix):

1. **The grid enumerates heroes via `UAssetManager::GetPrimaryAssetIdList(Hero)`** —
   called ~209× at menu-load (traced via vtable-slot hooks). In the stock game it returns
   0 (LokiAssetManager never fills the per-type AssetMap), so the grid is empty.
2. **A runtime scan makes enumeration return 25.** `tools/sigbypass-mod/scan_on_enum.dll`
   hooks `GetPrimaryAssetIdList` (LokiAssetManager vtable **slot 110**) and, on the FIRST
   call, runs `ScanPathsForPrimaryAssets` for all 30 types (rcx IS the manager) BEFORE
   tail-jumping to the original — so the enumeration returns `Num=25` by construction
   (logged from inside the hook). Then it un-hooks (restores the slot) so a code-integrity
   check finds the vtable pristine (session 43: a left-in-place patch crashes ~3–5 min in).
3. **The content-manifest "enabled" flag was hiding the heroes.** The client requests
   `GET /content-service/manifest/<v>?nonEnabledOnly=true`. Our handler returned all 25
   heroes there — marking them all NON-enabled — so the grid filtered them out even once
   enumeration returned 25. FIX (committed): `server/internal/menu/menu.go
   handleContentManifest` returns EMPTY heroes for the `nonEnabledOnly=true` query, so all
   heroes stay ENABLED.
4. **With BOTH fixes the heroes RESOLVE and LOAD** (measured in Loki.log):
   `RequestAsyncLoad() null assets` 8→0, `ChangeBundleStateForPrimaryAssets failed to find
   NameData` 2→0, and the client loads real hero content — ability GameplayCues for
   ShieldBot.DashAttack, Flash.OffCD, Hook.Impact.HookGuy, HookGuy.ChargeBlast, etc.
5. **Then it CRASHES.** ~5s after "Unlockable heroes fetched: 25", during hero-cue loading:
   `LogSlate: InvalidateAllWidgets` → `LogAudio: Audio Device unregistered from world 'None'`
   → `LogUObjectHash: Compacting` → `LogSentrySdk: flushing ... crashpad`. This is EXACTLY
   the crash session 42 saw under early injection and misattributed to "early-init
   fragility." It was the hero-content-load crash all along.

## The remaining wall (Session 45's target)

**Loading the hero roster's content crashes the client.** This is the project's real
blocker now — and it's the same crash family that dogged the dedicated-server path
(S40/41 D3D12/RHI). We DON'T yet have a callstack because SUPERVIVE routes crashes through
Sentry (no UECC minidump is written). One hero loads fine (the detail-panel preview =
"Frontline Pyromaniac"); the full roster crashes → it's a multiple/bulk-hero issue, not a
single bad asset.

Honest caveats carried forward:
- **No visual tile confirmation yet** — the client crashes during the load, before you can
  navigate to HUNTERS (hero content loads automatically for the lobby/party previews). The
  proof the data path works is the measured behavior change (null-loads 8→0, NameData 2→0,
  real hero cues loading), not a screenshot.
- **Crash-isolation was INCONCLUSIVE.** Enabling only 3 heroes via the manifest did NOT
  cleanly resolve just 3 (grid stayed empty, null-loads returned to 8), so we could not
  separate "bulk-load spike" from "render-any-multiple-heroes." Don't assume it's bulk.

## Read these first, in order

1. `CLAUDE.md` — project rules, launch gotchas, DO-NOT list.
2. `memory/supervive-hero-roster-blocker.md` — top entry is the Session-44 correction
   (the S43 "SOLVED, STABLE" entry below it is SUPERSEDED/wrong).
3. `docs/session-44-grid-datapath-SOLVED-crash-is-the-wall.txt` — **THE key doc.** Full
   chain, the two fixes, the measured breakthrough, offsets, reproduce steps, caveats.
4. `docs/session-43-scan-on-browse.txt` — has a CORRECTION BANNER on top; read that banner,
   then skim for the Browse-hook/GEngine-find/un-hook machinery (reused, but NOT the fix).
5. Supporting: `docs/session-42-step6..9-*.txt` (the AssetManager RE this built on).

Auto-loaded memory already in context: `supervive-hero-roster-blocker.md` (S44 on top),
`supervive-rpc-signature-solved.md`.

## Ground-truth offsets (this build; RVAs stable, module base moves with ASLR)

- `LokiAssetManager` vtable = RVA **+0x888CB78**
- `UAssetManager::ScanPathsForPrimaryAssets` = RVA **+0x34CF9F0** (vtable slot 88)
- `GetPrimaryAssetObject` = +0x34BFB50 (slot 101); `GetPrimaryAssetPath` = +0x34BFF20 (103);
  **`GetPrimaryAssetIdList` = +0x34BF320 (slot 110)** ← scan_on_enum hooks this;
  `ChangeBundleStateForPrimaryAssets` = +0x34AF2A0 (slot 119) — arg-read layout still
  UNVERIFIED (my TArray offset gave garbage; re-derive before trusting it).
  Slots counted from `H:\Unreal Engine\UE_5.4\...\Engine\Classes\Engine\AssetManager.h`;
  validated by AddDynamicAsset=slot 94.
- `GGameThreadId` slot = RVA **+0x9D49158** (uint32, nonzero once engine thread runs)
- `&FNamePool.Blocks[0]` = RVA **+0x9D81450** (FName id = `(block<<16)|(off>>1)`, Len10
  header: `len = header>>6`; narrow/ASCII)
- `UEngine::AssetManager` = **UEngine + 0x340** (rcx in UEngine::Browse is GEngine)
- `UEngine::Browse` = RVA +0x3EC57D0 (prologue hex `40555356574154415541564157`)
- Hero FName id **0x1A568**; AssetTypeMap = mgr+0x478 (stride 0x20: key FName@0,
  FPrimaryAssetTypeData*@+8); FPrimaryAssetTypeData: Type@0, BaseClass@0x30, scan-paths@0x70;
  Hero per-type AssetMap @ td+0x178 (RPM-verified 25 keys: "Alchemist","Wukong",...).

## Tooling built (this build)

- `tools/sigbypass-mod/scan_on_enum.cpp` (+ .dll, gitignored — rebuild) — **the fix.**
  `clang++ -shared -O2 scan_on_enum.cpp -o scan_on_enum.dll -lkernel32`
  (clang++ at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\...\usr\bin`).
- `tools/sigbypass-mod/trace_hooks.cpp` + `trace_resolve.cpp` — vtable-slot tracers (swap a
  slot to a logging stub, tail-jump/wrap to the original, resolve FNames via the pool). This
  is the technique that cracked the binding — reuse it to trace whatever the crash path
  touches. Markers → `docs/*-marker.txt`.
- `tools/inject` (`watch`/`watch-now`/`mmap`, non-elevated), `tools/usmapdump` (read-only
  RPM: `peek`, `disasm`, `nameid`, `vtdump`, `findptr`), Python ctypes RPM readers (recreate
  in scratchpad; FNamePool resolver above).

## Session 45 plan (priority order)

### Path 1 (recommended): get a real callstack for the hero-content-load crash
Sentry eats the crash (no UECC minidump). Options to see the faulting RIP/module:
- **VEH-log**: from an injected DLL, `AddVectoredExceptionHandler` (FIRST handler), log the
  faulting address + module + a short stack, then `EXCEPTION_CONTINUE_SEARCH` so Sentry
  still runs. NOTE CLAUDE.md warning: the packer's VEH eats C++ EH — this is a read-only
  VEH that only logs and passes through, which is different, but test carefully.
- **Bypass Sentry**: hook/neutralize `LogSentrySdk`'s crash handler (or the crashpad
  handoff) so UE's own crash reporter writes a `Saved/Crashes/UECC-*` minidump with the
  callstack + module list (that's how S40/41 identified D3D12). Then read it with the
  Python `minidump` pkg (already installed).
- Once you have the RIP/module: decide **D3D12/RHI** (render the hero previews — the
  S40/41 family, likely unsolvable client-side) vs **memory/streaming spike** (loading all
  25 heroes' content at once — potentially throttle-able).

### Path 2: can the load be STAGED so the grid renders without the bulk crash?
The 3-hero manifest test was inconclusive (subset didn't resolve). Figure out the correct
lever to make the client load FEWER heroes' content at once (so it survives long enough to
render tiles). Candidates: the manifest "enabled" semantics (get subset-enable actually
working), or throttling `RequestAsyncLoad`/`ChangeBundleState` from an injected hook, or
loading heroes lazily. Success = a STABLE menu with even a FEW visible hero tiles (the
first-ever visual confirmation) + it tells us the crash is a bulk spike, not render-any.

### Path 3: confirm it's the same crash as S40/41
If Path 1 yields a D3D12/RHI RIP in the same band as S40/41 (`+0x296xxxx`/`+0x2976FF0`,
D3D12Core.dll loaded, RHI thread), that closes the loop: grid + dedicated-server crash are
literally the same instruction family, and the roster is not achievable client-side without
solving the render wall (a hardware/driver/build problem, not a backend one).

### Strategic note to raise with the user
The grid DATA PATH is solved and the two long-standing problems are now one. But the
remaining wall (hero-content-load crash) may be the D3D12/RHI render wall — which prior
sessions could not beat from user space (anti-cheat blocks renderer CVars/flags; the crash
is deep in D3D12 command-list/residency). If Path 1 confirms that, the honest framing is:
the roster grid is blocked on the same rendering crash as everything else, and the win to
bank is that we now understand and can trigger it precisely.

## The live test cycle (memorize)

Steam must be running first (else Auth Failure 14005). Hosts file must have the two
SUPERVIVE-REVIVAL entries (127.0.0.1). Certs in `server/certs` are reused by `EnsureCert`
(restarting ags does NOT regenerate them — safe). Do NOT run `launch-redirect.ps1`.

```powershell
# 0. Kill just the game + injectors (leave Steam + ags, or restart ags for a manifest change)
Get-Process 'SUPERVIVE-Win64-Shipping',inject,crashpad_handler -EA SilentlyContinue | Stop-Process -Force

# 1. (if you changed the backend) rebuild + restart ags from the server dir:
#    go build -C server -o ags.exe ./cmd/ags   ; then run server\ags.exe with CWD = server\
#    verify: curl "http://localhost:8080/content-service/manifest/x?nonEnabledOnly=true" -> Heroes {} empty

# 2. Start the gated early injector BEFORE launching the client:
tools/inject/inject.exe watch SUPERVIVE-Win64-Shipping.exe `
  tools/sigbypass-mod/scan_on_enum.dll 0x3EC57D0 40555356574154415541564157

# 3. Launch the NORMAL client (redirects only, NO stub) via launch-recon.bat (recreate in
#    scratchpad from the S43 doc — the 9 -ini: AccelByte/Loki URL overrides + -log).
```

Client log: `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (truncated per run).
scan_on_enum marker: `docs/scan-on-enum-marker.txt`. ags capture: `server/docs/capture.log`.

Computer-use for visual: request access to basename **`supervive-win64-shipping.exe`** (not
"SUPERVIVE"/Steam); the game window is on the primary monitor; foreground it via user32
ShowWindow/SetForegroundWindow (P/Invoke) since the taskbar is explorer (not grantable).
HUNTERS is the left-nav item; zoom the grid region ~[250,185,720,620].

## What NOT to do

- Don't re-grind the AssetManager REGISTRATION route — it's fully explored (registration ✓,
  enumeration ✓ returns 25). The wall is the hero-content-LOAD crash, downstream of it.
- Don't trust `scan_on_browse.dll` as "the fix" — it does NOT populate the grid (session-43
  verdict was wrong; see the correction banner). Use `scan_on_enum.dll`.
- Don't leave a vtable-slot or code patch installed long — un-hook after use (the code-
  integrity check crashes the game ~3–5 min in otherwise; that's a SEPARATE crash from the
  hero-content-load one — don't confuse them).
- Don't propose C++-exception-using injection payloads (packer VEH kills them). A read-only
  VEH that logs + passes through is different and is the Path-1 tool.
- Don't send `-LogCmds` expecting Verbose logs — this is a SHIPPING build; Verbose/VeryVerbose
  UE_LOG is compiled out (confirmed). Use hooks/RPM, not log verbosity.
- Don't run `launch-redirect.ps1` (wiped hosts before). Steam must be up first.

## Wrap-up expectations

- Write a `docs/session-45-*.txt` evidence log. Update `memory/supervive-hero-roster-blocker.md`
  (top entry) + the `MEMORY.md` index line. Commit as you go (small single-purpose commits).
- If the crash is confirmed the D3D12/RHI render wall, say so plainly and give the user the
  honest strategic picture rather than grinding a wall prior sessions already characterized.

Good luck. The grid's data path is SOLVED and the two big problems are now ONE. The last
mile is a real callstack for the hero-content-load crash — then we know if the roster is
achievable client-side at all.
