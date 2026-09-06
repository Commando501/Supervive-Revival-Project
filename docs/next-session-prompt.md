# Next session — re-test FK-7 with the fixed shims

Copy everything below the line into a fresh Claude session.

---

## The task

Re-test **FK-7** — "the tutorial run dies within ~1–5 minutes" — on the tutorial route, using the
instruments built in S111. The previous session did not touch the tutorial; it spent 224 launches on
the **menu** route establishing *why the process dies*, and the answer invalidates most of FK-7's
evidence base.

**Read first, in this order:**
1. `docs/s111-SUMMARY.md` — what was established, what shipped, the rules it added.
2. `docs/s111-FK7-HANDOFF.md` — **the audit findings that this task depends on. Start here for the plan.**
3. `docs/fk7-crash-settled.md` §0 (governing) — but note its S111 corrections banner near the
   173–201 s table, including a **retraction of a retraction** (see below).
4. `CLAUDE.md` → "Before touching anything tutorial- / FK-7- / FK-24-shaped".

## The one thing that changes everything

**`tutorial_launch.cpp:6511-6513` (RM_PLAY) installs a 5-byte `.text` patch at `ProcessInternal` and
holds it for 600 seconds** — `g_done` is never set in RM_PLAY, so it stands for the whole run.

S111 measured, one variable at a time, that **a standing `.text` write is what makes the anti-tamper
protector kill the process**: patch standing **11/12** deaths vs no patch **0/5**, p = 0.00097. A
*permanent* patch to heap **bytecode** is free (0/9); it is the **module image** specifically.

So every FK-7 sitting ever run carried, for its entire duration, the exact condition measured at
**~88 % lethal**. The 600 s window brackets the whole observed FK-7 death spread (87–524 s).
Two independent audits reached this conclusion separately.

**⇒ The primary hypothesis is that FK-7 is largely our own PI hook.** Your job is to test that, not
to assume it.

## What survives of FK-7 (audited)

- **11 death records** survive every contamination filter. **Ten are one 15-hour stretch in
  2026-07-24→26** (nine inside a single 2 h 55 m sitting); exactly **one** — `UECC-C13252F5`, 258 s,
  2026-08-05 — is from the current era.
- **All 11 are shim-mediated.** `log_forceopen_tutorial_url == 2` in 15/15 — **there is not one
  shim-free tutorial run anywhere in the corpus.**
- The **camera family** identification is the most robust thing in the record and survives intact:
  the corrupted `ViewTarget.Target` is **the shim's own spawned camera actor**, proven by the
  shim-private constant `KCAMPITCH -66.0` recovered from crash memory. Note that this is evidence
  *against* a game defect. The **writer of the `0x01` byte is still unnamed**, and the leading
  unexplored suspect is our own shim's diagnostic block.
- **"Deterministic, not flaky" is retracted.** ~10 deaths / 49 staged force-opens at the era-B boot
  base ≈ **20 %**; era-C ≈ 6 %. The quoted "4 launches / 4 crashes" is a 4-run sample from one sitting.

## ⚠ A correction the previous session had to make about itself

S111 claimed `0x3494B40` was "the tick task-graph dispatcher, **not** animation code". **That was
wrong and is retracted.** It quoted 2 of the function's 4 string literals and dropped
`"[PreviousMarker %s, NextMarker %s]"` (×2) — unambiguously **animation marker sync**. S106's original
`FAnimSync::TickAssetPlayerInstances` **stands**. Only this survives: `0x3495973` and `0x349596d` are
the **same function** (one family member, not two). Verify with
`python tools/strxref/strxref.py func 0x3495973` — **and read all four literal lines.**

## Use subagents — maximum 3, and only where they pay

Run them in parallel, then synthesise yourself. Do **not** let a subagent launch the game, inject
anything, or modify files — live runs are sequential and must stay under your control.

- **Agent 1 — build the non-`.text` RM_PLAY variant.** Implement the `UFunction.Func` (+0xE0) pointer
  swap described in `docs/s111-FK7-HANDOFF.md` §3, as a registered `build.ps1` variant, default OFF.
  The shim already *reads* that field for its native-call primitive; writing it is the mirror
  operation and the target is heap. Must produce a distinct `.text` sha256 and pass `verify_dll.py`.
- **Agent 2 — pre-flight the sitting.** Execute the checklist in `docs/s111-FK7-HANDOFF.md` §5 and
  report OK / NEEDS ACTION per item. Several items will waste a launch if missed.
- **Agent 3 — post-mortem each death.** Classify by fault family (`tools/crashtri/fk8_classify.py`),
  read the staged markers, and report whether the death is ours or the game's.

## The experiment

**One variable: whether a standing `.text` patch is present.** Everything else identical.

| arm | probe | prediction |
|---|---|---|
| **control** | current `build\tutorial_launch_play.dll` (600 s standing patch) | dies at the historical FK-7 rate |
| **treatment** | the non-`.text` variant from Agent 1 | if FK-7 is ours, deaths drop sharply |

~10 armed windows per arm. **Classify every death by fault family before counting it** — protector
(`RIP == runtime.dll base + 1`, EXECUTE, `ExceptionInformation[0]==8`) is **ours**, not FK-7.
**Never classify by elapsed time.**

If Agent 1's variant is not viable, fall back to `-DKPLAYHOLDMS=<ms>` to shrink the 600 s window to
the experiment length — strictly worse, but a one-line change that still moves the variable.

## Rules that cost real launches when ignored

1. **A quiet control is VOID, not a pass.** This cost a whole void A/B in S111 before the positive
   control was made to fire.
2. **Verify injection positively, every run.** The `-Hook` path silently fails **~1 in 10**. Require
   `docs/inject-watch.out.log` to change *and* name the DLL, or require the shim's own marker stamp.
3. **Diff `.text` sha256, never file size.** The *deployed* `tutorial_launch_play.dll` is byte-identical
   to `play_statictest` — **use the `build\` path.** Two S111 variants shared file *and* `.text` size
   while differing in hash.
4. **Delete `docs/tutorial-launch-marker.txt` before staging.** It currently contains a stale
   `[SP] done step=4`, and `Stage-Inject` never checks `inject.exe`'s exit code — a failed `sp`
   injection would satisfy the gate instantly and arm the probe with no possessed hero.
5. **Anchor the hold to `Load map complete …/LVL_Tutorial`, not `T+<n>`.** The launch clock carries the
   operator's staging schedule (drifted +33.0 s July→August).
6. **Archive labels are not authoritative** — `archive-crashdumps.ps1` snapshots the whole crashpad DB
   *before* a launch under the *upcoming* run's label. The `RESULT` lines are the record.
7. **`gft_ready_fix` writes nothing to the module image** — but its object walk uses the same
   check-then-dereference TOCTOU that caused the `0x205d` deaths. Classify its faults out too.

## Success criteria

You are done when you can say, with a stated denominator and a fault-family breakdown, **either**:

- *"FK-7 is substantially our own `.text` patch"* — treatment arm's death rate drops significantly
  versus control; **or**
- *"A tutorial-specific game defect survives"* — deaths persist in the treatment arm with SUPERVIVE
  frames on the faulting stack and no self-inflicted signature. **That dump does not currently exist
  anywhere in the corpus, and producing one would be the first real FK-7 evidence in the project.**

"Inconclusive at this N" is an acceptable and honest outcome — say it plainly rather than rounding a
p-value. Set `forceTutorialMatch` back to `false` when done.
