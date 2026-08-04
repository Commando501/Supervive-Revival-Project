# S108 — FK-7 verification attempt: the sitting is VOID, FK-7 stays OPEN

**Date:** 2026-08-04 (S108) · **Verdict: FK-7 remains OPEN. Not closed, not re-scoped downward.**
**Governing rule:** `docs/fk7-crash-settled.md` §0 — *a quiet run is VOID, not a pass.*

Every claim tagged **MEASURED** or **INFERRED**.

---

## 0. The one-line answer

The mandatory positive control was run and **it was quiet**. `docs/next-session-prompt-s108.md` §3 is
explicit about what that means:

> *"Runs 1–2 — `play-novtguard`, hold to T+220 s, as a **MANDATORY positive control**: prove this build
> vintage reproduces the crash *at all*. … **If the controls are quiet the sitting is void and Runs 3–4
> must not be read as a pass.**"*

The control was quiet. **Therefore Runs 3–4 were not run, and no `play` run this session may be read as
evidence that the fix works.** Closing FK-7 now would repeat its original sin exactly.

---

## 1. What was actually run

| run | DLL | reached armed state? | outcome |
|---|---|---|---|
| `wp2r1` | `play_wprobe2` | **no** — died in LoadMap | silent death, no dump (FK-26) |
| `wp2r2` | `play_wprobe2` | yes | died ~50–60 s after probe inject, **dump `FED1F952`** |
| `wpDRr1` | `play_wprobe` | **no** — died 5 s after `Browse` | silent death, no dump (FK-26) |
| `wpDRr2` | `play_wprobe` | yes | died ~80 s after probe inject, no dump |
| **`novtg1`** | **`play_novtguard`** | **yes** | ran to ~T+290 s, then died |
| `testact1` | `play_testactor` | **no** — `[SP] done` never appeared, staging aborted | Run 0's second arm is still **NOT DONE** |

> ⚠ **CORRECTED after the adversarial pass** (`docs/s108-skeptic-review.md`): the "no dump" column
> that stood here was **wrong**. Sentry's crashpad *does* write a minidump — one was caught live at
> 43,893,392 bytes and was uploaded-and-deleted within ~3 minutes — so "no `UECC-*` directory" is a
> property of my search, not of the run. `wp2r2` also **did** crash (dump `FED1F952`), so the tally is
> **4 of 4 force-opens crashed**, and the run-length discrimination in §2.1 is between *how long*
> they lasted, not between crashing and not crashing.

★ **`play_novtguard` is the FK-7 positive control and it did NOT reproduce the camera crash.**
MEASURED: zero `[VTG]` lines (expected — `KVTGUARD=0` compiles the guard out), no camera-family dump,
and the session ran past the historic **T+173…194 s** camera window unharmed.

---

## 2. Three measurements that matter beyond this sitting

### 2.1 ★ The deaths in the probe runs are the PROBE, not the build

MEASURED, and this is the cleanest discrimination available:

* both probe-carrying runs that reached the armed state died at **50–80 s**;
* the **probe-free** control (`novtguard`, no `KWPROBE` at all) ran to **~290 s** — 3.5–5× longer,
  through the entire camera window.

That is independent corroboration of `docs/s108-crash-triage.md`'s headline — the S107 crash was the
instrument killing its host — arrived at from live run lengths rather than from the dump. ⇒ **Probe
runs must not be used as FK-7 evidence at all**, in either direction. They have their own mortality.

### 2.2 ★ `FlushAsyncLoading=5` with `LogChaosCloth=0` — a combination the corpus did not contain

`docs/fk7-crash-settled.md` §0.3 rests on a clean pairing across 9 sessions:

> all 4 crash logs have `FlushAsyncLoading=5, LogChaosCloth=1`; all 5 dumpless logs have `=4, =0`.

MEASURED this session, `novtg1`: **`FlushAsyncLoading = 5` and `LogChaosCloth = 0`.**

The pairing is therefore **not a law**, and the inference chain that used flush-count as a proxy for
"the mesh build happened, so the FK-7 antecedent existed" is weakened: the 5th flush occurred and the
cloth warning did not. INFERRED consequence: `LogChaosCloth` is the better antecedent marker of the
two, and any argument that used `=5` to establish the antecedent should be re-checked.

Corroborating S106's own conclusion: cloth = **0** with `KTESTACTOR=0`, consistent with the test actor
having been the single degenerate body. This is *most* of Task 3's Run 0 — the missing half is the
`play_testactor` arm, which was not run (see §3).

### 2.3 The ~290 s death matches the integrity-kill latency, not FK-7

MEASURED: `novtg1` died at ~T+290 s from stage completion. `fk7-crash-settled.md` §0 row 10 records a
**~285 s observed kill latency** for the code-integrity check against RM_PLAY's long PI-patch hold.
INFERRED, but the arithmetic is close enough that **this death should not be counted as a crash
outcome** without opening it — and it left no dump to open (FK-26).

⇒ Any future FK-7 run held to **T+300 s** (as §3 of the S108 prompt specifies) is being held *past*
the integrity-kill horizon. **The hold target and the kill latency are in conflict**, and the prompt's
Runs 3–4 design should be revised to T+220–250 s before it is executed.

---

## 3. What was NOT done, and why — stated so it is not mistaken for a negative

* **Run 0's `play_testactor` arm** — not run. The `LogChaosCloth` 0-vs-1 A/B is therefore **half
  complete**: the `0` arm is MEASURED (§2.2), the `1` arm is not.
* **Runs 3–4 (`play`, hold to T+300 s)** — deliberately not run. The control was quiet, so by the
  governing rule they would have been unreadable. Running them would have manufactured a
  false pass.
* **A second `novtguard` control** — not run. n=1 against a MEASURED per-launch base rate of
  1-in-3-to-1-in-2 means a quiet control is **entirely expected** and proves nothing. Two more
  controls are needed before the vintage question can even be asked.

---

## 4. FK-7 closure status after S108

| | |
|---|---|
| **FK-7 the BELIEF** (*"flaky, ~2 of 3 die, budget retries"*) | CLOSED — CONFIRMED FALSE (unchanged) |
| **FK-7 the FIX** (does the tutorial route survive?) | **OPEN.** Still **zero** reproduce-then-repair runs. |
| Does the vtguard prevent Family B? | **UNKNOWN — not exercised.** Independently concluded by `docs/s108-crash-triage.md` from the dump, and by this sitting from the quiet control. |
| Blocker 1 — who writes the corrupt byte (FK-24) | **OPEN**, and its probe is now known to be self-lethal until S108's fixes are validated live. |
| **New blocker** | **FK-26** — the force-open dies silently ~2 of 3 attempts with no dump, so run budgets and the dump census both undercount. |

**The honest position: S108 moved FK-7 no closer to closure, and it removed one false step toward it**
(the probe runs, which could have been read as fix evidence and are in fact instrument mortality).

---

## 5. The corrected run plan for the next sitting

1. Rebuild every `wprobe*` artifact — the two 174,080-byte ones **can kill the process**
   (`docs/s108-fk24-instrument-corrected.md` §1, D-S108-3).
2. `forceTutorialMatch = true` + `configs\fk24-stage.ps1` gives a hands-free sitting; budget on
   **armed windows reached**, not launches — MEASURED yield ~1 in 3.
3. **Hold to T+220–250 s, not T+300 s** (§2.3).
4. Run the control **≥3 times** before reading any `play` run.
5. Complete Run 0's missing `play_testactor` arm (§3) — it costs one launch and needs no crash.
6. Gate every criterion on `[VTG] *** INVALID`, never on survival.
