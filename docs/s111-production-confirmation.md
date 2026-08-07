# S111 — production confirmation. ⚠ **NEGATIVE: dropping the primary's patch did NOT fix production.**

**2026-08-06 22:09 → 22:43. 30 launches**, full default set (5 DLLs), no-patch primary,
`-NoMissions -InjectGapSeconds 3`, 60 s hold — the **exact condition** the 25/90 baseline was
measured under. Total across the S111 series: **178 launches**.

---

## 0. Result

| | runs | protector deaths | scan faults |
|---|---:|---:|---:|
| baseline (patched primary, same condition) | 90 | **25 (28 %)** | 8 |
| **this run (no-patch primary)** | **30** | **5 (17 %)** | **0** |

**One-sided Fisher: p = 0.165. NOT significant.**

Treatment verified **30/30** — every run's marker read `stamp=FIX/jz=0`, so the primary genuinely
carried no `.text` patch in any of them. All 5 deaths classified **protector** (`runtime.dll+1`,
EXECUTE); **zero** scan faults, consistent with the S111 scan fix holding.

## 1. What this means

**The prediction was wrong, and it was flagged as unproven before the run.**
`docs/s111-jz-dropped-shipping.md` §3 said explicitly: *"'this takes production to ~0 %' is INFERRED
from the bisect, not measured end-to-end"* and named the reason it might fail — *"the other four
shims still write… also `.text` writes, never bisected individually."* That is exactly what happened.

The mechanism story is **not** overturned. The bisect stands (patch standing 11/12 vs no patch 0/5,
p = 0.00097). What is now clear is that the primary's `jz`-NOP was **one `.text` writer among
several**, and removing it alone does not clear the process:

- `mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix` each install a `ProcessInternal` **prologue
  patch** — a 5-byte `jmp` written into `.text` — transiently, serialised through the shared mutex.
- `catalog_pick_fix` patches `IsUseable`.
- Those are still present in every run of this campaign.

17 % vs 28 % is a numerical improvement of the right sign and rough size for removing one of several
writers, but at this N it is indistinguishable from noise. **Do not claim a production improvement.**

## 2. Was dropping the patch still worth it?

Yes, on two independent grounds that do not depend on this null result:

1. **It removes a genuine, measured hazard** — the bisect is unambiguous that a standing `.text`
   patch kills, and the primary's was standing ~5–45 s of every launch.
2. **It costs nothing.** The roster still renders (screenshot-verified), the catalog is still found
   (`cm=YES` in **24/30** runs here), and the shim is otherwise unchanged.

⚠ **One functional datum worth noting:** `P5r4` survived the full 60 s with `cm=NO` — the catalog was
never found inside the hold. The other 5 `cm=NO` runs are the deaths (they died before catalog load).
So 1/30 runs had a slow catalog. At a 60 s hold that is a measurement artifact rather than a user
problem, but if the poke ever has to land before first HUNTERS navigation (§1 of the shipping doc),
a slow catalog is precisely the failure path. Worth watching.

## 3. Next — and the target is now specific

The remaining `.text` writers are the PI-hooking secondaries. The one-variable ladder is the same
shape that worked before:

| arm | inject | isolates |
|---|---|---|
| **H** | `-Hook catalog_store_fix.dll` (no-patch primary, **alone**, no secondaries) | whether the primary is now clean |
| I | primary + `mainmenu_refresh_pi8` only | the first PI hooker |
| J | primary + each remaining secondary | the rest |

**Arm H is the decisive one and is nearly free** — arm G already ran it once at 320 s and survived.
~10 runs at 60 s against this campaign's 5/30 would say whether the residual 17 % lives in the
primary or in the secondaries. If arm H is ~0/10, the secondaries own the whole remaining rate and
the fix is to give their PI prologue patches the same treatment: shorten the standing window, or
replace the hook with something that is not a `.text` write.

## 4. State

No game running. `catalog_store_fix.dll` deployed = the no-patch build (`jz NOP'd` string absent).
Crash tree 98 → 103. All artifacts under `dumps/crashpad-*s111ab-P*`.

⚠ **Archive labels are not authoritative.** `crashpad-…-s111ab-P5r1` contains a *pre-launch snapshot
of an earlier death*, not a P5r1 death — P5r1 reported `artifact=NONE`. The `RESULT` lines are the
record; the archiver snapshots the whole crashpad DB before each launch and labels it with the
upcoming run's tag.
