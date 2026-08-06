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

That build already exists (it *is* arm C's primary). Injected alone it performs the `.text` `jz`-NOP
and **nothing else** — no scan, no PI hook — at the **same image count as arm D**. So arm E vs arm D
is a genuine one-variable comparison:

| | images | `.text` patch | PI hook |
|---|:--:|:--:|:--:|
| D | 1 | ✗ | ✗ |
| **E** | **1** | **✓** | ✗ |

- **arm E dies ~30 %** → the `.text` `jz`-NOP is the trigger. That is very good news: the patch is
  already self-restoring and its lifetime is tunable, or it can be replaced by the data-only
  `[+0x354]` poke the shim already performs as belt-and-braces.
- **arm E is 0/11** → the `.text` patch is innocent too, and suspicion moves to the PI prologue
  writes or to image count. Arm F (`-Hook mainmenu_refresh_pi8.dll`, a PI-hooker alone) splits that,
  and five copies of `nulldll` would settle the count question.

No new code is required for arm E. ~1 hour for 11 runs.

## 4. State

No game running. `catalog_store_fix.dll` = the S111 fix (`SAFECOPY-S111` present). `nulldll` is a
**control artifact**, is not in `$DefaultSet`, and is never injected by any normal launch.

```
.\build.ps1 -Name nulldll
scratchpad\armd.ps1 -Tag D -N 1 -HoldSeconds 320    # treatment = inject log changed + names nulldll
```
