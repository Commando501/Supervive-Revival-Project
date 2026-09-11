# S111 — arm D, the inert-DLL control. **Manual mapping is NOT the trigger.**

**2026-08-06 15:50 → 16:53. 11 launches × 320 s hold, ONE do-nothing DLL manually mapped.**
Total across the S111 experimental series: **123 launches**.

Arm D injects `tools/sigbypass-mod/nulldll.cpp` — `DllMain` calls `DisableThreadLibraryCalls` and
returns `TRUE`. No thread, no patch, no hook, no scan, no file I/O. It is mapped by the **same
injector, the same way** as a real shim (relocations applied, imports resolved,
`RtlAddFunctionTable`, `DllMain` invoked on a remote thread), via
`launch-redirect.ps1 -Hook <dll>`, which injects **exactly one DLL and no secondaries**.

---

## 0. The ladder

| arm | what was injected | runs | hold | **protector deaths** |
|---|---|---:|---:|---:|
| pooled A+B+C | 5 DLLs, full shim logic | 90 | 60 s | **25 (28 %)** |
| C | 5 DLLs, primary's scan disabled | 30 | 60 s | **9 (30 %)** |
| **D** | **1 DLL, completely inert** | **11** | **320 s** | **0 (0 %)** |
| — | `-NoHook`, nothing at all | 11 | 320 s | **0 (0 %)** |

- arm D vs arm C: **p = 0.0408**
- arm D vs pooled injected: **p = 0.0360**
- **arm D vs `-NoHook`: 0/11 vs 0/11 — identical.**

**Mapping an inert image into the protected process is indistinguishable from not injecting at all.**
Every arm-D run cleared 320 s, i.e. 5.3× the window in which the injected arms were dying.

**Treatment verified positively, 11/11.** This was the trap worth guarding: `nulldll` writes no
marker and does nothing observable, so a silently-failed injection would look exactly like `-NoHook`
and a null result would read as "mapping is innocent" — a quiet control mistaken for a pass. Each run
therefore required `docs/inject-watch.out.log` to **change** *and* contain both
`manual-map complete` and `nulldll`. Sample evidence:

```
exception table: 0x14E entries at 0x26B276CB000 (will RtlAddFunctionTable)
DllMain remote-thread exit: 0x1 (DllMain returned BOOL; nonzero = OK)
verify: MZ at 0x26B276B0000 ✓
OK: manual-map complete (DllMain returned).
```

## 1. ⚠ What arm D does NOT separate — and this is the honest limit

Arm D changes **two** variables at once against the injected arms:

1. **inert** vs **active shim logic**, and
2. **one** mapped image vs **five**.

So the clean conclusion is narrow: *mapping one inert image is harmless*. It does **not** establish
that mapping five inert images would be harmless. A per-image or cumulative cost is not excluded by
this experiment.

That said, arm D **does** eliminate the specific hypothesis that motivated it: *"the protector reacts
to manual mapping itself, so no amount of shim-logic tuning helps."* That is now false for the
single-image case, and with it the pessimistic reading — that the fix must be an entirely different
loading strategy — loses its evidence.

## 2. What the remaining suspects are

With mapping-as-such cleared, the surviving candidates are:

- **the self-restoring `.text` `jz`-NOP** (`catalog_store_fix`), and
- **the `ProcessInternal` prologue writes** (`mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`),
- **or the sheer number of mapped images** (1 → 5).

## 3. ★ The next experiment is one line, and it is fully controlled

**Arm E: `-Hook catalog_store_fix_noscan.dll`.**

That build already exists (it *is* arm C's primary), and injected alone it runs at the **same image
count as arm D**.

> ### ❌ CORRECTION — "the `jz`-NOP and nothing else" was wrong
> An earlier draft of this section claimed arm E performs only the `.text` patch. Reading the Worker
> shows `KNOSCAN=1` still leaves a good deal running: it writes a marker file, calls
> `SnapshotModules()`, **installs a vectored exception handler**, allocates an **executable stub**
> (`BuildStub`), **hooks vtable slot 110** via `VirtualProtect`+write, patches the `jz`, and later
> unhooks. Only the memory scan is removed. Arm E is therefore **"the primary shim's whole activity
> minus the scan"**, not an isolated `.text` test.

| | images | shim activity |
|---|:--:|---|
| D | 1 | none whatsoever |
| **E** | **1** | marker I/O + VEH + exec stub + slot-110 hook + `.text` `jz`-NOP |

E vs D is still the largest split available for free — it separates **the primary shim's own actions**
from **the secondaries' PI prologue writes and the 1→5 image count**:

- **arm E dies ~30 %** → the trigger is inside the primary shim itself. A follow-up bisect with new
  `-D` switches (VEH off / slot-110 hook off / `jz` off) then names which of its five actions, and
  each of those is individually cheap to change or drop.
- **arm E is 0/11** → the primary is innocent *alone*, and suspicion moves to the secondaries' PI
  prologue writes (arm F = `-Hook mainmenu_refresh_pi8.dll`) or to image count (5 × `nulldll`).

No new code is required for arm E. ~1 hour for 11 runs.

## 4. State

No game running. `catalog_store_fix.dll` = the S111 fix (`SAFECOPY-S111` present). `nulldll` is a
**control artifact**, is not in `$DefaultSet`, and is never injected by any normal launch.

```
.\build.ps1 -Name nulldll
scratchpad\armd.ps1 -Tag D -N 1 -HoldSeconds 320    # treatment = inject log changed + names nulldll
```
