# S111 — the `-NoHook` control. ★ **The protector kill is OURS. It is caused by injection.**

**2026-08-06 14:37 → 15:40. 11 launches × 320 s hold, zero shims injected.**
Closes ignorance-map **open item #5**, which the corpus could never answer because *it contained no
such run*. Total across the S111 experimental series: **101 launches**.

---

## 0. Result

| | runs | hold | deaths | **protector deaths** |
|---|---:|---:|---:|---:|
| injected arms, pooled (A+B+C) | 90 | 60 s | 34 | **25 (28 %)** |
| arm C alone (1 shim, scan disabled) | 30 | 60 s | 9 | **9 (30 %)** |
| **`-NoHook` (no shims at all)** | **11** | **320 s** | **0** | **0 (0 %)** |

- vs arm C: **p = 0.0408**
- vs all injected arms pooled: **p = 0.0360**

**With no injection, the protector never fired — across 3,520 s (58.7 min) of uptime.** With
injection it kills ~28 % of launches *within the first 60 s*. The `-NoHook` runs each survived
**5.3× longer** than the window in which the injected arms were dying.

**Treatment verified 11/11**: `-NoHook` writes no shim marker, so the check used was the marker
file's `LastWriteTime` being **unchanged** across every run. Any movement would have meant a shim ran
and voided that run. None moved.

## 1. Why this isolates injection specifically, and not "doing less work"

The obvious objection is that a `-NoHook` client simply exercises less code — the roster and store
never populate, so maybe it just does less and dies less.

**Arm C rules that out.** Arm C ran the `KNOSCAN` control build, which *also* never finds the
CatalogManager and *also* leaves the roster and store unpopulated. Functionally the client is in the
same impoverished state as `-NoHook`. The **only** difference is that arm C had one DLL
manually mapped into it.

> arm C (unpopulated + 1 injected DLL) → **30 %** protector deaths
> `-NoHook` (unpopulated + 0 injected DLLs) → **0 %**

The discriminating variable is **the injection itself**, not the workload.

## 2. What this changes

1. **The corpus's largest self-inflicted class is now attributed.** Family A (`runtime.dll + 1`,
   EXECUTE, no registered module) was 24+ instances across the whole corpus and had **no known
   trigger** — `docs/fk8-crash-timing-mined.md` §3.1 could only describe its signature. It is
   triggered by our injection.
2. **The ~30 % per-launch death rate in ordinary sessions is ours, not the game's.** That reframes it
   from an environmental hazard to be budgeted around into **a tractable engineering problem**.
3. **The `-InjectGapSeconds` table's premise is vindicated even though its numbers are not.** That
   table (already flagged UNDER RE-EXAMINATION twice: its outcome was never split by fault family,
   and its 3 s rate failed to reproduce — `docs/s111-scanfix-ab.md` §2) was *right* that injection
   drives deaths. It just measured the wrong quantity.
4. **The "~285 s code-integrity kill" did not fire once in 11 runs that all crossed it.** Consistent
   with CLAUDE.md's rule that the check catches a **standing `.text` patch** — `-NoHook` leaves none.
   This is the first direct evidence for that mechanism rather than an inference from timing.

## 3. Scope — state it, do not over-read

- **N = 11, one boot, one machine, menu route, `-NoHook` vs `-NoMissions -InjectGapSeconds 3`.**
  p ≈ 0.04 is significant but not overwhelming; a single protector death in the next few `-NoHook`
  runs would weaken it substantially.
- **It does NOT identify WHICH aspect of injection provokes the protector.** Three candidates remain
  live and untested against each other: the manual-mapped image itself, the self-restoring `.text`
  `jz`-NOP, and the `ProcessInternal` prologue writes. Arm C still patched the `jz` and still
  mapped a DLL, so this experiment cannot separate them.
- **It does not follow that shims must be abandoned** — the front-end menu depends on them. It
  follows that the injection *mechanism* is now the highest-value thing to make cheaper.

## 4. The next experiment, and it is cheap

A **one-variable ladder** over the three candidates, ~10 runs each at the same condition:

| arm | manual-map | `.text` patch | PI hook | isolates |
|---|:--:|:--:|:--:|---|
| D | ✓ | ✗ | ✗ | mapping alone |
| E | ✓ | ✓ | ✗ | + the `jz`-NOP |
| F | ✓ | ✓ | ✓ | + PI prologue writes |

Arm D is a **do-nothing DLL** (`DllMain` returns immediately). If arm D already dies at ~30 %, the
protector is reacting to manual mapping itself and no amount of shim-logic tuning will help — the
fix would have to be a different loading strategy. That is the single most informative run left.

## 5. State

No game running. `catalog_store_fix.dll` = the S111 fix (`SAFECOPY-S111` stamp present); no control
build left deployed; no pending crash reports. Reproduce with:

```
scratchpad\nohook.ps1 -Tag NH -N 1 -HoldSeconds 320     # per run; treatment = marker mtime unchanged
```
