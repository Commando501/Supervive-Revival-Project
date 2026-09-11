# S111 — the `catalog_store_fix` scan-fix run series (5 valid runs)

**2026-08-05, 20:44 → 21:11 local. Menu route** (`forceTutorialMatch = false`), full default shim
set, elevated launcher, Steam up, single boot session. Fixed build verified deployed and unchanged
across the whole series (`.text` sha256 `202a6c7d…`, re-checked mid-series).

## Result

| run | exposure | outcome | stamp | functional control |
|---|---:|---|---|---|
| run1 | 106 s | **DIED — family A (protector)** | YES | CatalogManager, Num=1004, jz=1/1, unhook=1 |
| runA | 121 s | survived hold, operator-stopped | YES | Num=1339, jz=1/1, unhook=1, lastPurch=1339 |
| runB | 121 s | survived hold, operator-stopped | YES | Num=1339, jz=1/1, unhook=1 |
| runC | 121 s | survived hold, operator-stopped | YES | Num=1004, jz=1/1, unhook=1 |
| runD | 121 s | survived hold, operator-stopped | YES | Num=1339, jz=1/1, unhook=1 |

**Total exposure 590 s. `0x205d` faults: 0. Scan-shaped faults (READ, unregistered region): 0.
Family-A deaths: 1.** UECC tree unchanged at 92 (this class writes crashpad reports, not `UECC-*`).

Every operator stop is timestamped in UTC in the run log — `docs/fk8-crash-timing-mined.md` §7.2
item 2 records that `Stop-Process -Force` is indistinguishable from a silent crash, so an
unlabelled kill would corrupt the corpus.

## ⚠ The honest reading: this series CANNOT establish that the fix works

The only place menu-route **exposure** is quantified is CLAUDE.md's `-InjectGapSeconds` sweep —
6,237 s for 5 deaths, and per the corpus those deaths are family B (our catalog scan). That is a
baseline of **~1 scan death per 1,247 s**.

| | exposure | expected scan deaths | **P(observe 0 \| the fix does NOTHING)** |
|---|---:|---:|---:|
| this series | 590 s | 0.47 | **0.62** |
| under CLAUDE.md's own residual (1/3054 s) | 590 s | 0.19 | **0.82** |

**Observing zero was the most likely outcome either way.** The series is consistent with the fix
working and equally consistent with it doing nothing. To reach P<0.05 under the sweep-derived rate
needs **~3,741 s** of menu exposure — ~31 runs at this hold, or far fewer with longer holds.

⚠ There is **no menu-route launch denominator** on disk. `docs/gft-ready-marker.txt` (81 append-mode
records) counts *tutorial staging* injections only — it advanced 80→81 across five menu launches
here, so it cannot serve. Open item #1 remains open.

⚠ A second, weaker point: the `0x205d` offset is specific to the **pre-fix** `.text`
(`4c9f1604`, 86,528 B). The fixed build is `202a6c7d` / 87,040 B, so a *post-fix* scan fault would
land at a different RVA. "No `0x205d`" is therefore necessary but not sufficient — which is why
`fk8_classify.py` also reports `shape=scan-like` (READ fault in a region belonging to no
registered module). **That was also 0/2.**

## What the series DOES establish

1. **The fix does not break the shim.** Five for five: the rewritten `ReadProcessMemory` scan found
   the live CatalogManager, the `jz` was patched *and* self-restored, slot 110 was unhooked, and the
   poke loop reached all 1,339 CatalogEntries. That was the real risk of the change — a scan that
   reads nothing never faults and would have looked like a pass.
2. **The build under test was live in every run**, via the new `scan=SAFECOPY-S111` marker stamp.
3. **Family A is now the binding constraint.** It killed run 1 at ~106 s and one void-period run;
   this fix does not address it and never claimed to.

## Deaths captured (2 distinct, both family A)

```
crashpad-20260805-204616-s111-scanfix-run1      A-protector  RIP=0x7FFD3B400001 EXECUTE low16=0x0001
crashpad-20260805-205659-s111-VOID-concurrent   A-protector  RIP=0x7FFD3B400001 EXECUTE low16=0x0001
```
Identical addresses are **correct, not an artifact**: the EXE base is per-boot, not per-process, so
runs in one boot share `<protector base>+1`. Family A total: 24 → **26**.

⚠ **Archive copies are not deaths.** Three `.dmp` files existed across the `s111-*` archives but only
**two** distinct report uuids — the archiver snapshots the crashpad DB both before a launch and after
exit. I counted 3 before catching it; `fk8_classify.py` now dedupes by uuid and says so out loud.

## ⚠ VOID runs — excluded, and why

The first driver (`run_launches.ps1`) reported two "clean" runs that were **void**: its hold loop
never executed, and it launched a second game while the first was still alive, so two shim instances
`CREATE_ALWAYS`-ed the same marker file (which is why one reported `cm=NO`). They are excluded from
every number above; only the death they produced is retained and classified. A driver that reports
success without having run the experiment is the same failure class as a quiet positive control.

## Next, in order of value

1. **Exposure, not run count.** ~3,700 s of menu uptime would actually settle it. Family A and the
   ~240–295 s kill mode cap a single run at roughly 250 s, so this means ~15–20 longer runs.
2. **An A/B against the pre-fix DLL** (still on disk: `.text 4c9f1604`) under identical conditions
   would be far more informative per unit time than more one-armed runs, at the cost of deliberately
   re-introducing a known process-killer. Worth doing if the exposure campaign is run at all.
3. **Open item #5 — a `-NoHook` run held past 300 s.** Family A is now the dominant unaddressed
   self-inflicted class and **the corpus still contains no such control**, so it is not established
   that it is our injection at all.
