# S112 — completion review: FK-7 and FK-8

**2026-08-08.** A skeptical audit of what is actually closed, written against the evidence rather
than against the summaries. New measurements taken during the review are marked ★ NEW.

---

# FK-7 — the tutorial run dies within ~1–5 minutes

## Verdict: ~~**SUBSTANTIALLY ANSWERED. NOT CLOSED.**~~ → **CLOSED 2026-08-08**

> **UPDATED.** This review's verdict was "not closed" because the fix was measured but **not shipped**
> and the residual was untested. Both were then addressed: the fix is now the DEFAULT and is deployed
> (`.text 5151621d2154e454`), confirmed on the documented recipe path with no functional regression;
> and the residual was re-tested at a matched 600 s hold. Final corpus: **10/10 died with a standing
> `.text` patch vs 3/36 without, p = 0.00000007.** The open items below were split out as **FK-31 /
> FK-32** (`docs/fk31-fk32-successors.md`). The findings in this file otherwise stand.

### What is closed (MEASURED, and it survives scrutiny)

**1. The dominant cause is our own standing `.text` patch.** Pre-registered one-variable A/B,
N = 10 armed windows per arm: control (RM_PLAY's 600 s standing `.text` patch) **10/10 died**;
treatment (identical shim, hook expressed as a heap `UFunction.Func` swap, zero module-image writes)
**2/10 died**. **Fisher's exact two-sided p = 0.00071**; sensitivity 11/11 vs 2/10, p = 0.00022.

**2. ★ NEW — the "survived by doing less" confound is FALSIFIED.** This was the strongest available
objection: a non-`.text` callback mechanism could get fewer dispatches, RM_PLAY could quietly do
less, and the arm would survive for the wrong reason. It does not hold.

| arm | run | `[PL]` init lines | `[DIAG]`/s | `[FOW]`/s |
|---|---|---:|---:|---:|
| control | ctl-19 (died 64 s) | 25 | 0.09 | 0.25 |
| control | ctl-23 (died 80 s) | 25 | 0.20 | 0.26 |
| treatment | trt-16/20/22/38 (survived 331 s) | 26 | **0.55** | **0.32** |

Identical init sequence, and the treatment logs **more** shim work per second. Functionally: in
treatment survivor `trt-22` the hero walked `(-65,-1770,393) → (2841,-1770,441)` with the run
AnimSequence resolved and self-driven walk active; control `ctl-23` died **partway along the same
path** at `x≈1379`. Same work, same trajectory, different survival.

**3. No game-attributable death exists.** 28/28 dumps this session are `OURS/protector`
(`RIP == runtime.dll base + 1`, EXECUTE, `ExceptionInformation[0] == 8`). Across 41 launches, **zero**
dumps with a SUPERVIVE frame at the fault and no self-inflicted signature.

### What is NOT closed

**1. ~~The 2/10 residual~~ → RE-TESTED, now FK-32.** *(Phase 3 flew the `-DKFSNAME` arm this item
asked for: `swapped=2` instead of 17,126, matched 600 s hold, **0/8 vs 0/8**. That cannot discriminate
footprint — but it bounds the residual to **3/36** and both original deaths came from the SHORTER
hold. Tracked as FK-32.)* Original text: **the leading suspect is our own instrument.** Neither residual
death is a protector kill; neither left an artifact. The treatment swaps **17,126** `UFunction.Func`
pointers onto the hot path of all Blueprint execution — a large novel surface, and it must be named
as a live alternative explanation for its own residual. Untested: `-DKFSNAME=<name>` swaps one
function instead of thousands. **Until that runs, "20 %" is the treatment's rate, not the game's.**

**2. The staging hazard — OPEN, now tracked as FK-31.** *(⚠ this item proposed `-DKNOLOGINVT=1` as
"the clean test"; it was built and flown and is **FALSIFIED** — 4/4 died, 0/4 map loads, fatal
`ALokiGameMode::Login failed to Login`, p = 0.0026. The patch is still load-bearing. See
`docs/fk31-fk32-successors.md`.)* Original text: **it is large.** **8 of 20** launches that never armed died during
staging with only `gft_ready_fix` + `tutorial_launch_fo` resident, before the probe existed.
`gft_ready_fix` writes no module image, so the writer is `fo`: a transient ≤8 s `.text` prologue
**confounded in every run** with a ≤25.5 s `.rdata` slot-285 vtable patch. `s112-trt-02` died with
that `.rdata` patch demonstrably still standing (no `[5] done (vtable restored)`). The clean test is
`-DKNOLOGINVT=1`, which **does not exist** and risks a `Login` fatal.
⇒ **"FK-7 is our PI hook" remains too narrow.**

**3. ~~The treatment arm is only proven to 331 s.~~ → RESOLVED.** *(Phase 3 ran both non-`.text` arms
at a matched **600 s** hold: 16/16 survived, and the shipped default then survived 5/6 more at 600 s.
The historical 87–524 s spread is now covered.)* Original text: Pre-registered Phase 2 (600 s extended treatment
holds) was **not run**. This does **not** weaken the primary comparison — control saturates at 100 %
by 137 s, so the contrast is fully resolved inside the hold — but the treatment's own long-run
hazard is unmeasured, and the historical FK-7 spread ran to 524 s.

**4. Still no shim-free tutorial run has ever been made.** True before this session, true after.
The treatment arm still injects four DLLs.

**5. ★ NEW — the camera family did not occur at all, and that is NOT evidence it is fixed.**
0 camera-family dumps in 41 launches. Tempting to read as confirmation of the S106 `KXFORMFIX`
spawn-`FTransform` repair — **do not.** The effective denominator is the 21 armed windows (a camera
actor cannot corrupt before it is spawned), and at the historical ~8 %/staged-launch rate the
expected count is ~1.7, so **P(0) ≈ 0.17**. Unremarkable. The fix remains unvalidated by a live
reproduce-then-repair, exactly as before.

**6. FK-24 — untouched.** The writer of the `0x01` byte at `PlayerCameraManager->ViewTarget.Target
+0x420` is still unnamed. This review did not address it.

---

# FK-8 — is `SecondsSinceStart` a real elapsed measure?

## Verdict: **CLOSED on its narrow claim, and now INDEPENDENTLY RE-CONFIRMED. But "FK-8 closed" must not be read as "the timing questions are settled" — its own §7 lists 14 open items.**

### ★ NEW — a direct test, where S111's was indirect

S111 closed FK-8 with a **permutation control**: within a sitting a run cannot outlast the wall-clock
gap since the previous crash; observed violations 0/56 against a permuted mean of 8.56 (P = 0/20000).
That is a valid *inequality* test, but it can only detect gross violations — it cannot measure
accuracy, because it never knows the true elapsed time.

This session does. Every run has a driver-timestamped launch, the stager's logged
`$proc.StartTime`, and a death instant — **ground truth**. Comparing that against the dump's own
`Seconds Since Start`, for the 11 armed deaths where the death instant is known exactly:

```
N=11   median delta -6.2 s   10 of 11 within -4.1 .. -13.5 s   (runs spanning 250-555 s)
outlier: s112c-ctl-21  SSS=507  wall=555.8  delta -48.8 s
```

⇒ **`SecondsSinceStart` is a genuine elapsed measure — confirmed directly, against known ground
truth, on a fresh corpus.** FK-8's closure stands and is now better supported than when it was made.

**Two things the permutation control could not have seen, and this test does:**

- **A systematic ~6 s undercount.** Consistent in sign across all 11. Small, but it means
  `SecondsSinceStart` is not the process-creation instant — it starts marginally later, or is
  sampled marginally before the fault.
- **★ One unexplained outlier: `ctl-21`, −48.8 s.** Verified **not** a multi-process artifact — a
  single PID (`14160`) and a single logged start time across all three stage logs. **I cannot explain
  it.** It is 1 of 11, and it is larger than the ~6 s systematic offset by 8×. It does not threaten
  the closure (the measure is still clearly elapsed-time-like) but it does mean **per-death
  `SecondsSinceStart` values carry occasional error of tens of seconds**, which matters for any
  argument that leans on a narrow band. Filed as open.

### ★ NEW — FK-8 §7.2 item 2 is ANSWERED

The item asks: *"Are the artifact-less terminations crashes or `Stop-Process`?"* and proposes
instrumenting every `Stop-Process` call site. The exit code answers it more directly and more cheaply:

| source | exit code | measured how |
|---|---|---|
| an access violation (the protector's crash kill) | `0xC0000005` | 9 of 9 instrumented control deaths |
| **our own `Stop-Process -Force` / `.Kill()`** | **`0xFFFFFFFF`** | ★ NEW — run as an explicit control this review |
| the artifact-less termination | **`0x0000DEAD`** | the instrumented treatment death |

⇒ **Neither a crash nor an operator kill.** `0xDEAD` is a deliberate sentinel passed to
`TerminateProcess`/`ExitProcess` by something that is **not ours** — there is no `TerminateProcess`
or `ExitProcess` call anywhere in the shim sources (`0xDEAD` appears twice, both as *read* sentinels:
`catalog_probe.cpp:191`, `tutorial_launch.cpp:3370`).

⇒ The project's standing attribution of the artifact-less class to **hangs** — resting on
`CrashReportClient.ini` setting `Stall.RecordDump=false`, so hangs are *configured* to leave nothing
— is **wrong for at least this instance**. Some artifact-less deaths are silent kills, and a process
handle held open across exit recovers them for free.

⚠ **N = 1 for `0x0000DEAD`.** One observation. It is a hard, non-random value from a controlled
comparison, but the claim "the two arms die by different mechanisms" rests on a single instrumented
treatment death and **should not be treated as established**. The instrument is now permanent, so
every future death prices it in at zero cost. This is the single cheapest thing the next session can
strengthen.

### What remains open in FK-8 (its own §7, unchanged by this review)

- **§7.1 — an unadjudicated contradiction between two verifiers** re-anchoring the same deaths to the
  map load (73.1→88.8 s vs a disjoint era-B/era-C split). The file's own instruction stands:
  **do not cite either re-anchored number.** Not resolved here.
- **Item 16 — what routes a death to crashpad vs CrashReportClient** is *more* open than before
  (7 UECC rows satisfy every proposed crashpad correlate).
- **Item 3 — does the `-InjectGapSeconds` 71× result survive splitting by fault family?** Still not
  re-fit. CLAUDE.md still carries that table under a re-examination banner.
- Items 6–15 (symbolisation, FK-24 at corpus scale, the `LoadMap` assert cluster, `_0000`, …).

**Item 1 (the exposure denominator) is now partly served in practice:** this session produced 41
launches with exact per-launch denominators and outcome classes in `docs/fk7-ab-results.csv`, and
`docs/gft-ready-marker.txt` gained a matching run of `injected; base=` records.

---

# Bottom line

| | status |
|---|---|
| **FK-7 the BELIEF** ("the tutorial dies in 1–5 min, budget retries") | **CLOSED — and the cause is ours.** Removing one standing `.text` patch takes the armed-window death rate 100 % → 20 %, p = 0.00071. |
| **FK-7 the FIX** (does the tutorial route survive?) | **PARTLY.** 8/10 treatment runs completed a 331 s hold with a walking, animating hero. Not proven past 331 s; residual 2/10 unexplained. |
| **FK-7 as a GAME DEFECT** | **NOT SUPPORTED, NOT EXCLUDED.** Zero qualifying dumps in 41 more launches. No shim-free run has ever been made, so the game has never actually been observed unaided. |
| **FK-8** | **CLOSED, and independently re-confirmed against ground truth.** One unexplained −48.8 s outlier; ~6 s systematic undercount; 14 downstream timing questions still open in its own §7. |

**The single highest-value next experiment** is no longer FK-7's primary question. It is
`-DKFSNAME=<name>` (swap one `UFunction` instead of 17,126) at a 600 s hold: it simultaneously tests
the treatment's own residual, extends the hold past the historical spread, and shrinks the
instrument's footprint by four orders of magnitude.
