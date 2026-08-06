# S111 — arm E. ★ **The trigger is the primary shim's own activity, not mapping.**

**2026-08-06 17:03 → 17:34. 8 launches × 320 s hold, ONE `catalog_store_fix_noscan.dll` mapped alone**
via `-Hook` (exactly one DLL, no secondaries). Total across the S111 series: **131 launches**.

---

## 0. The complete injection ladder

All arms, same boot, same machine, menu route, `-NoMissions`-equivalent conditions.

| arm | what was injected | runs | hold | **protector deaths** |
|---|---|---:|---:|---:|
| — | `-NoHook`, nothing at all | 11 | 320 s | **0 (0 %)** |
| **D** | ONE **inert** DLL (`nulldll`), mapped | 11 | 320 s | **0 (0 %)** |
| **E** | ONE `catalog_store_fix_noscan`, mapped | **8** | 320 s | **7 (88 %)** |
| C | FIVE DLLs, primary's scan disabled | 30 | 60 s | 9 (30 %) |
| A+B+C pooled | FIVE DLLs, full logic | 90 | 60 s | 25 (28 %) |

### ★ arm E vs arm D — **p = 0.00016**

Both arms: **320 s hold, ONE manually-mapped image, same injector, same boot.** They differ in
exactly one thing — whether that image *does anything*. Arm D's inert DLL survived 11/11. Arm E's
active DLL died 7/8, all family A (`runtime.dll+1`, EXECUTE), at 48 / 76 / 133 / 136 / 139 / 221 /
294 s.

**Treatment verified 8/8** by requiring `docs/inject-watch.out.log` to change *and* name
`catalog_store_fix_noscan`.

## 1. ⚠ Arm E's 88 % is NOT a higher hazard than the 5-DLL arms — that is a hold-time artifact

The headline rates tempt a wrong reading ("one shim is worse than five"). Arm E holds **320 s**; the
5-DLL arms held **60 s**, so arm E has 5.3× the exposure. Matching the window:

> deaths within the first 60 s — **arm E 1/8 (12 %)** vs **pooled 5-DLL 25/90 (28 %)**, p = 0.92.

**Arm E is not elevated once exposure is matched.** Its high headline number is the longer hold, and
nothing else. Do not cite 88 % against 28 %.

## 2. What is now established, and what it means

With arm D having cleared manual mapping, and arm E dying at the same image count, the trigger is
**something the primary shim's worker thread does**. That is a large narrowing — but arm E does
**not** name a single action, because `KNOSCAN=1` still leaves five distinct behaviours running:

| # | action | notes |
|---|---|---|
| 1 | marker file I/O (`CreateFileA`/`WriteFile`) | mundane; least likely |
| 2 | `SnapshotModules()` | walks the module list |
| 3 | **`AddVectoredExceptionHandler`** | installs a VEH into a process whose protector *uses* VEH |
| 4 | **`BuildStub` — allocates executable memory** | RWX/RX private allocation |
| 5 | **slot-110 vtable hook** (`VirtualProtect` + write) + **`.text` `jz`-NOP** | writes into module memory |

⚠ **My earlier claim that arm E tests "the `.text` `jz`-NOP and nothing else" was wrong** and is
corrected in `docs/s111-armd-nulldll.md` §3. Arm E is "the primary's whole activity minus the scan".

**The three interesting suspects are (3), (4) and (5)** — a VEH installed into an anti-tamper process
that itself dispatches through VEH; an executable private allocation; and writes into the module
image. All three are exactly what a protector watches for.

## 3. Next — bisect inside the primary, ~1 hour, no new experimental design

Add `-D` switches to `catalog_store_fix.cpp` and run each at arm D/E's conditions (1 image, 320 s).
Each is a one-variable step down from arm E:

| arm | change from E | isolates |
|---|---|---|
| E1 | `KNOVEH=1` — skip `AddVectoredExceptionHandler` | the VEH |
| E2 | `KNOSLOT=1` — skip the slot-110 hook + `BuildStub` | exec alloc + vtable write |
| E3 | `KNOJZ=1` — skip the `.text` `jz`-NOP | the module-image write |

Whichever restores arm D's 0 % is the trigger. **All three are droppable or replaceable in
production**: the VEH is a *diagnostic* crash logger, not a fix; the slot-110 hook is used only to
trigger the AssetManager scan once; and the `jz`-NOP already has a data-only alternative (the shim
pokes `[+0x354]` as belt-and-braces). So whichever one it is, there is a plausible fix.

⚠ Run the bisect at **320 s holds and ~10 runs/arm** — at 60 s the effect is only ~12–28 % and the
arms will not separate.

## 4. State

No game running. `catalog_store_fix.dll` = the S111 fix (`SAFECOPY-S111` present, no arm-C string).
`catalog_store_fix_noscan.dll` and `nulldll.dll` are control artifacts in `build\` only — neither is
in `$DefaultSet` and neither is injected by a normal launch.

```
scratchpad\arme.ps1 -Tag E -N 1 -HoldSeconds 320   # treatment = inject log changed + names noscan
python tools/crashtri/fk8_classify.py dumps/crashpad-*s111arme-*
```
