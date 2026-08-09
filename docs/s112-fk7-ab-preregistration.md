# S112 — FK-7 A/B: pre-registration

**Written 2026-08-07, BEFORE any launch was spent.** Fixed in advance so the analysis cannot be
chosen after seeing the data. Anything decided later is marked as such in the results doc.

---

## 1. The question

Is FK-7 — *"the tutorial run dies within ~1–5 minutes"* — substantially **our own standing `.text`
patch**, or does a tutorial-specific **game** defect survive its removal?

## 2. Why this is now askable

`tutorial_launch.cpp:6511-6513` (RM_PLAY) installs a 5-byte `0xE9` jmp into `ProcessInternal`
(module `.text`, RVA `0x13454A0`) and then waits on `g_done` for **600000 ms**. `g_done` is never set
in RM_PLAY, so **the patch stands for the entire run**.

S111 measured, one variable at a time, at a 320 s hold:

| what is modified | runs | protector deaths |
|---|---:|---:|
| nothing (`-NoHook`, or an inert mapped DLL) | 0/11, 0/11 | **0 %** |
| UFunction `Script` **bytecode**, heap, permanent | 0/9 | **0 %** |
| `.text` prologue × 3, transient | 4/12 | 33 % |
| `.text` × 1, **standing** | 7/8 | **88 %** |

⇒ Every FK-7 sitting ever run held the ~88 %-lethal condition for its whole duration, and the 600 s
window brackets the entire observed FK-7 death spread (87–524 s).

## 3. Design — one variable

Strictly one thing differs between arms: **whether a standing `.text` patch is present.** Staging,
injection gaps, hold length, teardown and archiving are byte-identical (`configs/fk7-ab-run.ps1`).

| arm | probe | prediction |
|---|---|---|
| **control** | `build\tutorial_launch_play.dll` — the 600 s standing `.text` patch | dies at a high rate |
| **treatment** | the non-`.text` variant (heap `UFunction.Func` swap; fallback: a shortened hold) | if FK-7 is ours, deaths drop sharply |

Both arms carry the same shared baseline exposure from staging, which is therefore controlled, not
eliminated: `fo`'s PI prologue jmp (≤8 s `.text`), `sp`'s PI prologue jmp (≤8 s `.text`), and `fo`'s
slot-285 `CustomLogin` vtable patch (≤25.5 s `.rdata`). `gft_ready_fix` writes no module image at all.

**Allocation: strict alternation**, starting with control. This balances any monotone drift across
the sitting (thermal, boot-session, ASLR era) rather than confounding it with arm, which is a known
hazard in this corpus — the FK-7 evidence base is itself 10-of-11 from a single 15-hour stretch.

## 4. Unit of analysis

The **armed window**, not the launch. A run counts only if the positive control fired.

**The positive control is `[PL] *** init complete: body=…; camera + WASD active ***`**
(`tutorial_launch.cpp:5190`).

This *replaces* the mandated 3× `play_novtguard` control, deliberately. That control fires only on
the camera family, which appears ~8 % per staged launch, so `P(all 3 quiet) ≈ 0.92³ ≈ 78 %` — it
would declare a sitting VOID about four times in five **even when everything works**. The
replacement is better on all three axes that matter:

- it fires ~100 % of the time when RM_PLAY actually armed, so a quiet control means something;
- it is **arm-symmetric** — it fires in both arms, so it cannot bias the comparison; and
- it detects the single most likely treatment-arm failure, a callback mechanism that silently
  gets no game-thread hits. That failure would otherwise masquerade as "the treatment arm survives."

Outcome classes (recorded by the driver):

| class | in denominator? |
|---|---|
| `DIED` — process gone before the hold expired | **yes** |
| `SURVIVED` — reached the full hold, armed | **yes** |
| `VOID_ARM` — probe injected, positive control never fired | no |
| `VOID_DIED_PREARM` — died before the control fired | no (see §7 sensitivity) |
| `STAGE_FAIL` — `fk24-stage.ps1` aborted (exit 2/3/4/5) | no |

## 5. Hold

**330 s, measured from probe injection**, both arms.

Measured-from-injection is staging-invariant by construction. It is chosen over any `T+<n>` rule
because `SecondsSinceStart` is the **launch** clock and carries the operator's staging schedule,
which moved **+33.0 s** between the July and August batches — so every `T+<n>` rule silently drifts.
The `Load map complete …/LVL_Tutorial` timestamp is recorded per run as the cross-session anchor.

330 s is close enough to S111's 320 s that the 88 % standing-`.text` figure stays directly
comparable, and it clears the 240–295 s late-kill band with margin.

**Phase 2 (conditional):** if the treatment arm is clean at N=10, run treatment-only extended holds
at **600 s** — the full RM_PLAY window — to probe the 336/432/491/524 s tail. Long holds are spent
only where they can produce the novel result.

## 6. Stopping rule

Target **N = 10 armed windows per arm**. One pre-planned interim look at N = 6 per arm, stopping
early only if Fisher's exact (two-sided) gives **p < 0.005**; otherwise continue to 10. The
conservative interim boundary keeps the final α ≈ 0.05.

Fisher's exact at N=10/arm against a clean treatment arm: 8/10 → p = 0.00015; 6/10 → p = 0.0054;
5/10 → p = 0.016; 4/10 → p = 0.043; **3/10 → p = 0.105 (not significant)**. So if the control arm
comes in near the historical ~20 % rather than near S111's 88 %, **this design is underpowered and
the honest report is "inconclusive at this N"** — stated here in advance so it cannot be rounded
later.

## 7. Analysis, fixed in advance

- **Primary:** any death vs survival among armed windows. Fisher's exact, two-sided.
- **Sensitivity:** repeat with `VOID_DIED_PREARM` counted as deaths. Report both. If the two arms'
  pre-arm death counts are asymmetric, that is itself a finding and is reported, not smoothed.
- **Secondary, and the point of the exercise: every death is classified by fault family before it is
  counted.** Never by elapsed time.
  - **protector** — `RIP == <runtime.dll module base> + 1`, EXECUTE, `ExceptionInformation[0] == 8`.
    Resolve runtime.dll's base **per dump**; it is not the literal `0x7FF90E000001` (that was one
    boot's instance), and a substring match on `runtime` also matches `VCRUNTIME140.dll`, which
    inverted a real 0/22 negative in S111. → **ours**.
  - **`gft_ready_fix` TOCTOU** — the same check-then-dereference pattern that produced
    `catalog_store_fix`'s `.text` RVA `0x205d` faults. → **ours**.
  - **`ProcessInternal`-depth fault** — `0x1345511` lies inside the `ProcessInternal` extent; a
    signature of the instrument's entry point, per `s108-crash-triage.md:361-380`. → **ours**.
  - **camera family** — the one-byte `0x01` at `PlayerCameraManager->ViewTarget.Target+0x420`. The
    corrupted object is **the shim's own spawned camera actor**, proven by the shim-private constant
    `KCAMPITCH -66.0` recovered from crash memory. → **ours** (this is evidence *against* a game
    defect, not for one).
  - **anim family** — a freed `UAnimationAsset` the shim loaded. S110 fixed this via `KANIMREF`,
    which the candidate build carries. → **ours**.
  - **assert / `LowLevelFatalError` / `fastfail` / `gsfailure`** — not an anti-tamper kill; counted
    and reported separately.
  - **hang** — no exception, no dump (`CrashReportClient.ini` sets `Stall.RecordDump=false`, so
    hangs are *configured* to leave nothing). Recognised from the log tail.
  - **GAME DEFECT** — SUPERVIVE frames on the faulting stack and **no** self-inflicted signature.
    **No such dump exists anywhere in the 114-death corpus.** Producing one would be the first real
    FK-7 evidence in the project, and is the single most valuable possible outcome here.

## 8. What would falsify the primary hypothesis

Deaths persisting in the treatment arm at a rate statistically indistinguishable from control,
**with** at least one death classified GAME DEFECT. Absent that classification, persistent treatment
deaths mean a self-inflicted mechanism we have not yet named — not a vindication of FK-7.

## 9. Known limitations, stated up front

- **No shim-free tutorial run has ever been made** (`log_forceopen_tutorial_url == 2` in 15/15), and
  this experiment does not make one either — the treatment arm still injects four DLLs. It removes
  the standing `.text` write, not the shims.
- ~2 of 4 launches reach an armed window, so ~20 armed windows costs ~40 launches.
- The 71× injection-gap reduction was measured on the **menu** route; whether it moves tutorial
  deaths is untested, and this experiment holds the gap fixed at the default 20 s rather than
  testing it.
- `fo`'s `.rdata` writes (rows 2 and 5 of the handoff's table) are **not** tested here. S111
  measured `.text`; the shim's assertion that `.rdata` is also caught is an S61-era inference that
  has never been tested under the S111 protocol. It is held constant across arms.
