# S111 — reconciling the FK-8 corpus mining with the S110 timing measurements

Two sessions ran in parallel on 2026-08-05 and both touched the tutorial-death timing question.
`e5cd820` (FK-8 corpus mining, 114 death records) rewrote CLAUDE.md's hold guidance; S110
(`fde4915`..`505cc68`) measured five live sittings directly. This reconciles them **from the data**,
not by preferring one author.

---

## 1. First: are the two even measuring the same quantity? — YES, verified

S110 measured wall-clock from process creation (`(Get-Date) - $p.StartTime`, and dump mtimes).
FK-8 uses `seconds_since_start` out of the crash records. Those could easily have had different
origins, which would have made the whole disagreement an artifact. They do not:

| run | S110 wall-clock | FK-8 `seconds_since_start` | delta |
|---|---:|---:|---:|
| `s110itemwatch` | ~434 s | **432** | 2 s |
| `phase2b-void` | ~293 s | **290** | 3 s |
| `animref-SUCCESS` | ~338 s | **336** | 2 s |

Agreement to 2–3 s, which is exactly the slop expected from deriving mine off dump mtimes and watcher
ticks. **The clocks are the same clock. Any disagreement below is real.**

## 2. My error, corrected before anything else

I first read the corpus CSV's empty `exception_code` / `callstack_*` / `unwind_status` columns for my
four runs and concluded they were **unclassified** — and was about to report that "all 22 crashpad
reports are self-inflicted" overstated the case. **That was wrong.** All 22 primary crashpad rows have
those CSV columns empty, but the FK-8 work parsed the minidumps directly (`tools/crashtri/mdexc.py`),
and `docs/fk8-crashpad-class.md` §25–26 and `fk8-crash-clusters.md` §386–387 explicitly classify
`s110itemwatch`, `phase2b-void` and `animref-SUCCESS` — **11 of those 14 are `runtime.dll+0x1`.**

An empty column in one export is not absence of evidence. That is the same mistake this session has
been cataloguing all day, made against a colleague's work instead of the game's.

## 3. Where the two agree (and S110 corroborates FK-8)

* **My three tutorial deaths are the protector family.** That independently corroborates S109's "every
  death ever captured is the protector" and S110's restatement of it. No conflict.
* **`+0x205D` is `catalog_store_fix.dll`'s `.text` RVA `0x205d`.** This **closes open lead #2 in the
  S111 handoff** ("the `+0x205D` family has never been characterised beyond 'executes in an unmapped
  64 KB-aligned region'"). Straight win for the FK-8 work.
* **"~285 s" is not a reliable predictor.** S110 said so from 5 sittings; FK-8 says so from 114
  records. Same conclusion, independent routes.
* **Detect the kill by fault family, not elapsed time**, and anchor to `Load map complete
  …/LVL_Tutorial` rather than `T+<n>`. Correct, and S110's phase-locking work supports it: the staging
  pipeline is deterministic relative to launch, so a launch-relative rule silently encodes the
  operator's schedule.

## 4. Where they conflict — and the CLAUDE.md band is too narrow

CLAUDE.md now states: *"the late-kill mode is **240–295 s, N=15, median 264 s** — only 4 of 15 are
≥283 s"*.

That does not describe the class my sittings belong to. **Primary crashpad reports on the tutorial
route, N=13** — the population containing every S110 sitting:

```
  87  phase2-nostage          283  tutr3-DEATH            432  s110itemwatch
 156  tut3-NOSTAGE            290  phase2b-void           491  s109-positive-control
 160  (unlabelled)            295  tuta1-DEATH            524  tut1-DEATH
 259  tut4-DEATH              336  animref-SUCCESS
 263  tuta3-DEATH
 267  tutr1-DEATH
                       min 87   median 283   max 524
```

**7 of 13 fall outside 240–295**, and four exceed the band's upper bound — by up to **229 s**.
Critically, **two of those four (`s109-positive-control` 491 s, `tut1-DEATH` 524 s) are not S110 runs
at all**, so this is not "my sittings were unusual": the long tail was already inside FK-8's own
corpus before S110 added anything.

⇒ The `240–295 / median 264 / N=15` figure describes **a subset** (plausibly the UECC class, which is
where parsed `SecondsSinceStart` and assert flags live), not the crashpad class. Used as operative hold
guidance it will **under-hold**, which is the specific failure that wastes an armed window.

### And S110's own number is too tight as well

S110 concluded *"budget ~330 s, not 285"* from five sittings. Against the fuller N=13 the median is
283 and the tail reaches 524. **~330 s is better than ~285 s and still wrong.**

## 5. The reconciled position — stronger than either input

**No `T+<n>` hold rule survives contact with this distribution.** Tutorial-route deaths span
**87–524 s** with no usable central tendency: the interquartile spread alone is ~100 s, and the max is
6× the min. Both sessions independently reached "the number is unreliable"; the data says the right
response is not a *better* number but **no number**:

1. **Anchor to the world, not the launch** — hold relative to `Load map complete …/LVL_Tutorial`
   (FK-8's recommendation; S110's phase-locking result explains *why* launch-relative drifts).
2. **Classify the death by fault family** — `RIP == runtime.dll base + 1`, EXECUTE,
   `ExceptionInformation[0]==8` — never by when it happened.
3. **Treat elapsed time as a descriptive statistic, never a gate.** If a sitting needs N seconds of
   armed window, that is a budgeting question with a wide distribution, not a deadline.

## 6. What should change in CLAUDE.md

The `240–295 s, N=15, median 264 s` sentence should say which class it describes, and should not be
the operative hold rule. Suggested: keep the retraction of "~285 s" (both sessions agree), keep the
staging-invariant anchor and the fault-family test, and replace the band with the honest spread —
**tutorial-route deaths measured 87–524 s (crashpad class, N=13, median 283)** — so nobody re-derives
a deadline from it.

⚠ Both timing figures — FK-8's and S110's — were computed from populations neither author chose. Mine
were five sittings I happened to run; theirs is whatever crashed and left a report. Neither is a
designed experiment on survival, and **no exposure denominator exists for either** (FK-8 makes this
point itself about the ~80 staged launches vs ~29 clean deaths). The spread above is a description of
recorded deaths, not a hazard function.
