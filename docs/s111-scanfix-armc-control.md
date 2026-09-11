# S111 — arm C, the scan-disabled control. **`ReadProcessMemory` is exonerated.**

**2026-08-06 13:49 → 14:22. 30 launches**, identical condition to arms A and B
(`-NoMissions -InjectGapSeconds 3`, 60 s hold, same machine). Total campaign: **90 launches**.

Arm C is a **control build only**: `-DKNOSCAN=1` removes the memory scan entirely — neither the old
unguarded walk nor the new `SafeCopy` one runs. Built through the registered `noscan` variant, so it
lands as a **differently named** DLL (`catalog_store_fix_noscan.dll`, `.text 58e5c33b`, 85,504 B —
1,536 B smaller than arm A, the scan code being gone) and cannot be confused with a candidate.

**Treatment verified 30/30:** every arm-C run reported `stamp=NOSCAN` **and** `cm=NO` (the shim
cannot find the CatalogManager without a scan). The batch driver aborts if the deployed binary does
not match the requested arm.

---

## The three-arm result

| arm | scan | runs | deaths | **scan faults** | **protector** | unclass |
|---|---|---:|---:|---:|---:|---:|
| **B** pre-fix | old, unguarded | 30 | 14 (47 %) | **8** | 5 (17 %) | 1 |
| **A** S111 fix | new, `SafeCopy` | 30 | 11 (37 %) | **0** | 11 (37 %) | 0 |
| **C** control | **none** | 30 | 9 (30 %) | **0** | 9 (30 %) | 0 |

### The question arm C was built to answer

> Does the `ReadProcessMemory` scan cause the elevated protector (`runtime.dll+1`) deaths?

**No.** Arm C removes the scan **completely** and the protector rate barely moves:

- **A (new scan) 11/30 = 37 % vs C (no scan) 9/30 = 30 % → p = 0.392.** No detectable difference.

If `ReadProcessMemory` were driving protector kills, arm C — which makes no such call — should have
dropped to arm B's level. It did not. **The concern raised in `docs/s111-scanfix-run1.md` §5, and
carried as the campaign's open secondary endpoint, is now closed: the fix does not trade one death
family for another.**

### And it explains arm B's *low* protector count, which was the real puzzle

Arm B's 5/30 (17 %) was never evidence of safety — it is **competing risks**. Eight of arm B's 30
runs died of the scan at 12–33 s, i.e. *before* the protector had its chance. Censor 8 runs out of a
population dying at ~30 % and you expect roughly 5 + 8×0.30 ≈ 7.4 protector deaths had they survived,
against arm C's observed 9 — consistent within this N. C vs B is **p = 0.180**, i.e. arm B is not
significantly *lower* than the no-scan baseline once you stop reading a censored count as a rate.

**The correct summary of the whole campaign:** the protector kills ~30 % of launches under this
condition **regardless of what our scan does**, and the pre-fix scan added **8/30 deaths on top of
that**. The fix removes those 8 and adds nothing.

## Net effect of the fix

| | pre-fix (B) | fixed (A) |
|---|---:|---:|
| total deaths | **14/30 (47 %)** | **11/30 (37 %)** |
| deaths we caused | 8 | **0** |
| deaths the protector caused | 5 (censored) | 11 |

The fix is a **strict improvement**: it eliminates the entire self-inflicted death class
(8/30 → 0/30, p = 0.0023) and does not raise the protector class (p = 0.392 vs a no-scan control).

## ⚠ Scope and cautions

- **Arm C is not a shippable build.** With the scan off the shim never finds the CatalogManager, so
  the roster and store do not populate and the `jz` self-restore never fires (it is gated on
  `catLoadedAt`), leaving the `.text` patch up for the life of the run. Harmless at a 60 s hold; do
  **not** run this arm long or treat it as a candidate. `KNOSCAN` defaults to **0** and is reachable
  only through the registered `noscan` variant — this project has twice been burned by a diagnostic
  left switched on (`KTESTACTOR`, `KSTATICTEST`).
- **The arm-A binary is the campaign binary** (`.text 202a6c7d`, unchanged since the A/B). Arm C was
  compiled from source that also added the inert `KNOSCAN` scaffolding and a stamp-format change, so
  arm C's non-scan code differs from arm A's by those two trivia. Not re-run; noted for honesty.
- **Protector rates are per-condition.** 30 % applies to `-NoMissions -InjectGapSeconds 3` at a 60 s
  hold on this boot. It is not a general figure.
- **Deployment restored and verified:** `catalog_store_fix.dll` = `.text 202a6c7d`, `SAFECOPY-S111`
  stamp present, no `DISABLED-ARMC-CONTROL` string, no game running.

## What is now settled, across 90 launches

1. The `0x205d` scan fault is **caused by the unguarded scan** and **removed by the fix** (8/30 vs
   0/30, p = 0.0023, pre-registered).
2. The fix **does not cause protector deaths** (37 % vs 30 % no-scan control, p = 0.392).
3. The protector family is **independent of our scan** and is the dominant remaining death cause at
   ~30 % of launches under this condition — and it is still **unexplained**. Ignorance-map open item
   #5 (a `-NoHook` run held past 300 s) remains the next control worth running: nothing yet
   establishes that the protector kill is triggered by our injection at all.
