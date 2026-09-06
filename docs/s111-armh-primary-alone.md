# S111 — arm H. The residual is **cumulative**, not owned by any one shim.

**2026-08-06 22:46 → 23:15. 24 launches**, no-patch primary injected **alone** via `-Hook` (no
secondaries), 60 s hold — matched to the default-set campaign. Total S111 series: **202 launches**.

---

## 0. The ladder, at one hold and one boot

| arm | injected | runs | protector deaths | rate |
|---|---|---:|---:|---:|
| baseline | 5 DLLs, **patched** primary | 90 | 25 | **28 %** |
| default set | 5 DLLs, **no-patch** primary | 30 | 5 | **17 %** |
| **arm H** | **no-patch primary ALONE** | **24** | **1** | **4 %** |

| comparison | p (one-sided Fisher) | |
|---|---:|---|
| arm H vs baseline | **0.0090** | **significant** |
| arm H vs default set | 0.155 | not significant |
| default set vs baseline | 0.165 | not significant |

## 1. What this actually shows

**Neither single step is significant on its own, but the endpoints are.** Removing the `.text` patch
(28 % → 17 %) and removing the four secondaries (17 % → 4 %) are each individually
indistinguishable from noise at these N, yet together they take the rate from 28 % to 4 % with
p = 0.009.

That is the signature of an **additive / cumulative** hazard rather than one guilty component:

- The primary's `jz`-NOP was **one** `.text` writer. Removing it helped, by roughly the amount one of
  several writers would.
- The four secondaries — `mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix` (5-byte
  `ProcessInternal` prologue `jmp`s) and `catalog_pick_fix` (`IsUseable` patch) — are the rest, and
  they contribute roughly as much again.
- ⚠ **Arm H is NOT zero: 1/24.** So even a single, patch-free shim occasionally provokes the
  protector. Something in the primary's *remaining* activity (VEH, exec stub, slot-110 vtable hook,
  or the scan) still carries a small residual, or there is a floor unrelated to `.text` writes.

**This corrects the framing I used going in.** I proposed arm H as a test of "do the secondaries own
the residual", with the expectation of ~0/10. The answer is *mostly, but not entirely* — and the
"0/10" version of the hypothesis is falsified by the 1/24.

⚠ **Caution against over-reading 4 %.** Arm H at 12/12 clean looked like a flat zero; the 13th–18th
runs produced the death. Stopping early would have published "0 %". The rate is small, not absent.

## 2. Practical consequence

There is no single fix. The rate scales with **how much `.text` we write and how long it stands**, so
the levers are cumulative too:

1. **Ship the no-patch primary** — done, and it is the largest single reduction measured (28 → 17 %).
2. **Trim the injected set to what a given experiment needs.** Arm H shows the marginal cost of the
   four secondaries is roughly the same again (17 → 4 %). For tutorial sittings that do not need the
   store/passes/customization surfaces, `-NoLoadout -NoPasses -NoMissions` is now a *measured*
   stability lever, not a guess.
3. **Give the PI prologue patches the same treatment the `jz` got** — they are transient already, but
   their standing window has never been measured. That is the next `-D` bisect, and it is the same
   shape as `KNOVEH`/`KNOSLOT`/`KNOJZ`.

## 3. Scope

- One boot, one machine, menu route, 60 s holds. Arm H is 24 runs; the 4 % point estimate has wide
  error bars (0/24 would have been 0 %, 2/24 would be 8 %).
- The three arms were **not** interleaved — baseline and default-set ran earlier in the session than
  arm H. Drift across the session is not excluded.
- Only the protector family is counted. Scan faults were **0** in every no-patch arm, so the S111
  scan fix continues to hold across 54 further launches.
- ⚠ Archive labels remain non-authoritative (the archiver snapshots the whole crashpad DB pre-launch
  and tags it with the *upcoming* run). The `RESULT` lines are the record.
