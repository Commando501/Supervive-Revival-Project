# S111 — the 60-launch A/B campaign. **The scan fix is CONFIRMED.**

**2026-08-05 23:31 → 2026-08-06 00:34. 60 launches, 30 per arm, one boot session, menu route.**
Condition held constant: `-NoMissions -InjectGapSeconds 3`, 60 s hold, alternating batches of 6 to
control for drift. Arms differ **only** in `tools\sigbypass-mod\catalog_store_fix.dll`; the
`scan=SAFECOPY-S111` marker stamp labels every run automatically, and the batch driver **aborts** if
the deployed DLL does not match the arm it was asked to run.

---

## 0. Result

| arm | runs | deaths | **scan faults (`0x205d`)** | protector | unclassifiable |
|---|---:|---:|---:|---:|---:|
| **B — pre-fix** (`.text 4c9f1604`) | 30 | 14 | **8** | 5 | 1 |
| **A — S111 fix** (`.text 202a6c7d`) | 30 | 11 | **0** | 11 | 0 |

**PRIMARY endpoint — scan fault: 8/30 vs 0/30, one-sided Fisher exact p = 0.0023.**

The endpoint, the test and the significance threshold were **all pre-registered** before any campaign
data existed (`docs/s111-scanfix-ab.md` §3), including the pre-computed finding that ~30 runs/arm
would be required. This is not a threshold chosen to fit the data.

**The fix removes the fault it was written to remove.**

## 1. ⚠ SECONDARY endpoint — a real caveat, not a footnote

| | arm A (fix) | arm B (pre-fix) | one-sided Fisher |
|---|---:|---:|---:|
| protector deaths (`runtime.dll+1`) | **11/30** | 5/30 | **p = 0.072** |

**Not significant at α=0.05, but it is the exact hypothesis flagged when the fix was written** —
`ReadProcessMemory` is a classic memory-scanning API and the fix introduces it into a manually-mapped
DLL inside an anti-tamper-protected process (`docs/s111-scanfix-run1.md` §5, written before any of
this data existed). It cannot be dismissed as post-hoc.

Read it carefully, in both directions:
- **Total deaths are LOWER with the fix (11 vs 14).** The fix is not net-harmful on the evidence.
- But the *composition* shifted: 8 scan + 5 protector → 0 scan + 11 protector. At p=0.072 with two
  endpoints examined, this is **suggestive and unresolved**, not established.
- ⚠ **Do not conclude the fix causes protector kills.** Family A predates the fix by 24 corpus
  instances across 42 days on both routes. An equally consistent reading: runs that would previously
  have died early *of the scan* now survive long enough to meet the protector, which is a competing-
  risks artifact, not a new hazard.

**The clean way to settle it** is a third arm with the scan **disabled entirely** (neither the old
unguarded walk nor the new `SafeCopy` one). If protector deaths stay at ~11/30 there, `ReadProcessMemory`
is exonerated. That arm does not exist yet.

## 2. Why this campaign worked when the first A/B did not

The first attempt was **void — the positive control never fired**. Three conditions were needed
before arm B would reproduce the crash at all:

| arm-B condition | launches | scan faults |
|---|---:|---:|
| default shim set, gap 20 | 3 | 0 |
| default shim set, gap 3 | 3 | 0 |
| **`-NoMissions` + gap 3** | 6 | 1 |
| **`-NoMissions` + gap 3 (campaign)** | 30 | **8 (27 %)** |

**`-NoMissions` is the generating condition**, which matches the corpus exactly: every family-B death
in it came from a non-default configuration, never the default full set. Without finding that, 60
clean arm-A runs would have proved nothing — a quiet control is VOID, not a pass.

## 3. Method notes — three instrument problems caught during the campaign

1. **The detection was undercounting deaths.** A death writes **either** a crashpad report **or** a
   `UECC-*` directory. The original runner only diffed crashpad UUIDs and reported "no new crashpad
   report" for a real death (`newNM5`). The campaign driver snapshots and diffs **both**. Four of the
   14 arm-B artifacts and one of the 11 arm-A artifacts came via the UECC path — they would have been
   silently lost.
2. **Archiving can race crashpad's writer.** `B4r5` was copied mid-write: a 6.4 MB truncated dump
   (normal ~40 MB) that no reader can parse, and the next launch cleared the complete original. That
   death is **permanently unclassifiable** and is counted as such — in **arm B**, i.e. counted
   *against* the hypothesis being argued for. The driver now waits 10 s after a death before archiving.
3. **A zero-byte minidump is not "no evidence".** Two deaths (`B2r6`, and one earlier) wrote a
   zero-byte `UEMinidump.dmp` but a fully parseable `CrashContext.runtime-xml`, classified via the
   corpus's dump-free discriminator (frame-0 module: `ntdll` = protector, `mdnsNSP` = scan). This
   reproduces the corpus's degenerate-class finding live.

⚠ `cm=NO` (CatalogManager never found) is **not** a scan-death discriminator, despite correlating
early on — `A4r6` and `A5r3` are `cm=NO` protector deaths. It only means the death preceded catalog load.

## 4. Scope of the claim

**Established:** under `-NoMissions -InjectGapSeconds 3`, menu route, this build, this boot, the
pre-fix DLL produces the `0x205d` scan fault in ~27 % of launches and the fixed DLL produces it in
**0 of 30**, p=0.0023.

**Not established:** behaviour on the tutorial route; behaviour across boots/build vintages; whether
the fix affects the protector family (§1); and whether the fixed build can fault in its scan at some
*other* offset — though `fk8_classify.py`'s `shape=scan-like` check (READ fault in an unregistered
region) was **0 across all 11 arm-A deaths**, every one of which was `runtime.dll+1`, EXECUTE.

## 5. State

Arm A (the fix) is deployed and verified (`.text 202a6c7d…`, stamp present). No game process is
running. The crash tree grew 93 → 98 during the campaign; every artifact is archived under
`dumps/crashpad-*s111ab-*`. Reproduce any classification with:

```
python tools/crashtri/fk8_classify.py dumps/crashpad-*s111ab-*
```
