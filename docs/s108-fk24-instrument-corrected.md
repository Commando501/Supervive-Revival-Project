# S108 — FK-24: the probe's own verdict was the artifact; three instrument defects fixed

**Date:** 2026-08-04 (S108) · **Branch:** `dedicated-server-stub`
**Governing prior:** `docs/fk24-writer-probe.md`, `docs/fk7-crash-settled.md` §0, `docs/next-session-prompt-s108.md`

Every claim is tagged **MEASURED** (read out of a dump, a log, a binary, or the source) or **INFERRED**.

---

# ⚠⚠ RETRACTIONS — READ BEFORE ANYTHING ELSE

An adversarial pass (`docs/s108-skeptic-review.md`) **refuted several claims below**. They are left
visible on purpose; the retraction history is the value. **Where this block and the body disagree,
this block governs.**

### R1 — ★ §2's `vtHits=1` conclusion is REFUTED. It was a SAMPLING artifact.

§2 says *"MEASURED across two runs: after RM_PLAY's one-shot init completes, `vtHits` did not advance
past 1."* **That is false, and it is this project's signature error committed by the very document
written to catalogue it.** Every `vtHits` reading in the record comes from the `NOT-YET at 8000 ms`
line — which in `fk24-run-wp2r2-probe-retry.txt` is at **line 89**, while `[PL] *** init complete ***`
is at **line 128**. **There is no post-init sample in any run.** A pre-init reading was recorded as a
structural property of the game.

The disproof was already on disk and this doc failed to open it: dump **`FED1F952`** — produced by
`wp2r2`, *the very run §2 concludes from* — is an AV writing `0x2bd733eaee0`, which is that run's own
`[WP] target &VT.Target=0x2BD733EAEE0`, at a RIP inside that run's own shim image, on bytes
`4C 89 33` = the phase-0 `mov [rbx],r14` **selftest store**. So the selftest store **did execute**,
after the +8 s sample ⇒ **`vtHits` ≥ 2**.

⇒ **FK-24a is REFUTED and withdrawn.** **FK-24c's "falsification" of the `DoTopDownCam` re-assert is
WITHDRAWN** — it rested on FK-24a. **FK-24b is a PHANTOM:** the missing census is explained by the
census *trigger* underflow, not by a stopped thread (see R4). §2's "the next fix is not a new
watchpoint mode" therefore rests on a dead premise and must not be actioned as written.

### R2 — §3.3 / FK-26 is REFUTED. "No UECC directory" ≠ "no dump".

Sentry's crashpad **does** write a minidump — the skeptic caught one live: a **43,893,392-byte**
minidump plus its Loki.log in the crashpad database at 02:17:16, **gone by 02:20** (uploaded, then
deleted). My "silent, dumpless death" was my instrument's blind spot, measured with a tool that only
enumerates `UECC-*` directories. The discriminator is clean and anti-correlated **6/6**:
`handing control over to crashpad` ⇔ no `UECC-*` dir.

§3.3's table is also wrong: **`wp2r2` did not "survive"** — it crashed at 01:57:52 producing
`FED1F952`; a **fourth** force-open run (`wpDRr2`) is missing from it; and `wpDRr2` died 0.8 s after
the `[SMA]` block, not during LoadMap. Corrected tally: **4 of 4 force-opens crashed** (5 of 5
including the `novtg1` control). **FK-26 duplicates the already-filed FK-25** (`fk7-crash-settled.md`
§0.3's "5 dumpless deaths", where the denominator point was already made) — **merge it into FK-25,
do not carry it as a new item.** The *run-budget* consequence still stands; the "invisible to any
census" framing does not.

### R3 — §0's C1 is narrowed. "The DR watchpoint was live the whole time" is NOT established.

The DR arithmetic was independently re-derived and holds (`0x110405 = g_wpDr7Val | bit10`, `Dr6`
= B0|B1, BS=0, TF=0), and `wpDRr2` adds a clean 138-thread arm with `dr7ReadbackZero=0`,
`preexistingDR=0`. **But** `WpArm()` resets `selfPhase` to 0 on *every* arm and the retarget path
re-arms, so `selfPhase=0` means *"not since the last arm"*, not *"never"*; and the dump is a single
snapshot from a run that also printed a `W2 ... bits CLEARED BY SOMETHING ELSE` line. The defensible
claim is: **the DR watchpoint demonstrably fired on the game thread, so the VOID verdict and the
escalation it triggered were unfounded.** Continuous liveness is not shown.

### R4 — two of my own fixes were HALF-fixes, now completed (S108b)

* **The census underflow: I clamped the printed value and left the trigger.** `now` is sampled before
  `WpArm()`, so `now - g_wpLastCensus` underflowed and DR mode fired a bogus `t=+0s` census
  immediately. Now a **signed** difference. This is what created the FK-24b phantom.
* **★ D-S108-3 was `#if KWPROBE==1` only, so page mode kept the process-killing gap** — and
  `FED1F952` is `_wprobe2.dll` self-killing through exactly it. §4's ⚠ warned only about the two
  174,080-byte builds; **`_wprobe2.dll` and `_wprobe2_v66.dll` were lethal too.** Fixed: the fallback
  now also restores page protection on an orphaned write fault inside our page.

### R5 — §3.1's "substitutes for the press EXACTLY" is overstated

`SoloMode` really does have exactly one reader and one writer. **But** `handleStartSoloMode` also does
`s.partyVer++`, publishing a new party version — and `FParty.Version` is the `SetParty` gate — which
the flag does **not** do. The client's `TryStartSoloMode`/`OnStartSoloModeComplete` path is also
skipped, and the flag reports the match **from login** (travel at +11 s, *before* the lobby Browse at
+15 s). Correct word: **sufficient**, not identical.

### R6 — a lead neither document noticed

**3 of 3 runs that got past the body build died 0.8–10 s after the shim's own `KSMACTOR`
`SetStaticMesh` block.** There is a free single-variable bisect available: **`-DKSMACTOR=0`**.
This is the cheapest open lead in the session and nothing was spent on it.

Post-retraction artifact hashes (all `verify_dll.py` **PASS**; `play` still `a67239a0d83d9300`):
`_wprobe` `1feeb8bc201ceac4` · `_wprobe2` `a7e1e2ac792ea387` · `_wprobe2_v66` `1a47da24b492d8dd`.

---

## 0. Headline

**TASK ONE's premise is FALSIFIED, and it was falsified twice independently.**

S108 was briefed to escalate FK-24 from the DR watchpoint (`wprobe`) to the page-mode watchpoint
(`wprobe2`), on the strength of S107's line:

```
[WP] selftest *** FAIL: no trap 8000 ms after arming (selfPhase=0) -- the watchpoint is VOID on the
     game thread. READ NOTHING ELSE IN THIS RUN AS A NEGATIVE. ***
```

That line is wrong about its own subject. **The DR watchpoint was live the whole time.**

| # | route | finding |
|---|---|---|
| 1 | **source analysis** (this session, before any launch) | `g_wpSelfPhase` advances *after* the idempotent store retires (`WpSelfTestTick`, `tutorial_launch.cpp:1551`). So `selfPhase=0` means the store **never executed** — a statement about `VtGuard`'s cadence, not about the watchpoint. |
| 2 | **the S107 crash dump** (`166396E2`, triaged by subagent) | The crash was `0x80000004 STATUS_SINGLE_STEP`; `Dr7` == the probe's own `g_wpDr7Val`; `Dr6` low nibble = B0\|B1; RIP one byte past the probe's **own selftest store** (`mov [rbx],r14`); **127 of 128 threads still armed, GameThread among them**. |

Route 2 is the stronger one: it shows the game thread's debug register **fired**. The packer never
defeated DR. So the documented escalation criterion — *"escalate to `wprobe2` on a VOID verdict, never
on a clean negative"* — **was never met**, because there was no VOID.

This is the project's dominant error mode (`memory/supervive-instrument-artifact-pattern`) occurring
*inside the positive control built specifically to prevent it*, which is now its **sixth** confirmed
instance and the second to land inside the very instrumentation meant to catch it.

> ### The writer is still NOT named. FK-24 remains OPEN.
> Nothing here identifies who writes `0x01`. What S108 did is repair the instrument so that a future
> sitting can produce a readable verdict, and remove a defect that made the probe **kill its own host**.

---

## 1. The three defects, and the fix for each

All in `tools/sigbypass-mod/tutorial_launch.cpp`. All are inside `#if KWPROBE` regions —
**MEASURED: `tutorial_launch_play.dll` still hashes `.text` = `a67239a0d83d9300`, byte-identical to
the pre-S108 candidate**, so the FK-7 A/B set is untouched by any of this.

### D-S108-1 — the selftest verdict conflated "never ran" with "never trapped"

`WpSelfWatch` printed FAIL at a hard-coded 8000 ms. But arming happens at the first successful
`VtResolve()`, which is **inside the one-shot RM_PLAY init block** — and that block owns the game
thread for far longer than 8 s. MEASURED in S107: the FAIL printed at +8 s and
`[PL] *** init complete ***` did not appear until somewhere before the +29 s census. `VtGuard` could
not physically reach the selftest call site inside the deadline.

**Fixed.** `WpSelfWatch` is rewritten to be phase-aware and the deadline is now `KWPSELFWAITMS`
(default 90000):

* `selfPhase >= 1` + no trap ⇒ `FAIL(VOID-WATCHPOINT)` — the only shape that licenses the word "void".
* `selfPhase == 0` ⇒ `INCONCLUSIVE: the positive control NEVER RAN, so the watchpoint is UNTESTED:
  this is neither 'live' nor 'void'. Do NOT escalate on this line alone.`
* At 8 s it now prints a `NOT-YET` line naming S107's misreading in words, and keeps watching.

`WpVerdict`'s ROW6 is likewise split into **ROW6a UNTESTED-INSTRUMENT** and ROW6 VOID-INSTRUMENT.
ROW6a's `NEXT` explicitly says *"Do NOT switch KWPROBE mode on this row"* — because the page build
drives its selftest from the **same** `VtGuard` call site and would have reproduced the identical
non-result. **MEASURED: it did exactly that** (§2).

### D-S108-2 — nothing measured whether `VtGuard` was running at all

Added `g_wpVtHits`, incremented immediately **before** `WpSelfTestTick`, so a quiet selftest is
attributable rather than mysterious. Reported on the selftest lines and on every census.
Also added `selfPhase` and `orphanSwallowed` to the census, and **clamped the census clock** — S107's
first census printed `t=+4294966s`, an unsigned underflow because `now` is sampled at the top of
`WpThread`'s loop, *before* `WpArm()` runs, and the 128-thread arm sweep takes longer than a tick.

### D-S108-3 — ★ the probe could KILL THE PROCESS, and in S107 it did

**MEASURED from dump `166396E2`.** Debug registers live in the **thread**, not in `g_wpArmed`. Any
path that leaves DR7 set while the flag is down — a partial or failed disarm, a **second probe image**
owning its own copy of the flag, the packer restoring a context — turns the next store to `&Target`
into a `STATUS_SINGLE_STEP` that `WpHandle` **declines**. An unhandled single-step terminates the
process. S107 had two `wprobe` images resident (MEASURED: the crashing image base `0x1A4A4690000` is
not any of the four in `fk24-stage-run2.log`), i.e. two `CrashVEH`s, two `g_wpArmed`s, one set of
debug registers.

**Fixed.** `WpHandle` gains a **terminal fallback**: with the flag down and the grace window expired,
it still swallows a single-step that *provably* names our slots (`Dr6 & (bit0|bit1)` **and**
`Dr0 == g_wpAddr`), clearing `Dr6` and continuing. It is **not** recorded as coverage — the run is
over as a measurement — it only stops the instrument from killing its host. Swallows are counted and
reported as `orphanSwallowed=`.

> ⚠ **The S107 crash was therefore NOT a game crash.** It was the instrument. Anyone reading
> `crash_census.csv` should treat dump `166396E2` as an instrument artifact, not an FK-7 data point.
> Full frame-by-frame triage: `docs/s108-crash-triage.md`.

---

## 2. What the page build actually did — and why it is the WRONG escalation

Run `wp2r2` (2026-08-04 01:53), `tutorial_launch_play_wprobe2.dll`, KWPROBE=2. **MEASURED:**

```
[VTG] pcm=0x2BD733EAAC0 ViewTarget@0x420 (reflection) PendingViewTarget@0xC40
[WP] cfg mode=PAGE_READONLY armAt=0 selftest=1 sweep=250ms poll=2ms hold=0ms
[WP] arm PAGE_READONLY OK: VirtualProtect=1 wasProt=0x4 readback prot=0x2 covered=1 coalesced=0
[WP] selftest NOT-YET at 8000 ms: selfPhase=0 vtHits=1 -- the idempotent store has NOT EXECUTED ...
[PL] *** init complete: body=BUILT; camera + WASD active ***
```

* The offset is **reflection**-resolved (`ViewTarget@0x420 (reflection)`), so offset-derived
  conclusions are not fallback-constant artifacts. ✅
* The page armed and **covered=1**. ✅
* **`vtHits=1`** — `VtGuard` reached the selftest call site exactly **once**, on the pre-arm resolve,
  and **never again**. So the page build reproduced D-S108-1 precisely as predicted. This is the
  measurement that turns "escalate to wprobe2" from a plan into a known dead end.
* **No `[WP] census` line ever printed**, though the census is common code (not mode-gated) and the
  process lived ≳50 s armed against a 30 s cadence. ⇒ **`WpThread` stopped.** Cause unknown; filed.
* Consequently **`traps=` was never reported at all**. ⚠ **Do NOT record "the page probe saw zero
  traps"** — the counter was never printed. The honest statement is *the page build produced no
  trap telemetry whatsoever*.

**INFERRED but strongly indicated:** the page build is a worse instrument here, not a better one. It
inherits the same starved selftest, adds an unexplained poll-thread stop, and by the doc's own
analysis (`fk24-writer-probe.md` §2.5) perturbs the timing of the race under study.

### The real blocker for FK-24, now named

`VtGuard` is invoked from the transiently-installed `ProcessInternal` hook. **MEASURED across two
runs: after RM_PLAY's one-shot init completes, `vtHits` did not advance past 1.** Until `VtGuard`
runs repeatedly post-init, the positive control cannot fire *in either mode*, and the
`&Target` re-assert that `DoTopDownCam` was expected to perform every 3rd hit (§2.4 item 2 of the
probe doc, INFERRED there) **is not happening either**. That expectation should now be treated as
**falsified pending re-measurement**, not as a property of the game.

**The next fix is therefore not a new watchpoint mode.** It is to drive `WpSelfTestTick` from a
game-thread site that actually runs after init, and to measure the PI-hook hit cadence directly.

---

## 3. Getting into the tutorial without a human — and a new hazard

### 3.1 `forceTutorialMatch` replaces the START button exactly

The S107 recipe needs a human to press PLAY → TUTORIALS → BASIC TRAINING → START. That press has
**exactly one** backend effect: `POST /startSoloMode` sets `playerState.SoloMode`, and
`handleCoreGamePlayer`'s gate is `forceTutorialMatch || SoloMode != ""`. **MEASURED: `SoloMode` has
no other reader in the codebase** (`store.go:66` + that gate), so the flag substitutes for the press.

Set `forceTutorialMatch = true` (`server/internal/interactive/interactive.go`) — the S65/S90/S91
force-open config — and **MEASURED: the client parked itself 13 s after launch**:

```
[2026.08.04-06.42.54] LogTravelManager: Attempting to travel to Match: ID:"match-9b9d..." Address:""
```

That is far faster than the "~1/min poll" the source comment predicts. Revert to `false` for the
plain interactive menu.

`configs/fk24-stage.ps1` (new) automates the whole sitting: pre-flight that ags is really arming a
match, wait for the parked state, then inject in order, gating each step on measured evidence and
copying the marker off after every injection (FK-25).

### 3.2 ★ Order correction: `gft_ready_fix` must precede the force-open

**MEASURED (run `wp2r1`).** With `gft_ready_fix` injected *after* the force-open, the run died ~60 ms
after `LogLokiGameMode: Display: Client is ready to play`, with the log full of
`ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready`. S107 got away with the
documented `fo → gft → sp` order only because it injected all four back-to-back, so gft landed
*during* the 5.7 s LoadMap. Injecting gft **first** removes the race instead of winning it by luck —
it needs no world and re-applies its bit every ~2 s for the whole session.

### 3.3 ★ NEW, and it changes every run budget: the force-open dies SILENTLY ~2 of 3 times

**MEASURED, 3 force-open attempts on 2026-08-04:**

| run | gft order | outcome |
|---|---|---|
| `wp2r1` | after fo | **died** during/at end of LoadMap — **no UE dump** |
| `wp2r2` | before fo | survived → full `[PL] init complete` |
| `wpDRr1` | before fo | **died** 5 s after `UEngine::Browse Started Browse: ".../LVL_Tutorial?game=..."` — **no UE dump** |

In both deaths Sentry's crashpad took the process (`handing control over to crashpad`) and
**`Saved/Crashes` gained nothing** — no `UECC-*` directory, no callstack, no `RequestExit` line.
`gft_ready_fix` was confirmed working in `wpDRr1` (`instances=11, readiness bit set`), so 3.2 is
**not** the whole story: the ordering fix is necessary but not sufficient.

**Consequences, and they are load-bearing:**

1. **A tutorial sitting needs ~3× the launches its plan assumes.** `fk24-writer-probe.md` §4.6 budgets
   ≥6 launches against a 1-in-3-to-1-in-2 bug rate; that arithmetic silently assumed every launch
   *reaches* the armed window. **MEASURED: only 1 of 3 did.**
2. **This is a live FK-25 instance and it is invisible to the dump census.** `crashtri/harvest.py`
   enumerates `UECC-*` directories; these deaths create none. Any statement of the form "N of 87
   dumps show X" has a denominator that **excludes this failure mode entirely**.
3. It is a distinct open item from FK-7 and from FK-24. Filed below.

---

## 4. Artifact matrix (rebuilt S108, `.text` sha256[:16], all `verify_dll.py` **PASS**)

| DLL | `.text` len | sha256[:16] | note |
|---|---:|---|---|
| `tutorial_launch_play.dll` | 162,816 | `a67239a0d83d9300` | ★ **unchanged from pre-S108** — the candidate is untouched |
| `…_play_novtguard.dll` | 159,744 | `7bb7c67e371f3f1e` | unchanged — FK-7 positive control |
| `…_play_testactor.dll` | 163,328 | `321c71de3346c205` | unchanged |
| `…_play_wprobe.dll` | 174,592 | `5adeef77a0797ba0` | **S108: all three fixes** (was `6da63dc0…`) |
| `…_play_wprobe2.dll` | 174,592 | `bdefac3ba0c32abd` | S108 fixes D1/D2 (was `0ec5a66b…`) |
| `…_play_wprobe2_v66.dll` | 174,592 | `0159ef6d15d72481` | **new** variant, `-DKPUPYAW=-90` |
| `…_play_wprobe_v66.dll` | 174,080 | `6627a2a3fc248c16` | ⚠ **STALE** — pre-S108, has the process-killing gap |
| `…_play_wprobe_noxformfix.dll` | 174,080 | `d65fb5f0067a9e1c` | ⚠ **STALE** — same |

⚠ The two 174,080-byte `wprobe*` builds predate D-S108-3 and **can kill the process**. Rebuild before use.

---

## 5. Open items this session created or sharpened

| id | item | status |
|---|---|---|
| FK-24 | **who writes `0x01` at `PCM+0x420`** | **OPEN.** Unchanged. No trap was ever recorded by any mode. |
| FK-24a | `VtGuard`/PI-hook does not run post-init (`vtHits` stuck at 1) — blocks the positive control in **both** modes | **NEW, and it is the actual blocker.** |
| FK-24b | `WpThread` stops in page mode (no census ever printed) | **NEW.** Cause unknown. |
| FK-24c | `DoTopDownCam` re-asserting `&Target` every 3rd hit | **falsified pending re-measurement** — it was INFERRED, and `vtHits=1` contradicts it |
| FK-26 | **force-open dies silently during LVL_Tutorial load ~2 of 3 attempts, leaving no UE dump** | **NEW.** Invalidates run budgets and is invisible to the dump census. |
| FK-25 | marker truncated on every injection | mitigated operationally by `fk24-stage.ps1`'s per-stage copies; the shim still uses `CREATE_ALWAYS` |

---

## 6. What NOT to do next (each of these was tried or is now excluded)

- **Do not escalate to `wprobe2` on a `selfPhase=0` line.** It shares the starved selftest and adds a
  stopped poll thread. MEASURED, not argued.
- **Do not read `docs/tutorial-launch-marker.txt` after a later injection** and treat it as the run's
  record. It is truncated. Use the `fk24-stage-*.txt` copies.
- **Do not treat dump `166396E2` as an FK-7 or game-side data point.** It is the probe killing the host.
- **Do not budget a tutorial sitting on launch count alone.** Budget on *armed windows reached*;
  MEASURED yield is ~1 in 3.
- **Do not run the two 174,080-byte `wprobe*` DLLs.**
