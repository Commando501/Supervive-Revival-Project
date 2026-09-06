# FK-7 handoff — the tutorial route, audited against S111's findings

**Written 2026-08-07 at the end of S111.** Three read-only audits: the tutorial shims' memory writes,
the surviving FK-7 evidence, and the staging preconditions. Nothing here was run live.

---

## 1. ★★★ The finding that reframes FK-7

**`tutorial_launch.cpp:6506-6513` (RM_PLAY):**

```cpp
if(!InstallHook()){Marker("[PL] FAIL InstallHook\r\n");return 6;}
DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<600000) Sleep(20);  // ~10 min
UninstallHook();
```

`InstallHook` writes a 5-byte `0xE9` jmp into `ProcessInternal` (`kPiRva=0x13454A0`) through
`VirtualProtect(PAGE_EXECUTE_READWRITE)` — **module `.text`**. Line `:995` confirms **RM_PLAY never
sets `g_done`**, so the patch stands the full **600 s**.

S111 measured that **a standing `.text` write is the protector-kill trigger**:

| condition (320 s hold) | runs | protector deaths |
|---|---:|---:|
| nothing injected / inert mapped DLL | 0/11, 0/11 | **0 %** |
| permanent **bytecode** patch (heap) | 0/9 | **0 %** |
| 3 × **transient** `.text` prologue | 4/12 | 33 % |
| 1 × **standing** `.text` write | 7/8 | **88 %** |

⇒ **Every FK-7 sitting ever run held the 88 %-lethal condition for its entire duration**, and the
600 s window brackets the whole observed FK-7 death spread (87–524 s). Two independent audits reached
this separately. The source even documents the asymmetry — `:1036`: *"menu shims hold the lock for ONE
game-thread call; tutorial modes hold the hook for 20 s..10 min"* — written about mutex contention,
but read against S111 it is the finding.

### The rest of the tutorial route's module-image writes

| # | writer | class | standing window |
|---|---|---|---|
| **1** | `play` PI prologue jmp (`:6511`→`:6513`) | **`.text`** | **600 s** |
| 2 | `fo` slot-285 `CustomLogin` × 5 vtables (`:6570`→`:6593`) | `.rdata` | ≤ 25.5 s |
| 3 | `fo` PI prologue jmp (`:6572`→`:6574`) | `.text` | ≤ 8 s |
| 4 | `sp` PI prologue jmp (`:6555`→`:6557`) | `.text` | ≤ 8 s |
| 5 | `fo` PC-vtable de-override ≤4 slots (`:6198`→`:6215`) | `.rdata` | ~ms |

Cumulative ≈ **640 s** of module-image modification per staged sitting.

**Clean — no module-image writes at all:** `gft_ready_fix` (its only write is a heap flag,
`gft_ready_fix.cpp:85`), `inject.exe` (writes only `VirtualAllocEx`'d memory), and `sp`/`play`'s
non-PI work (all heap UObject fields).

⚠ **Open, and cheap to test:** rows 2 and 5 are `.rdata`, not `.text`. S111 measured `.text`. The
shim asserts `.rdata` is also caught (`:63-64`, an S61-era inference) but that has **never** been
tested under the S111 protocol.

## 2. What survives of the FK-7 evidence base

Starting from **51 distinct tutorial-route deaths**, after removing the crashpad class (13, all
self-inflicted), asserts (16), hangs (5), and the FK-24 probe self-kills (2) → **15 remain**. Four
more (`A15041E9`, `10CF9C87`, `E7323D14`, `471B4885`) are `ProcessInternal`-depth faults already
classified in `s108-crash-triage.md:361-380` as *"a signature of the instrument's entry point, not of
a bug"* — `0x1345511` sits **inside** the `ProcessInternal` extent.

> **⇒ 11 records remain. Ten are one 15-hour stretch (2026-07-24→26), nine of those inside a single
> 2 h 55 m sitting. Exactly one — `UECC-C13252F5`, 258 s, 2026-08-05 — is from the current era.**

**All 11 are shim-mediated**, and `log_forceopen_tutorial_url == 2` in **15/15** — there is **no
shim-free tutorial run anywhere in the corpus**. The two named families are, by the project's own
measurements, a shim-object corruption (camera: the corrupted `ViewTarget.Target` is the shim's own
spawned actor, proven via `KCAMPITCH -66.0`) and a shim-lifetime bug (anim: a freed `UAnimationAsset`
the shim loaded and never rooted — S110 measured the collection outright; fixed by `KANIMREF`).

**Honest verdict: there is no surviving evidence that FK-7 exists as a game defect.** The strongest
counter-arguments, stated fairly: byte-identical RVA chains across different ASLR bases are genuinely
not stochastic (but a deterministic *shim* explains that equally well); `C13252F5` shows the anim
family did not vanish; and the `0x01`-byte writer is still unnamed, so game code is not formally
excluded.

**Exposure denominator (new):** `docs/gft-ready-marker.txt` holds 81 `injected; base=` records.
Grouped by ASLR base (per-boot): **49 share `base=0x7FF6E7D30000`** — the era-B base of every era-B
crash ⇒ **~10 deaths / 49 staged force-opens ≈ 20 %**. Era-C base: **1/16 ≈ 6 %**.

⚠ **The mandated control budget is unaffordable as specified.** The `play_novtguard` positive control
fires only on the camera family, which appears ~4 times in 49 staged force-opens (~8 %).
`P(all 3 controls quiet) ≈ 0.92³ ≈ 78 %` — **the 3-control gate would declare the sitting VOID ~4
times in 5 even when everything works.** Either the control changes, or FK-7 verification as
currently designed cannot be executed. **Resolve this before spending launches.**

## 3. ★ The fix to build: `UFunction.Func` (+0xE0) pointer swap

Replace the `ProcessInternal` `.text` hook with a **heap** write, which S111 measured as free.

`UFunction.Func` is a field of a heap UObject. The shim **already reads it** (`:25` `UFUNC_FUNC=0xE0`;
`:1130` `*(uintptr_t*)(f+UFUNC_FUNC)`) — the whole native-call primitive is built on calling through
it. For a Blueprint `UFunction`, `Func` *is* `&ProcessInternal`, which is exactly why hooking
`ProcessInternal` intercepts BP dispatch. Overwriting `Func` on one chosen, frequently-called BP
`UFunction` with a pointer to the shim's own stub gives:

- the **identical callback signature** — `:34` `typedef void (*PFN_THUNK)(void*, void*, void*)` matches
  `OnPI(void*, void* frame, void*)` at `:970` exactly;
- the **same live `FFrame`** the shim captures today (`:975`);
- pass-through by saving the original `Func` and tail-calling it, as `g_tramp` does now;
- **zero module-image bytes touched**, and no need for `SafeWrite`'s whole-process thread suspend.

**Requirements / risks, stated honestly:** the chosen function must fire on the game thread at the
cadence RM_PLAY needs (camera re-assert, WASD, VtGuard — several times per tick); the existing
`hitsGT` counter makes that measurable before committing. Do not pick a function the shim itself
invokes via `CallNative`, or the stub re-enters. **Unproven:** arm J validated that the protector does
not checksum `UFunction.Script`; `Func` is a field of a *different* heap allocation. A ~10-run control
settles it at the same cost as any other arm.

**Fallback if that is not viable:** `-DKPLAYHOLDMS=<ms>` to shrink the 600 s hold to the experiment
length. Strictly worse, one line, still moves the variable. ⚠ Do **not** duty-cycle
(install/uninstall repeatedly) without evidence — S111 varied *duration*, not the *number* of write
events, so trading one long window for many short ones is speculative.

**Also worth one build:** `-DKNOLOGINVT=1` to drop `fo`'s slot-285 vtable patch (row 2). Its stated
purpose (`:6582-6588`) is to stop native `Login` fataling during deferred travel — whether that is
still true after S107/S108 made the world load reliably has **never been tested**, and it removes a
≤25 s module-image window.

## 4. Dead code — do not count these as writers

`PatchLoginVtables` (`:324`) and `InstallGameSessionDeoverride` (`:6261`) are **defined but never
called**. The entire `KWPROBE` block is `#define KWPROBE 0` and not compiled into `play`.
`KSTATICTEST` and `KTESTACTOR` both default to 0.

## 5. Pre-flight checklist

| # | item | status | action |
|---|---|---|---|
| 1 | RM_PLAY 600 s standing patch | **NEEDS DECISION** | build the §3 variant, or at minimum pre-commit to fault-family classification |
| 2 | `forceTutorialMatch` | **NEEDS ACTION** — `false` at `interactive.go:558` | set `true`, then `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags` |
| 3 | `play-novtguard` control | **NEEDS ACTION** — stale 2 generations; deployed copy still has `KSTATICTEST`; build copy lacks `KANIMREF` | `.\build.ps1 -Name tutorial_launch -Variant play-novtguard` (differs from `play` in ≥3 dimensions until rebuilt — breaks the one-variable rule) |
| 4 | stale `docs/tutorial-launch-marker.txt` | **NEEDS ACTION** — contains `[SP] done step=4`; `Stage-Inject` never checks `inject.exe`'s exit code ⇒ a failed `sp` passes the gate instantly | `Remove-Item docs\tutorial-launch-marker.txt` |
| 5 | probe path | **USE `build\`** — deployed `tutorial_launch_play.dll` is byte-identical to `play_statictest` (`a67239a0d83d9300`) | `-Probe tools\sigbypass-mod\build\tutorial_launch_play.dll` |
| 6 | `play` `.text` vs CLAUDE.md | **OK** — `513c6277c3ae88f3` matches | — |
| 7 | `ConnectionDetails.address` | **OK** — already `""` | — |
| 8 | staging shims deployed == build | **OK** (gft / fo / sp) | — |
| 9 | git tree | **OK** — no code changes pending | — |
| 10 | injection exit code unchecked | **GAP** | inspect `docs\fk24-stage-<label>-N-*.txt` after each stage |
| 11 | no build stamp in tutorial shims | **GAP** | S111's stamp went only into `catalog_store_fix`; consider porting it |

**Current `.text` hashes:**
```
build/tutorial_launch_play.dll             236,032  .text 162,304  513c6277c3ae88f3  <- CANDIDATE
tools/sigbypass-mod/tutorial_launch_play.dll
                                           236,544  .text 162,816  a67239a0d83d9300  <- = statictest, DO NOT USE
build/tutorial_launch_play_novtguard.dll   231,424  .text 158,720  b931e1de2733aee3  <- STALE control
gft_ready_fix.dll                          134,656  .text  80,896  6b2fe2c2a747c19f
tutorial_launch_fo.dll                     157,184  .text  98,816  fa184b20934cc4b0
tutorial_launch_sp.dll                     198,656  .text 134,144  4285c0dd22ae9976
```

## 6. Stale claims in the FK-7 docs — do not act on these

- `fk7-crash-settled.md:1` *"deterministic, not flaky"* → ~20 % per staged launch.
- `:26` *"4 launches / 4 crashes"* → a 4-run sample from one sitting.
- `:177-181` *"camera bug is 1-in-3 to 1-in-2 per launch"* → **denominator error, still live**: those
  cohorts count **crashes**, not launches. Per launch ≈ 4/49 ≈ **8 %**. This propagates into the
  ≥6-launch budget in `memory/supervive-tutorial-crash-fk7.md` and `ignorance-map-s101.md:854, :886`.
- `:1273` *"the code-integrity confound never operated — patch uptime 60–79 s vs ~285 s kill latency"*
  → **contradicted.** S111 measured the hazard as a function of *how long a patch stands*; 60–79 s is
  squarely lethal. **Re-open.** (Source line is now `:6511-6513`.)
- `:1201`, `:295`, `:306`, `:1153` — any `T+<n>` hold rule → use the map-load anchor.
- `:167`, `:310` *"poison RIP `0x7FF90E000001`… present exactly once"* → it is `<runtime.dll base>+1`,
  one boot's instance, **N=24**.
- `:203-208` artifact matrix hashes → all stale; `a67239a0` is now `play-statictest`.
- `:993`, `:1024` *"delete `tutorial_launch_play.dll`, it's the stale pre-fix build"* → obsolete and
  now dangerous; `play` **is** the candidate and carries `KANIMREF`.

## 7. Genuinely unknown

- Whether **any** tutorial death is game-caused. No shim-free tutorial run has ever been made.
- **Who writes the `0x01` byte** into `ViewTarget.Target`. Unnamed since S106; the offline search is
  exhausted over ~52 % of `.text`; the live DR probe killed the host twice and never caught it.
  Leading unexplored suspect: **our own shim's diagnostic block** inside the +0.15 s window.
- Whether the **camera family reproduces on any current build** — its 4 dumps span 3 vintages, none
  the candidate's, newest 2026-07-26.
- What **routes a death to crashpad vs CrashReportClient**. Tutorial-route crashpad deaths are 100 %
  self-inflicted while its UECC deaths are 0 % — nobody knows if that asymmetry is real or a routing
  artifact.
- The **artifact-less death class** — `CrashReportClient.ini` sets `Stall.RecordDump=false`, so hangs
  are *configured* to leave nothing.
