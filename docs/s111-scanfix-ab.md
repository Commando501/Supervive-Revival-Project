# S111 — A/B of the `catalog_store_fix` scan fix against the pre-fix DLL

**2026-08-05, 22:42 → 23:26 local. 23 launches, one boot session, menu route.**
Arms differ **only** in `tools\sigbypass-mod\catalog_store_fix.dll`:

| arm | `.text` sha256 | marker stamp | |
|---|---|---|---|
| **A** | `202a6c7d…` (87,040 B) | `scan=SAFECOPY-S111` **present** | the S111 fix |
| **B** | `4c9f1604…` (86,528 B) | **absent** | the pre-fix build |

The stamp makes arm membership self-evident in every run's marker — no bookkeeping to get wrong.

---

## 0. Headline

**The positive control FIRED, and it fired only in arm B.** The `0x205d` scan fault reproduced with
the pre-fix DLL and never appeared with the fixed one. But the live comparison is **not
statistically significant and cannot be made so at a reasonable cost** — the per-launch scan rate is
~1-in-6, so p<0.05 needs ~30 launches *per arm*. The decisive evidence for the fix remains the
source-level defect plus the offline control; this A/B corroborates it in situ and **identifies the
generating condition**, which is new.

---

## 1. ★ The generating condition — the actual discovery here

The crash does **not** reproduce under the default configuration. It took three attempts to make the
positive control fire, and the failures are as informative as the success:

| arm-B condition | launches | exposure | deaths | scan faults |
|---|---:|---:|---:|---:|
| default set, gap 20 | 3 | 363 s | 0 | 0 |
| default set, **gap 3** (the "lethal" regime) | 3 | 453 s | 0 | 0 |
| **`-NoMissions` + gap 3** | 6 | ~800 s | 2 | **1** |

**`-NoMissions` is the condition.** This matches the corpus: every family-B death in it came from a
**non-default** configuration (`sub-NoMissions-1/2/3`, `sub-NoPasses-2`, `shimrun3`, `knee-g30-2/3`)
— never from the default full set. Nobody had reproduced that deliberately before.

⚠ **This reframes a CLAUDE.md claim.** CLAUDE.md records `-NoMissions` as ~21× more hazardous than
`-NoPasses` and attributes the hazard to how many PI-hookers are resident. The one scan fault
observed here landed in `-NoMissions`, which offers a **different candidate mechanism** — that a
share of the "`-NoMissions` hazard" is *our own catalog scan faulting*, not the PI hookers.
**MEASURED at n=1; do not treat as established.**

## 2. ⚠ CLAUDE.md's gap-3 hazard figure does NOT reproduce

CLAUDE.md's sweep gives the 3 s row as 129 s exposure / 12 injections / **3 deaths** ⇒ ~1 death per
**43 s**. Reproduction attempt, **treatment verified per run** in `docs/inject-secondaries.log`
(injections at 22:55:42/45/48/51/54 — exact 3 s spacing, whole burst in 13 s):

> **3 launches × 151 s = 453 s exposure, 15 injections, 0 deaths.**
> Expected under the stated rate: **10.5**. **P(observe 0) = 2.7 × 10⁻⁵.**

`docs/fk8-crash-timing-mined.md` already flagged that table **UNDER RE-EXAMINATION** because its
outcome variable was never split by fault family. This is a second, independent problem with it: the
headline rate itself does not reproduce.

⚠ **SCOPE:** 3 launches, one boot, one machine, current shim builds. This does not prove the original
measurement was wrong — build vintages and memory state differ. It does mean the 3 s regime is **not
a usable positive control today**, and that the table should not be cited as a rate.

## 3. The matched comparison

Both arms: `-NoMissions`, `-InjectGapSeconds 3`, 150 s hold, same boot, alternating batches.

| | launches | deaths | **scan faults (`0x205d`)** | other |
|---|---:|---:|---:|---|
| **arm B — pre-fix** | 6 | 2 | **1** | 1 protector |
| **arm A — S111 fix** | 6 | 2 | **0** | 2 protector |

One-sided Fisher on the scan endpoint: **p = 0.500**. Across *all* 23 launches
(arm A 11, arm B 12): **p = 0.522**.

⚠ **The thresholds were pre-registered before the data landed**, and it was computed in advance that
*no* outcome of the final batch could reach p<0.05. Runs per arm needed, holding arm A at 0 and arm B
at ~1/6: **12→p=0.24, 18→p=0.11, 24→p=0.055, 30→p=0.026.** So ~30/arm ≈ 60 launches ≈ 2.5 h.

**The death *rate* is the same in both arms (2/6). The death *cause* is not.** That is the whole
result: the scan signature appears only where the defective scan is present.

### The one scan fault, and how far its attribution goes

`oldNM3`, died 20 s in — squarely in the corpus's 15–45 s band.
`RIP = 0x22A4945205D` · `RIP & 0xFFFF = 0x205D` · `RIP − 0x205d` 64 KB-aligned · **READ** fault ·
in no registered module. Four-way match to the family-B signature.

⚠ **Not a byte-level match.** The original corpus forensics matched a 40-byte code window; that could
not be repeated here because **crashpad dumps do not capture that memory region** (the original was a
UECC dump). The attribution rests on the four-way signature, which is strong but weaker than the
corpus's.

## 4. ★ Incidental: family A is *directly* confirmed as `runtime.dll + 1`

`newNM5` died at 10 s and produced **no crashpad report** — it wrote a `UECC-*` directory instead
(the first UECC crash of this session; tree 92→93). Its dump **lists `runtime.dll`**, and `RIP − 1`
resolves to **exactly its base**:

```
ErrorMessage    EXCEPTION_ACCESS_VIOLATION 0x00007ffd3b400001
PCallStack      ntdll 0x00007ffd3b150000 + 2b0001   KERNEL32 0x…+17374 (BaseThreadInitThunk)
PCallStackHash  DA39A3EE…  (SHA-1 of the empty string — the os-only-unwind class)
```

Until now family A was `<protector base>+1` **by inference from address shape**, because
`runtime.dll` is absent from crashpad module lists (0/24). A UECC dump of the same fault **names the
module**. That also confirms the write-up's frame-0 discriminator (`ntdll` = poison-shaped;
`mdnsNSP` = scan-shaped).

⚠ **This exposed a bug in my own classifier**, now fixed: `fk8_classify.py` required family A to be
in *no* module, which was generalising a crashpad-class blind spot into the rule, and so misfiled the
better-evidenced UECC dump as `in-module:runtime.dll`. Same error shape the project keeps hitting.

## 5. What this establishes, and what it does not

**Does:**
- The `0x205d` scan fault is **reproducible on demand**, and the condition is now known (`-NoMissions`).
- It appeared **only** in the pre-fix arm across 23 launches.
- The fixed build shows **0 scan faults in 11 launches** across all configurations.
- Arm A remains functionally correct throughout (CatalogManager found, `jz=1/1`, unhook=1).

**Does not:**
- **Statistical significance.** p=0.50 matched, p=0.52 overall. One scan fault is one event.
- Rule out that the fixed build faults at a *different* offset: `0x205d` belongs to the pre-fix
  `.text`. The classifier's `shape=scan-like` check (READ fault, unregistered region) covers this and
  was **0 across every arm-A death** — all of which were `runtime.dll+1`, EXECUTE.

## 6. Deployment state

**Arm A (the fix) is deployed** — `tools\sigbypass-mod\catalog_store_fix.dll`, `.text 202a6c7d…`,
stamp present. The pre-fix DLL is **not** left on disk anywhere the launcher would load it.

## 7. Next

1. **~30 launches/arm** if a significant live result is wanted (~2.5 h, automatable — the runner and
   classifier both exist now).
2. **Re-fit the `-InjectGapSeconds` table by fault family.** Two independent problems now: the
   outcome variable was never split, and the 3 s rate does not reproduce.
3. **Test whether `-NoMissions` raises the scan hazard specifically** — it is the one condition that
   reproduces the fault, and CLAUDE.md currently explains that config's hazard a different way.
