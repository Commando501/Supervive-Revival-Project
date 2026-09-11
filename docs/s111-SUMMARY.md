# S111 — session summary. The crash corpus, and where ~30 % of every launch was going.

**2026-08-05 → 2026-08-07. 224 live launches.** One sitting, one boot session, menu route throughout.

This session started as "close FK-8" (a false-known about a crash-dump field) and ended having
attributed, measured and largely removed the project's dominant self-inflicted failure mode.

---

## 1. What was established, in order

| # | finding | evidence |
|---|---|---|
| 1 | **FK-8 CLOSED** — `SecondsSinceStart` is a real elapsed measure | permutation control, 0/56 violations, P(0)=0/20000 |
| 2 | The crash corpus is **114 distinct deaths**, not 86/87/92 — and **≥31.6 % are self-inflicted** | full corpus rebuild, `tools/crashtri/fk8_corpus.py` |
| 3 | **All 22 crashpad reports are self-inflicted** ⇒ the S109/S110 tutorial campaign produced **zero** FK-7 evidence | fault-family classification of every report |
| 4 | Our own `catalog_store_fix` scan was killing the process (unguarded TOCTOU at `.text` RVA `0x205d`) | identified to the byte from a minidump code window |
| 5 | **Scan fix confirmed** — 8/30 → **0/30** | pre-registered 60-launch A/B, **p = 0.0023** |
| 6 | `ReadProcessMemory` exonerated as a protector trigger | scan-disabled third arm, 37 % vs 30 %, p = 0.392 |
| 7 | **The protector kill is caused by OUR INJECTION**, not the game | `-NoHook` 0/11 × 320 s vs 25/90 injected, **p = 0.036** |
| 8 | Manual mapping is **not** the trigger | inert DLL 0/11, identical to `-NoHook` |
| 9 | **The trigger is `.text` modification** | one-variable bisect, standing patch 11/12 vs no patch 0/5, **p = 0.00097** |
| 10 | **It is `.text` SPECIFICALLY, not code modification** — permanent *bytecode* patching is free | arm J 0/9 vs standing `.text` 7/8, **p = 0.00041** |
| 11 | The hazard is **cumulative** — it scales with write volume × standing time | 28 % (5 DLLs patched) → 17 % (5 DLLs no-patch) → 4 % (1 DLL) |

## 2. The dose-response, in one table

All at a 320 s hold, one boot, protector deaths:

| what is modified | runs | rate |
|---|---:|---:|
| nothing (`-NoHook`, or an inert mapped DLL) | 0/11, 0/11 | **0 %** |
| UFunction `Script` **bytecode**, heap, **PERMANENT** | 0/9 | **0 %** |
| `.text` prologue × 3, **transient** (PI hooks) | 4/12 | **33 %** |
| `.text` `jz`-NOP × 1, **standing** | 7/8 | **88 %** |

**A permanent patch to code the VM executes is free. A self-restoring two-byte patch to the module
image kills ~88 % of runs.**

## 3. What shipped

- **`catalog_store_fix` scan** rewritten onto a `ReadProcessMemory`-backed `SafeCopy` — cannot fault
  (kernel-mode probe). ⚠ SEH was the trap and was rejected: the packer's **vectored** handler runs
  before any SEH frame handler.
- **The `.text` `jz`-NOP is gone from the shipping build** (`KNOJZ` defaults to 1). The roster still
  renders because the shim's existing `[+0x354]` **data** poke suffices — screenshot-verified.
  Rollback: `build.ps1 -Variant jzpatch`.
- **Marker build stamp** (`build=<date> <time> scan=… veh=n slot=n jz=n`) so any run is attributable
  to an exact build from its marker alone — closes ignorance-map gap F3 in practice.
- **New tools**: `tools/crashtri/fk8_corpus.py` (139-row corpus), `fk8_classify.py` (fault-family
  classifier, dedupes by report uuid), `tools/sigbypass-mod/tests/` (the project's first shim
  regression harness — an offline race reproducer with a firing negative control).

## 4. Net effect

**Menu-route death rate: 28 % → 4 % per launch.** The remaining 4 % is not attributed.

## 5. Rules this session added

1. **Never write to `.text`.** Express the effect as a **data** or **bytecode** write. Two working
   examples now exist: the `jz`→`[+0x354]` swap, and `catalog_pick_fix`'s permanent bytecode patch.
2. **Trim the injected set** to what the experiment needs — measured, not folklore (5 DLLs → 1 was
   17 % → 4 %).
3. **Verify injection positively.** The `-Hook` primary silently fails ~1 in 10. Require
   `inject-watch.out.log` to change *and* name the DLL, or require the shim's own marker stamp.
4. **A quiet control is VOID, not a pass** — cost a whole void A/B this session before the positive
   control was made to fire.
5. **Diff `.text` sha256, never file size.** Two variants shared file *and* `.text` size while
   differing in hash.
6. **Archive labels are not authoritative** — `archive-crashdumps.ps1` snapshots the whole crashpad DB
   *before* a launch under the *upcoming* run's label. The `RESULT` lines are the record.

## 6. Instrument errors caught (the project's dominant failure mode, 7 more instances)

- The clock itself: `SecondsSinceStart` is the *launch* clock and carries the operator's staging
  schedule (+33.0 s July→August), so every `T+<n>` rule silently drifts.
- `log_route` is a monotone function of survival time — "route X dies later" is partly definitional.
- Reading `MINIDUMP_THREAD.ThreadContext` instead of the exception stream's own → "every crash is at
  one identical address", 22/22, pure artifact.
- A substring match on `runtime` (matching `VCRUNTIME140.dll`) inverted a real 0/22 negative.
- `Saved\Logs` is a rotating ring — a stored "≈60 % retain a log" ratio gave 6/10, 7/10, 8/11 within
  hours.
- Counting archive `.dmp` files as deaths (47 files, 22 real reports).
- My own: an arithmetic slip on a fault address, published and corrected; a "1 shim" arm that was
  really 5; and an arm H that read 12/12 clean before its first death landed.

## 7. What is still open

- **The residual ~4 %** (1/24 with a single patch-free shim) is unexplained.
- **The three PI hookers are the last `.text` writers** — 33 % combined at a 320 s hold. Converting a
  PI hook to a non-`.text` mechanism is the only large lever left, and it is a design change.
- **FK-7 itself has not been re-tested.** Its evidence base is contaminated (finding 3) and the whole
  point of this session's work is that a tutorial sitting can now be run with instruments that
  distinguish our deaths from the game's. **That is the next session.**
