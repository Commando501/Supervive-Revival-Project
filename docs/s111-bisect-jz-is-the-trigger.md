# S111 — the bisect. ★★ **The `.text` `jz`-NOP is the trigger.**

**2026-08-06 17:39 → 18:17. 17 launches × 320 s hold, one image each.**
Total across the S111 experimental series: **148 launches**.

Three one-variable builds, each `KNOSCAN` (= arm E) **minus one behaviour**. Every arm mapped alone
via `-Hook`; treatment verified per run (inject log changed **and** named the exact DLL), and each
build stamps its own identity into the marker (`veh=n slot=n jz=n`).

---

## 0. Result

| arm | VEH | slot hook + exec stub | **`.text` `jz`-NOP** | deaths |
|---|:--:|:--:|:--:|---:|
| E | on | on | **ON** | **7/8** |
| E1 `KNOVEH` | **OFF** | on | **ON** | **2/2** |
| E2 `KNOSLOT` | on | **OFF** | **ON** | **2/2** |
| **E3 `KNOJZ`** | on | on | **OFF** | **0/5** |

> **patch standing (E+E1+E2) 11/12 vs no patch (E3) 0/5 — p = 0.00097**

Removing the VEH did nothing. Removing the executable stub and the vtable hook did nothing.
**Removing the single 2-byte `.text` write stopped every death.** All deaths were family A
(`runtime.dll+1`, EXECUTE), the same signature throughout.

## 1. ★ This is the project's oldest rule, finally measured

`CLAUDE.md` has said since S43: *"Don't leave a permanent `.text` patch in place — the ~3–5 min
code-integrity check catches it and kills the process."* That was an inference from one A/B. It is
now a **direct, one-variable measurement**, and it is the mechanism behind the death class that has
been mis-attributed for this whole series.

⚠ **And it exposes a flaw in arms C/E/E1/E2 that must be recorded.** `catLoadedAt` is set only when
the scan finds the CatalogManager (`catalog_store_fix.cpp:501`), and the `jz` self-restore is gated
on it (`:512`). Under `KNOSCAN` the scan returns 0, so **the restore never fires and the patch stands
for the entire run** — which production never does. So those arms were unintentionally testing
"permanent patch", not "the shim as shipped". That is exactly why arm E died at 88 % while
production arm A died at 30 %.

## 2. ★★ The same mechanism explains production, at shorter exposure

This is the part that matters. In production the patch **is** applied — it just gets restored:

- applied within a few seconds of the worker starting,
- restored **6 s after the catalog loads**, which is ~10–40 s in.

So production carries a standing patch for roughly **5–45 s**. And arm A's 11 deaths landed at
**12, 24, 24, 24, 27, 27, 27, 33, 33, 36, 61 s** — clustered 24–36 s, **inside that window**.

**One mechanism accounts for the whole ladder:** `-NoHook` 0 %, inert DLL 0 %, patch-restored
production ~30 %, patch-standing controls ~90 %. The rate tracks *how long a `.text` modification is
left in place*, and nothing else we varied.

## 3. What to do about it — and there is already an alternative in the file

The `jz`-NOP exists to make `IsCatalogDataReady` ignore the never-set 5th flag. But the shim
**already** pokes the same condition as **data**:

```cpp
// belt-and-suspenders data poke of [+0x354]=1 on the live instance
if(g_catMgr){ ... ((uint8_t*)(g_catMgr+kReadyOff))[4]=1; ... }
```

Ordered by cost:

1. **Drop the `jz` patch and rely on the `[+0x354]` data poke alone.** If the roster/store still
   populate, the entire death class goes away — a data write into a heap object is not a `.text`
   modification. **This is the experiment to run next**, and it is a one-line `-D` away.
2. **If the patch is still needed, shrink its window.** It is currently applied immediately and held
   until catalog-load+6 s. Applying it only just before the readiness check, or restoring on a short
   timer instead of on catalog-load, cuts the exposure that drives the rate.
3. **Do not bother hardening the VEH or the slot hook** — E1 and E2 show neither contributes.

## 4. Scope

- **N is modest**: 11/12 vs 0/5, p = 0.00097. Decisive for the contrast, but E1/E2 are only 2 runs
  each — they establish "removing this did not save it", not a precise rate.
- **One boot, one machine, menu route.**
- The production inference in §2 is **INFERRED**, not directly tested: it rests on arm A's death
  times falling inside the computed patch window. Testing it directly is exactly proposal (1).
- All arms here are `KNOSCAN` controls and **none is a shippable build**.

## 5. State

No game running. `catalog_store_fix.dll` = the S111 fix (`SAFECOPY-S111`). `KNOVEH`/`KNOSLOT`/`KNOJZ`
all default **0**; each is reachable only through its registered `build.ps1` variant, which emits a
differently-named DLL. All six variant `.text` hashes were diffed and are distinct — note
`noscan_nojz` and `noscan_noslot` share both file **and** `.text` size (140,800 / 84,992) and differ
only in hash, exactly the identical-artifact footgun `CLAUDE.md` warns about.
