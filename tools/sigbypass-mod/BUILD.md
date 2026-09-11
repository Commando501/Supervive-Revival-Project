# Building the native shims

`build.ps1` builds the injected DLLs in this directory. Before S106 there was no build script and no
`.dll` in git, so nothing in the default injection set was reproducible from a clean clone.

---

## Quick start

From any PowerShell (elevation is **not** needed to build — only to *launch* the game):

```powershell
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"

.\build.ps1                    # the default injection set          -> build\
.\build.ps1 -All               # 81 targets (63 shims + variants)   -> build\
.\build.ps1 -List              # what is registered, and what is clang-only
.\build.ps1 -Verify            # build, then byte-diff against the committed .dll
.\build.ps1 -Name missions_fix
.\build.ps1 -Name tutorial_launch -Variant play-novtguard
.\build.ps1 -Name missions_fix -InPlace       # write beside the sources (what the injectors load)
```

Output goes to `build\` by default, **never** overwriting a committed/known-good DLL. Use `-InPlace`
(or `-OutDir`) when you actually want to deploy what the injectors pick up.

---

## Prerequisites

| Need | Detail |
|---|---|
| **clang++** | The reference compiler. `build.ps1` finds it on `PATH`, then probes the Swift toolchain (`%LOCALAPPDATA%\Programs\Swift\Toolchains\*\usr\bin`), `%ProgramFiles%\LLVM`, and the VS-bundled LLVM. Override with `-Clang <path>`. On this machine it resolves to clang **21.1.6**. |
| **Visual Studio C++ toolset** | clang targets `x86_64-unknown-windows-msvc`, so it needs the MSVC headers, libs and `link.exe`. clang auto-detects the install; the script only forces `INCLUDE`/`LIB` if you pass `-VsEnv`. Located via `vswhere`, falling back to known paths. |

Nothing else. No CMake, no vcpkg, no third-party headers — every shim is a single self-contained
`.cpp` over `<windows.h>`.

---

## Why clang and not `cl.exe` (measured, S106)

The committed DLLs were built with **clang++**, not MSVC. Evidence, all re-derived from the artifacts
rather than taken on faith:

1. Every shim's own header comment records the command:
   `Build: clang++ -shared -O2 <f>.cpp -o <f>.dll -lkernel32`.
2. Rebuilding with clang 21.1.6 **reproduces the committed DLLs byte-for-byte except 3 bytes of PE
   `TimeDateStamp`** (plus its mirror in the debug directory — 6 differing bytes total). Verified for
   `catalog_store_fix`, `catalog_pick_fix`, `mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`,
   `battlepass_adopt_fix`, `gft_ready_fix`. Run `.\build.ps1 -Verify` to reproduce that result.
3. The DLLs carry a **Rich header** — so an MSVC `link.exe` linked them — reporting linker **14.42**
   (VS2022 17.12). clang's MSVC driver invokes the detected `link.exe` rather than `lld-link`, which
   is exactly how a clang-compiled object ends up inside a `link.exe`-produced image.

`cl.exe` **is** a usable fallback (`-Toolchain msvc`) for most shims, but it **cannot build two
files, and one of them is the active-route shim**:

| Shim | Why MSVC fails |
|---|---|
| `tutorial_launch.cpp` | `__builtin_sqrt` / `__builtin_cos` / `__builtin_sin` — error **C3861** |
| `browse_hook.cpp` | `__attribute__((ms_abi))` function-pointer typedef — error **C2143** |

MSVC output is also **not** byte-comparable to the committed DLLs (different CRT and codegen), so
treat `-Toolchain msvc` as "get unblocked without clang", not as the reference build.

---

## The hard constraints, and why they exist

`build.ps1` enforces the first two by **parsing the produced image**, not by trusting compiler flags.
A shim that violates one is deleted and reported as `REJECTED`.

### 1. No C++ exception machinery
The game is packed, and the packer installs a vectored exception handler that **kills the process** on
any C++ throw/unwind. Three canary variants were tested historically; all died, even with
`__CxxFrameHandler3` properly imported. So: **no `try`/`catch`, no `throw`, no throwing STL paths** in
an injected payload.

The build scans the output for `__CxxFrameHandler3`, `__CxxFrameHandler4`, `_CxxThrowException`,
`__std_terminate` and `_Unwind_Resume`. This gate was validated against all seven live-proven DLLs —
none contains any of those symbols, so it does not false-positive.

For a standalone second opinion (and an A/B helper), `verify_dll.py` in this directory runs the same
checks plus a marker-string diff:

```powershell
python verify_dll.py build\missions_fix.dll
python verify_dll.py --diff build\tutorial_launch_play.dll build\tutorial_launch_play_novtguard.dll
```

### 2. No dynamic CRT
An injected DLL must not depend on `vcruntime140.dll`, `msvcp140.dll`, `ucrtbase.dll` or
`api-ms-win-crt-*.dll`. The build parses the import table and checks every imported module against an
allowlist of system DLLs. clang defaults to the static CRT on `windows-msvc`; the MSVC path passes an
explicit `/MT` (MSVC would otherwise pick `/MD`).

If a shim legitimately needs a new system DLL, add it to `$AllowedImports` in `build.ps1` — the
failure message tells you so.

### 3. No permanent `.text` patch *(source-level, not build-enforced)*
A code-integrity check runs roughly 3–5 minutes after launch and kills the process if it finds a
modified `.text`. Any raw byte patch must be **self-restoring**: patch, let the builder run, restore.
`catalog_store_fix.cpp` is the reference implementation.

### 4. PI hooks must be transient and mutex-serialised *(source-level, not build-enforced)*
Two `ProcessInternal` hooks installed permanently **race on the prologue** and clobber each other. Any
shim that hooks `ProcessInternal` (`base+0x13454A0`) must:

* install its 5-byte `jmp` only **transiently** — install, piggyback one game-thread call, uninstall; and
* serialise through the shared named mutex **`Local\SuperviveMissionsPIHook`**.

That is what lets `mainmenu_refresh_pi8`, `loadout_fix` and `missions_fix` inject together in the
default set. `tutorial_launch.cpp` gained this in S106 (`KPIMUTEX`, default on; `-DKPIMUTEX=0`
restores the old unsynchronised behaviour for A/B).

> **Known gap:** `ds_hybrid.cpp` hooks `ProcessInternal` but has **no** mutex usage (0 occurrences of
> `CreateMutex` / `SuperviveMissionsPIHook`). It is not in the default injection set — it belongs to
> the parked DS route — so it does not race today, but injecting it alongside the default set would.

---

## Link libraries: there is no per-shim table, on purpose

Every shim links the same set: `kernel32 user32 wininet advapi32 shell32 ws2_32`.

**Measured:** an unused import library costs nothing. Building `gft_ready_fix` against all six produced
a DLL of *identical size* importing *only* `KERNEL32.dll` — the linker emits an import stub only for a
symbol actually referenced.

This deliberately replaces the old per-file convention, which was **wrong** for several shims: the
`Build:` comment in `tutorial_launch.cpp` says `-lkernel32` only, but `RM_PLAY` and `RM_PUPPET`
reference `GetAsyncKeyState` / `GetForegroundWindow` / `FindWindowA` and fail to link with **LNK2019**
without `user32` (measured both ways). A universal set means a new shim can call any Win32 API without
anyone remembering to update a table.

---

## Variants

Most shims build as a single plain `<name>.dll` and need no registry entry. Shims with a compile-time
mode switch have one in `$Variants`, mapping a suffix to extra `-D` flags. Output is
`<name>_<suffix>.dll` (dashes become underscores).

| Shim | Switch | Default when unset |
|---|---|---|
| `tutorial_launch` | `KRUNMODE` (`RunMode` enum) | `RM_CHEATSPAWN` |
| `ds_hybrid` | `KMODE` (`Mode` enum, line 99) | `MODE_SPECTATOR_CAM` |
| `gft_ready_fix` | `FILL_VALUES` | off |

`tutorial_launch`'s behaviour flags (all `#ifndef`-guarded, so `-D` on the command line wins):

| Flag | Default | What it does |
|---|---|---|
| `KVTGUARD` | 1 | Repairs a corrupt `APlayerCameraManager->ViewTarget.Target` from the game thread. **Symptom** guard. |
| `KGCROOT` | **0** (was 1 until S123) | `AddToRoot`s the loaded anim assets + body component (the worker-thread UAF). |
| `KPIMUTEX` | 1 | Serialises the transient `ProcessInternal` hook on `Local\SuperviveMissionsPIHook`. |
| `KXFORMFIX` | 1 | **S106d, CAUSE fix.** Spawn `FTransform` was copied as `0x50` bytes (truncating exactly at `Scale3D.Z` @ `0x50`) and four sites wrote `Scale3D` at the pre-S98 `0x38/0x40/0x48`. Every actor `SpawnActorCls` produced — *including the top-down `CameraActor` that becomes the view target* — spawned at `Scale3D = (x, y, 0)`. Third instance inside `BuildHeroBody`: `savedXform[0x50]` made the deferred `FinishAddComponent` re-apply `Scale.Z = 0` **at component registration**, silently undoing the S98 `RelativeScale3D = (1,1,1)` fix. |
| `KTESTACTOR` | **0** *(was 1)* | **S106d.** Leftover S94 diagnostic that built a **second** skeletal-mesh body on a standalone actor, in the same post-build hook hit, from a root scaled `(1,1,0)`. Best candidate for the single `LogChaosCloth` non-uniform-scale warning that appears in 4/4 crashing sessions and 0/5 non-crashing ones. |

### FK-7 artifact matrix (`tutorial_launch`) — rebuilt S106d, 2026-07-29

`KVTGUARD`, `KGCROOT`, `KPIMUTEX` and `KXFORMFIX` all default to **1**; `KTESTACTOR` now defaults to
**0** (S106d — it was 1). So the un-suffixed `play` build is **the candidate**: every guard on, both
S106d cause fixes applied, no leftover diagnostic body.

**Every control below differs from `play` in exactly one dimension.** Verified by rebuilding each
variant to an *identical output name* and byte-diffing (the export directory embeds the output
filename, so differently-named outputs cannot be compared directly — see *Reproducibility status*).

| DLL | Δ vs `play` | size | `.pdata` | `[VTG]` | `[GC]` | `[GCW]` | `[PIM]` | `test-body-actor` | C++ EH |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `tutorial_launch_play.dll` | — **(candidate)** | 236,544 | 442 | 8 | 8 | 4 | 4 | 0 | none |
| `…_play_novtguard.dll` | `-DKVTGUARD=0` | 232,448 | 439 | **0** | 8 | 4 | 4 | 0 | none |
| `…_play_nogcroot.dll` | `-DKGCROOT=0` | 230,400 | 438 | 8 | **2** | **1** | 4 | 0 | none |
| `…_play_nopimutex.dll` | `-DKPIMUTEX=0` | 235,520 | 441 | 8 | 8 | 4 | **0** | 0 | none |
| `…_play_noxformfix.dll` | `-DKXFORMFIX=0` | 236,544 | 442 | 8 | 8 | 4 | 4 | 0 | none |
| `…_play_testactor.dll` | `-DKTESTACTOR=1` | 237,056 | 442 | 8 | 8 | 4 | 4 | **1** | none |

All six pass `verify_dll.py` (`VERDICT: PASS`): no C++ exception machinery, no CRT import, imports
`KERNEL32.dll` + `USER32.dll` only. `nopimutex` additionally imports 92 KERNEL32 functions instead of
95 (the three mutex APIs drop out) — another independent single-dimension confirmation.

> **`play-noxformfix` has the same size and the same string counts as `play` — that is expected, not a
> duplicate.** `KXFORMFIX` only changes folded *constants*, and the `[XF]` log lines exist either way
> (they print the flag's value at runtime). It was proven distinct two ways:
> * byte-diff of same-named builds: **142,617 bytes differ**, 140,869 of them in `.text`;
> * emitted assembly: `g_xform+56` (offset `0x38`, the historical bug) is referenced **4× with
>   `KXFORMFIX=0` and 0× with `KXFORMFIX=1`**, which instead stores at `g_xform+64`/`+80`
>   (`movapd … g_xform+64` + `movq … g_xform+80`), and the `0x50` memcpy size disappears.
>
> The build is deterministic: rebuilding `play` with identical flags to an identical name differs in
> **2 bytes** (the PE `TimeDateStamp`).

#### Which DLL for which experiment

| Question | Inject | Read |
|---|---|---|
| Does the whole S106d fix set stop the 173–201 s crash? | `play` | no `[VTG] *** … INVALID`, no crash dir, hold past T+300 s |
| Is the view-target guard what's doing the work? | `play` vs `play-novtguard` | guard-off arm must reproduce the crash at RVA `3c5dc52` / `12c7e2d` |
| Is the anim-asset UAF (worker thread) still rooted? | `play` vs `play-nogcroot` | `FAnimSync::TickAssetPlayerInstances` crash only in the off arm |
| Is the leftover S94 test body the cloth antecedent? | `play` vs `play-testactor` | `grep -c LogChaosCloth Loki.log` → **0** vs **1**. ★ cheapest probe; pure log read, no crash needed, run it FIRST |
| Is the degenerate spawn scale on the causal path? | `play` vs `play-noxformfix` | `[XF]` lines report `Scale3D=(…)`; a `*** DEGENERATE ***` tag means registration saw Scale.Z = 0 |
| Do coexisting PI-hookers race? | `play` vs `play-nopimutex` | `[PIM]` lines absent in the off arm |

Family can be classified **without opening a minidump** (measured, S106d): the two ANIM (worker-thread)
sessions log `RequestExit(1, FRunnableThreadWin::GuardedRun.ExceptionHandler)` and produce 3 screenshots
in `Saved/Screenshots/WindowsClient`; the two CAMERA (game-thread) sessions log
`…LaunchWindowsStartup.ExceptionHandler` and produce **0**.

> **Removed in S106d (three footguns that would have corrupted the first A/B):**
> * `tutorial_launch_play_gcroot.dll` / `…_play_vtguard.dll` were **the same binary** — 2,048 differing
>   bytes, *entirely* the embedded export filename; identical size, identical 442 `.pdata` entries,
>   identical string counts. A/B-ing them compared a DLL with itself. **Deleted**; the aliases are gone
>   from `$Variants`. Use `play`.
> * `…_play_nogcroot.dll` was a **two-variable control** (`KGCROOT=0` *and* `KPIMUTEX=0`). Now one
>   variable; `play-nopimutex` covers the other.
> * `tutorial_launch_play.dll` was the **stale pre-fix build** (2026-07-26, 197,120 bytes, **0** `[VTG]`
>   strings, 425 `.pdata` entries) sitting under the most obvious name. **Deleted and regenerated.**
>
> Likewise `ds_hybrid.dll` and `ds_hybrid_spectator.dll` are still the same build (default `KMODE`).

> **⚠ 18 other `tutorial_launch_*.dll` in this directory are pre-S106d and NOT reproducible**
> (`tutorial_launch.dll`, `_phase`, `_wake`, `_tr`, `_cheat_name`, `_cheat_switch`, `_bpcall`,
> `_objcomplete`, `_objdrive`, `_qplay`, `_quest`, `_seq`, `_spawnplayer`, `_train`, `_camera`,
> `_dropin`, `_fireoverlap`, `_meshcam` — dated 07-12 … 07-24). They were built with ad-hoc `-D` flags
> that have **no `$Variants` entry**, so `build.ps1` cannot regenerate them and they still contain the
> pre-S106d `0x38` scale bug and the `s_tries` latch. Do **not** inject one expecting current behaviour.
> Every variant that *is* registered was rebuilt in place on 2026-07-29 (14 targets, 0 failures).

### FK-24 watchpoint probe artifacts (`tutorial_launch`, S107, 2026-08-03)

Two **diagnostic** builds that answer FK-24 — *what writes `0x01` into the low byte of
`PCM->ViewTarget.Target`?* They are not candidates and not A/B controls; they add an instrument on top
of `play`. `KWPROBE` defaults to **0** in the source, so `play` is unaffected by their existence — that
is not asserted, it is **measured** below.

**Rebuilt 2026-08-03 after the S107 review** — nine defects were found and fixed (two of them
crash-shaped blockers in the page build). The hashes below are the **post-fix** set; the earlier
`28aa024e…` / `22f37ca8…` / `0ee9f6bb…` artifacts are superseded and must not be injected.

| DLL | Δ vs `play` | mechanism | size | `.text` len | `.text` sha256[:16] | `[WP]` | `[VTG]` | C++ EH | imports |
|---|---|---|---:|---:|---|---:|---:|---|---|
| `tutorial_launch_play.dll` | — | none | 236,544 | 162,816 | `a67239a0d83d9300` | 0 | 8 | none | KERNEL32 + USER32 |
| `…_play_wprobe.dll` | `-DKWPROBE=1` | **DR0/DR1 hardware 1-byte write watchpoint**, swept over every thread | 256,512 | 174,080 | `6da63dc0ab9fafed` | 46 | 10 | none | + `SetThreadContext`, `GetSystemInfo` |
| `…_play_wprobe2.dll` | `-DKWPROBE=2` | **`PAGE_READONLY` process-wide write trap** on the page holding `&Target` | 254,976 | 174,080 | `0ec5a66b7028623a` | 39 | 10 | none | + `GetSystemInfo` |
| `…_play_wprobe_noxformfix.dll` | `-DKWPROBE=1 -DKXFORMFIX=0` | DR, on the build vintage that actually crashed | 256,512 | 174,080 | `d65fb5f0067a9e1c` | 46 | 10 | none | as `wprobe` |

The build is **deterministic**: rebuilding `play-wprobe` from a clean tree reproduces `6da63dc0ab9fafed`
byte for byte, so the DLL on disk is provably this source.

**`play` is byte-unchanged — proven, not claimed.** A probe-stripped copy of `tutorial_launch.cpp`
(every `#if KWPROBE …#endif` region and the probe comment block mechanically deleted) was compiled with
the same clang invocation: `.text` is **162,816 bytes, sha256 `a67239a0d83d9300`** — *identical* to the
`play` built from the probe-carrying source. All 23 `RunMode`s are intact (`RM_FORCEOPEN=0` …
`RM_PLAY=22`, contiguous), and `-DKWPROBE=1` compiles clean under `RM_FORCEOPEN` / `RM_CHEATSPAWN` /
`RM_TOPDOWNCAM` / `RM_PUPPET` as well.

`SetThreadContext` appearing **only** in `wprobe` is an independent single-dimension confirmation: the
page build genuinely does not touch debug registers.

Both are data-only instruments — debug registers and page protection, no `.text` patch — which is
exactly why they survive the ~3–5 min code-integrity check.

> ⚠ **Never build `wprobe` together with `KVTGUARD=0`.** `KVTGUARD=0` compiles out `VtGuard`'s body, so
> `VtResolve` never runs, the arm request never fires, and the probe **never arms and never self-tests —
> silently**. Measured: `tutorial_launch_play_novtguard.dll` contains 0 `[VTG]` strings. No such variant
> is registered, and none should be added.

#### The S107 review fixes (why the hashes moved)

| | defect | consequence if shipped |
|---|---|---|
| **D1** | page mode armed `PAGE_READONLY` ~100–200 µs (a whole `Markerf`) **before** setting `g_wpArmed`, and the handler's first line is `if(!armed) return false` | any write in that window → unhandled AV. `ViewTarget.POV` shares the page in 5/5 dumps and is written every frame. **Crash-shaped.** Fixed: flag and pend table first, protection second |
| **D2** | on a readback mismatch the page was left **read-only with the handler off** | guaranteed crash next frame, misreadable as FK-7. Fixed: restore protection before giving up; and the readback now tests *coverage* (a coalesced region is a valid arm), not exact base identity |
| **D3** | `WpDisarm` cleared `g_wpArmed` **before** walking ~140 threads clearing DR7 (3–5 ms) | a DR hit in that window propagated as an unhandled `STATUS_SINGLE_STEP` → process death. Reachable mid-session via the `retarget` path. Fixed: hardware first, flag last, plus a 2 s grace window in the handler |
| **D4** | with `Dr6` unavailable the probe claimed **every** single-step in the process | swallows the packer's own anti-debug stepping for the whole hold. Fixed: `EFlags.TF` is an architectural discriminator (a DR *data* breakpoint does not set TF) — TF-set steps are handed back, the residue is counted and the verdict declares the run instrument-suspect |
| **D5** | `ROW5` and `ROW7` were **dead code** — gated on `traps==0`, but `selftest==PASS ⟹ traps>0` by construction | the headline verdict named the wrong row and prescribed the wrong next step. Fixed: rows gate on `nonSelfAtTarget`; ROW2 and ROW5 are **merged** (they are one observable once the selftest and the guard both write `&Target`) and carry ROW5's escalation |
| **D6** | a non-game thread already using our DR pair got its `Dr0/Dr1` clobbered and its R/W+LEN bits OR-merged into nonsense | fixed: detect and **step aside**; the resulting hole is counted as `busySkipped` and reported as a VOID for those threads |
| **D7** | the 64-entry RVA novelty table **saturated open** — past 64 RVAs every trap logged in full | fixed: full ⇒ nothing is novel; census counters stay exact and a corrupting store still logs in full |
| **D8** | `g_wpTids` never evicted dead tids; at the 2048 cap `newly-armed` became permanently non-zero | poisons the W5 coverage signal. Fixed: the armed set is rebuilt from each sweep's snapshot |
| **D9** | `WPF_SELFTEST` was defined and **never set** | a selftest trap was indistinguishable from `VtGuard`'s repair store, so the B0/B1 width discriminator was never validated against ground truth. Fixed: a latch labels each selftest store, and the summary now prints `width-discriminator: VALIDATED` / `*** NOT VALIDATED ***` |

#### Which DLL for which experiment

| Question | Inject | Read |
|---|---|---|
| Who stores the `0x01` byte? | `play-wprobe` | `[WP] VERDICT:` — `ROW1` names the writer (rva + instruction bytes + which register held the PCM) |
| Did the instrument actually run? | either | `[WP] selftest *** PASS` (an in-session positive control aimed at `&Target` itself). **Absent ⇒ the sitting is VOID, stop and fix the instrument** |
| Does the packer clear debug registers? | `play-wprobe` | `dr7ReadbackZero` in `[WP] arm sweep#…`, and any `[WP] *** W2` line. Non-zero ⇒ VOID ⇒ escalate to `play-wprobe2` |
| Was the store one byte or a whole pointer? | `play-wprobe` | `[WP]   width:` — `B0 ONLY` = 1-byte store (the FK-7 shape); `B0+B1` = an 8-byte pointer store. **Hardware**, which is what replaces the retracted `+0x3F` delta |
| Does *our own shim* write it? | either | `origin=SELF` on the trap line (free to test; never tested before) |

> **Escalate `wprobe` → `wprobe2` only on a VOID verdict, never on a clean negative.** MEASURED base
> rate for the camera bug is 1-in-3 … 1-in-2 per launch, so `P(all quiet | 6 launches) ≈ 9 %` —
> **budget ≥ 6 launches**. Every launch still emits the selftest and the trap census, so a quiet launch
> is informative *about the instrument* even when it says nothing about the bug.

### FK-22 round-phase ladder artifacts (`tutorial_launch`, **S124, 2026-08-16**)

`RM_PHASELADDER` (enum **24**) runs the pre-registered FK-22 arms **A0'…A5**
(`docs/fk22-dropphase-reachability.md` §8–§12) with **zero module-image writes**.

⚠ **It is a NEW enum value. `RM_GOTOPHASE` (2) is untouched** — that mode arms with `InstallHook()`,
a standing `ProcessInternal` `.text` patch (S112: **10/10 armed windows dead vs 3/36**, Fisher
p = 0.00000008), and several docs reference its behaviour by name. Nothing that already existed
changed: `play` rebuilds **byte-identically** to `9bc10a4552c596e1` from the modified source
(measured, before/after).

Arming is RM_PLAY's heap `UFunction.Func` (+0xE0) swap verbatim (`FsArm`/`FsHold`/`FsDisarm`,
`KFUNCSWAP`/`KFSNAME`). With `KFUNCSWAP=0` the mode **refuses to run** and says why, rather than
silently falling back to the `.text` hook.

| Knob | Default | What it does |
|---|---|---|
| `KPLARMS` | `0x3F` | Which arms run. bit0 A0′ · bit1 A1 · bit2 A2 · bit3 A3 · bit4 A4 · bit5 A5 |
| `KPLHOLDMS` | `2000` | A4: how long `GameState+0xA44` is held at `3` before the STOP poke to `4` |
| `KPLHOLDHITS` | `600` | A4: hard cap on game-thread callbacks during that hold (clock-independent) |
| `KPLWDGRACEMS` | `5000` | How long past `KPLHOLDMS` the watchdog waits before forcing the STOP itself |
| `KPLSTEPMS` | `400` | Minimum spacing between ladder steps (one arm per game-thread hit) |
| `KPLMODEHOLDMS` | `90000` | Ceiling on the whole sitting; a normal run sets `g_done` and returns in ~5 s |

**Effects, exhaustively:** two `GoToPhase` calls, one `BP_AuthSetCurrentPhase` call, and **one byte**
of heap data (`GameState+0xA44`, poked to `3` and back to `4`), readback-verified in both directions.

**The A4 runaway has four independent stops** — while `+0xA44 == 3` the game's own Tick calls
`GoToPhase(4)` every frame and the phase store is dead (`0xF7EC20 = ret 0`), so it never self-clears:
(1) elapsed ≥ `KPLHOLDMS`; (2) hits ≥ `KPLHOLDHITS`; (3) `PhWatchdog`, a plain worker thread that does
**not** depend on game-thread dispatch; (4) the `__except` handler around every step **and** an
unconditional call at mode exit after `FsDisarm`. `PhaseRestore` is idempotent, thread-safe, and only
latches *restored* after a **verified readback**, so a transient failure is retried, not stranded.

| variant | `.text` sha256 | use |
|---|---|---|
| `phaseladder` | `de08812f6cc173fd` | ★ **CANDIDATE** — full A0′…A5, arms on `ReceiveTickClient` (in-world) |
| `phaseladder-any` | `18b5d73ef08c02c1` | +1 dim: swaps **every** BP UFunction. Use if the 8 s verdict reads `NO GAME-THREAD HITS` |
| `phaseladder-readonly` | `39240e4b4a71f559` | −1 dim: **A0′ only** — pure RPM, zero calls, zero writes. The staging positive control |
| `phaseladder-nopoke` | `9e8a6132ba7bf5b7` | −1 dim: A0′…A3 — both `GoToPhase` calls, **no** poke and **no** broadcast |

⚠ **These four are near-identical in size (177,664 – 184,832 B) and two of them differ by 512 B.**
Diff `.text`, never size — `tools/sigbypass-mod/verify_dll.py`, or the section-hash snippet in
`docs/s109-dump-forensics.md` §23.

**No-`.text`-write receipt, with a positive control from the same source file** — `SafeWrite`/`BuildHook`
are dead-code-eliminated because `kRunMode` is a compile-time constant:

| DLL | `FlushInstructionCache` | `VirtualAlloc` | `VirtualFree` |
|---|---|---|---|
| `tutorial_launch_phaseladder.dll` | absent | absent | absent |
| `tutorial_launch_phaseladder_readonly.dll` | absent | absent | absent |
| `tutorial_launch_play.dll` (shipping, measured-safe) | absent | absent | absent |
| **`tutorial_launch_fo.dll`** (does call `InstallHook`) | **PRESENT** | **PRESENT** | **PRESENT** |

⚠ `ReceiveTickClient` is **MEASURED not dispatched at the menu** (S114), so `phaseladder` is a silent
no-op there — but the mode is meaningless at the menu anyway (no live `GameMode_Tutorial`) and
`PhResolve` aborts by name with a candidate enumeration. Inject into the **staged tutorial world**.

---

## Adding a new shim

1. Drop `myshim.cpp` in this directory. `build.ps1 -All` and `-Name myshim` pick it up automatically —
   the file list is globbed, not hard-coded.
2. Keep it **exception-free** and **static-CRT** (see constraints above). The build will reject it
   otherwise, with the reason.
3. If it hooks `ProcessInternal`, follow the transient-install + `Local\SuperviveMissionsPIHook`
   pattern. Copy it from `missions_fix.cpp`.
4. Only if it has a compile-time mode switch, add a `$Variants` entry.
5. If it must be injected on every launch, add it to `$DefaultSet` **and** to
   `configs/inject-secondaries.ps1`.
6. Verify before shipping:
   ```powershell
   .\build.ps1 -Name myshim          # must print ok, not REJECTED
   ```

Do **not** rely on the `// Build:` comment at the top of each `.cpp`. Several are wrong (see the link
library section). `build.ps1` is the source of truth.

---

## Reproducibility status

`.\build.ps1 -All` builds **81 targets (63 shims + variants), 0 failures** *(re-measured S106d,
2026-07-29 — was 79 before the FK-7 variant table was rebuilt)*, every one passing both constraint
gates. The default set additionally reproduces the committed DLLs bit-for-bit apart from the embedded
timestamp.

Two caveats when comparing binaries by hand:

* The build is deterministic — the same source, flags and **output name** give a 3-byte
  (timestamp-only) difference.
* Shims that export symbols embed the **output file name** in the export directory, so building the
  same source to a *differently named* DLL shifts following data and produces a much larger diff.
  Compare like-named outputs only. (`-Verify` does this correctly.)

---

## What belongs in git

**Committed:** every `.cpp`, `build.ps1`, this file, and the `.ps1` helpers.

**Not committed:** `*.dll`, `*.exp`, `*.lib`, `*.obj`, and `build/` — covered by the local
`.gitignore`. Binaries are deliberately excluded because the build is now reproducible from source
(any DLL can be regenerated exactly), they are large and numerous (141 DLLs, tens of MB), and a stale
committed binary that silently disagrees with its source is worse than no binary at all.

The one argument for committing them — a clean clone cannot inject anything until it has clang and a
VS toolset — is answered by `build.ps1` taking under two seconds per shim.
