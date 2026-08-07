# S111 — the PI-prologue bisect. A dose-response in `.text` writes, with one end unresolved.

**2026-08-06 23:22 → 2026-08-07 00:20. 12 launches × 320 s hold**, no-patch primary injected alone
via `-Hook`, then the three `ProcessInternal` hookers manually mapped with `inject.exe mmap`
(`mainmenu_refresh_pi8`, `loadout_fix`, `battlepass_adopt_fix`). Every secondary's
`manual-map complete` was verified individually — **12/12 reported `primary+3/3`**.
Total S111 series: **214 launches**.

---

## 0. The ladder, all at one hold and one boot

| arm | `.text` writes | runs | protector deaths | rate |
|---|---|---:|---:|---:|
| `-NoHook` | none | 11 | 0 | **0 %** |
| D — inert mapped DLL | none | 11 | 0 | **0 %** |
| **I — no-patch primary + 3 PI hookers** | **3 × transient prologue `jmp`** | **12** | **4** | **33 %** |
| E — patched primary alone | 1 × **standing** `jz`-NOP | 8 | 7 | **88 %** |

| comparison | p | verdict |
|---|---:|---|
| **arm I vs arm E** | **0.0249** | **significant — PI hooks are much less lethal than a standing patch** |
| arm I vs inert / `-NoHook` | 0.0559 | **not significant — just misses** |

## 1. What this establishes

**A dose-response in `.text` modification, which is the same story the whole S111 series has been
telling.** Zero writes → 0 %. Three *transient* prologue writes → 33 %. One *standing* write → 88 %.
The ordering is monotonic and the extreme comparison is significant.

**The PI hookers are significantly safer than the `jz`-NOP was** (p = 0.025). That vindicates the
transient-install design — install → piggyback one call → uninstall, serialised through the shared
`Local\SuperviveMissionsPIHook` mutex. It is doing real work: three transient writes cost less than
one permanent one.

## 2. ⚠ What this does NOT establish, and I am not going to round it up

**Arm I vs zero is p = 0.0559. That does not clear 0.05.** A 33 % point estimate against a 0/22
combined floor (inert + `-NoHook`) *looks* decisive and is almost certainly a real effect, but Fisher
at these N does not license the claim. The honest statement is:

> The PI prologue patches are **significantly less harmful than a standing `.text` patch**, and
> **probably harmful relative to no writes at all** — but the latter is unproven at N=12.

Four more arm-I runs at the same rate (≈5/16) would settle it. I stopped at 12 because the
decision-relevant comparison (are they as bad as the `jz`? — no) is already answered.

⚠ **Do not read 33 % vs the 60 s numbers.** This arm is a 320 s hold. The default-set campaign that
produced 5/30 (17 %) used 60 s. Arm I is **not** comparable to it, and the two must never be put in
the same column.

## 3. Practical consequence

The levers, in measured order of value:

1. **Ship the no-patch primary** — done. Largest single reduction (88 % → the arm-I/H band at 320 s;
   28 % → 17 % at 60 s).
2. **Trim the injected set.** Still the best remaining lever, and now with a mechanism: each shim's
   cost is roughly its `.text` write volume × standing time. `-NoLoadout -NoPasses -NoMissions` for
   sittings that do not need those surfaces.
3. **Shortening the PI standing window is worth less than expected.** The transient design is already
   capturing most of the benefit — arm I is 55 points below arm E. Optimising it further is a small
   return compared to (1) and (2).

## 4. Scope

- One boot, one machine, menu route, 320 s holds. Arm I n=12; arm E n=8. Wide error bars on both.
- Arms were **not** interleaved — arm E ran earlier in the session than arm I. Session drift is not
  excluded, and the two share no runs.
- `catalog_pick_fix` (a non-PI `.text` patch of `IsUseable`) was **not** tested. It is the fourth
  secondary and the remaining untested writer.
- Only the protector family is counted; scan faults were 0 throughout.
- ⚠ Archive labels remain non-authoritative — the archiver snapshots the whole crashpad DB
  pre-launch and tags it with the *upcoming* run's label. The `RESULT` lines are the record, and a
  classifier run over `dumps/crashpad-*s111pi-*` will over-count for exactly this reason.
