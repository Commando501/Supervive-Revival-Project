# S140 TIER 2 — **`ULokiCMC::StartNewPhysics` RUNS.** The payload-poison / sentinel test.

**2026-08-23. Two staged clients, two injections, read-only RPM plus one DATA-class arm.
Zero `.text` writes, zero PI hooks.**

Pre-registration: **`docs/s140-t2-PREREGISTERED.txt`**, written and committed at `5402c4f` /
`3176139` **before** either injection. Nothing in it was edited afterwards.

Evidence: `docs/s140-t2-BASELINE.txt` · `docs/s140-t2-marker-armh.txt` · `docs/s140-t2-AFTER.txt` ·
`docs/s140-t2-marker-burst.txt` · `docs/s140-t2-f2-AFTER.txt` · `docs/Loki-s140t2-f1.log` ·
`docs/capture.log.s140t2-f1` · `dumps/s140-t2-startnewphysics/`.

---

## HEADLINE

> **[M] `ULokiCMC::StartNewPhysics 0x055C2430` EXECUTES — on the bot AND on the player, essentially
> every frame.** The payload write at `0x055C244F` is measured taking a copy of `Velocity`
> **396 times in 400 samples** at a ~2 ms cadence.
>
> **S139's `[M]` "StartNewPhysics has NEVER run on either component" is REFUTED, not merely
> retracted.** Tier 1 downgraded it to UNGRADED by showing the instrument was invalid; Tier 2
> measures the opposite.
>
> ⇒ **The whole movement chain runs end to end** — `TickComponent` → `ControlledCharacterMove` →
> `PerformMovement` → `StartNewPhysics` — with `Acceleration = ControlInputVector × 50000`.
> **And something WRITES the bot's `Velocity` once it holds a non-zero value** — ⚠ but see §1.5:
> both flights put that value there themselves, and an exactly-zero `Velocity` may SKIP the write
> path entirely, which would make the standing null a FIXED POINT rather than a computed zero.
> The wall is downstream of `StartNewPhysics`, in `PhysFalling` / `CalcVelocity`.

---

## 1. THE RESULT

### 1.1 Flight 1 — the poison is overwritten on BOTH components

`gasattr-sentinel` (`ce56fd715de835a1`) into PID 54632, staged on attempt 1.

| | at arm time (game thread) | +250 ms | +750 ms | +2 s | +5 s | +10 s |
|---|---|---|---|---|---|---|
| **BOT** payload `+0x16B0` | `(-9876.5, -8765.25, -7654.125)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` |
| **BOT** `Velocity +0xE8` | `(0.0009765625, 0, 0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` |
| **PLAYER** payload | `(-1234.5, -2345.25, -3456.125)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` | `(0,0,0)` |
| **PLAYER** `Velocity` | `(0,0,0)` *(never written)* | `(0,0,0)` | … | … | … | … |

Both poisons landed (`botPoison=1 plrPoison=1`, readback-verified), both were **gone within 250 ms**,
and **neither payload ever held the other object's poison** — `isOTHERobjectsPoison=0` on both, so
the two-sided addressing control **passed on a test that could have failed**.

That is cell 2 of the pre-registered BOT table and cell 1 of the PLAYER table. **The PLAYER arm is
entirely velocity-write-free** — it settles the same question with zero perturbation of the system
under test, and it agrees.

### 1.2 Flight 2 — the burst closes the one alternative

Flight 1 leaves exactly one alternative: Tier 1's "the only CMC-side writer of `+0x16B0` is
`0x055C244F`" is a **FLOOR** (55.48 % of `.text` decrypted; blind to `memcpy`/`rep movs` and to
register-computed addresses), so a *targeted* routine zeroing both `Velocity` and the snapshot would
produce the identical observation.

⚠ A **bulk** zeroing of the object was already excluded from flight 1's own samples: `MovementMode`
still read 3, `MaxAcceleration` 50000, and `TimeSinceFallingStart` was **advancing**.

`sentinel-burst` (`62b5423febd6f779`) into PID 47412 re-writes the sentinel into `Velocity` every
~2 ms and reads the payload. **Pre-registered, with all three branches written down first:**

```
BURST RESULT over 400 iterations at ~2 ms:
  hitSentinel = 396  (first at iteration 4)
  hitZero     =   4     <- the four before the first frame boundary
  hitPoison   =   0
  hitOther    =   0
  velocity-still-sentinel-at-read = 364
```

⇒ **the payload IS a copy of `Velocity`, taken by `0x055C244F`, which is inside
`ULokiCMC::StartNewPhysics`.** The alternative is **REFUTED**. `hitPoison = 0` and `hitOther = 0`
mean no sample ever showed anything else.

### 1.3 The frames-passing control (P-D) passed, and it is what makes the null branch meaningful

`TimeSinceFallingStart @+0x12B0`, flight 1, over the 9.78 s the sampler spans:

| | sample 0 | sample 4 | Δ | rate |
|---|---|---|---|---|
| BOT | 3.8334 | 13.6336 | 9.800 s | **1.002 ×** real time |
| PLAYER | 55.8781 | 65.6781 | 9.800 s | **1.002 ×** real time |

**Frames were passing.** Without this, "the poison survived" would have been uninterpretable — and
it is the whole reason the sampler runs on the worker thread (§3).

### 1.4 The flag reads 0 in a world where the step demonstrably runs

`+0x16C8` read **0** in *every* sample, on *both* components, in *both* flights — while
`StartNewPhysics` was running every frame. **That is Tier 1's retraction confirmed by observation
rather than by disassembly alone.** The old S139 inference (`latch == 0 ⇒ never ran`) is now
empirically false, not just unsound.


### 1.5 ⚠⚠ QUALIFICATION — "`Velocity` is actively written to zero" IS WEAKER THAN IT LOOKS

An adversarial verifier, working offline and without sight of the flight, established a mechanism
that bears directly on this: **a small non-zero `Velocity` can CONVERT A NO-WRITE INTO A WRITE.**
On the below-tolerance arm of a `GetSafeNormal`-shaped block the three `ucomisd` at
`0x055B8838 / 0x055B883E / 0x055B884A` all fall through to `je 0x55B8865` and **the write is
SKIPPED**; above tolerance it executes. And in engine `PhysFalling`, `2^-10` gives
`SizeSq = 9.5367431640625e-07` (`0x035ED9B3 call 0x035F4620`), after which
**`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write the result into
`Velocity`** on the `<= 1e-3` arm.

⇒ **What is established, precisely:**

| claim | grade |
|---|---|
| `StartNewPhysics` runs on both components | **[M]** — rests on the POISON being overwritten, which is independent of any `Velocity` write, and the PLAYER arm is entirely velocity-write-free |
| something writes the BOT `Velocity` when it holds a small non-zero value | **[M]** |
| anything writes `Velocity` when it is EXACTLY ZERO | **NOT ESTABLISHED** — and the mechanism above gives a specific reason the exactly-zero case may SKIP the write |

⚠ **Both flights put the sentinel there themselves**, so every observation of `Velocity` changing is
made in a world we perturbed. The player, whose `Velocity` we never touched, stayed `(0,0,0)` —
which is equally consistent with "never written" and with "written to zero".

★★ **This is favourable in one direction: it may make the standing phenomenon a FIXED POINT** —
zero ⇒ no write ⇒ stays zero — which would be a different and much simpler wall than a routine that
computes zero. **And it hands the next session a NAMED CANDIDATE SITE**: `0x035ED9BB` /
`0x035ED9C3` inside engine `PhysFalling`. ⚠ The verifier is explicit that it did **not** establish
`0x035ED98E` is *reached* on a given frame.

---

## 2. THE THREE FREE READS — all three taken, all three reproduce across two clients

Tier 1 §7 ranked these 2/3/4 and recorded that **nobody had ever taken them live.**

| read | BOT | PLAYER | grade |
|---|---|---|---|
| **`CMC+0xC0` `WorldPrivate`** | `0x20FFB5B5600` → `'LVL_Tutorial'` | same object | **[I,strong] → [M]** |
| **`CMC+0x3E4` `MaxSimulationIterations`** | **1** | **1** | [M] |
| **`CMC+0x3E0` `MaxSimulationTimeStep`** | **0.2** | **0.2** | [M] |
| **`CMC+0x3DC` `NumJumpApexAttempts`** | 0 | 0 | [M] |
| **vptr** | `base+0x088F8570` | `base+0x088F8570` | **[M]** |

- ★★★★★ **AND THE PER-EXIT GRADING EXERCISE IS SUPERSEDED, IN THE FAVOURABLE DIRECTION.** Tier 1
  spent its whole budget establishing that engine `PerformMovement` has **exactly six** exits and
  grading each one's input. **All six are now proven PASSED by direct observation — the call they
  all guard demonstrably executes.** That is strictly stronger than reading any individual input,
  and it does not depend on a single offset being right.
- ★ **`WorldPrivate` is non-null and it NAMES THE WORLD.** Engine `PerformMovement`'s **exit 2**
  input is satisfied — Tier 1 graded it `[I, strong]` precisely because this had never been read
  while three documents implied it had. ⚠ **Grade the field read `[M]` and the gate conclusion
  by the observation above, not by this read**: an adversarial verifier established that exit 2 is
  not a bare `WorldPrivate` test but `mov r13,[rcx+0xC0] / test / jne / call 0x035AFC40` — a
  non-null `+0xC0` is *sufficient* (it skips the fallback), but the field is mutable and was read
  at time T while the gate runs at T'.
- ★ **The live component IS a `ULokiCMC`**, so vtable disp `0x720` really is `0x055C2430` — the
  function under test. Had it been the engine base, `0x03600990` would not touch `+0x16C8`/`+0x16B0`
  at all and the whole test would have been void. The probe checks for exactly that.
- ⚠⚠ **`MaxSimulationIterations = 1`, NOT the stock UE default of 8**, and
  **`MaxSimulationTimeStep = 0.2`, not the stock 0.05.** `1 > 0` so the fourth early-out at
  `0x036009B5` (`cmp r8d,[rcx+0x3e4] / jge`, with `r8d == 0`) does **not** bail — but the
  *substepping budget is one iteration*, a real constraint on any future work in this function and
  recorded nowhere else.
  ★ **These are genuine overrides, not a wrong offset** — an adversarial verifier read the
  constructor writing the stock values at those exact displacements
  (`0x035CF917 [+0x3E4] = 8`, `[+0x3E0] = 0.05f`) and confirmed both offsets against the UHT
  records. The ctor sets 8 / 0.05; the live objects read 1 / 0.2. Something overrides them.
  ⚠ **Do not take either offset from a name search** — `MaxSimulationTimeStep` occurs at Offsets
  `0x3E0 / 0x198 / 0x1CC` and `MaxSimulationIterations` at `0x3E4 / 0x1A0 / 0x1D0` across different
  classes image-wide.

---

## 3. ⚠⚠ THE DESIGN DECISION THAT MADE THIS WORK, AND THE FALSE NEGATIVE IT AVOIDED

The handoff's recipe was: *write a sentinel into `Velocity`, wait ≥ 3 frames, read `CMC+0x16B0`.*
Implemented literally inside the arm, **it would have returned a false negative.**

**[M] `BsLadderStep` runs ON THE GAME THREAD inside `OnPI`** (`tutorial_launch.cpp:1234-1274` →
`DoBotSpawn` → `BsLadderStep`), so **every `Sleep()` in it blocks the game thread and no frames
pass.** A write–Sleep–read there is *guaranteed* to read the un-updated payload, and the result
would have been written up as "StartNewPhysics does not run" — recreating exactly the error this
Tier exists to correct.

★ The sampler therefore runs **on the existing Worker thread, between `FsDisarm()` and
`BsFinalReport()`** — the documented `RM_DROPPLANE` B4 precedent
(`tutorial_launch.cpp:6884`, *"Runs on the WORKER thread after FsDisarm + a settle"*). No
`CreateThread`, no stop flag, no join, and `[BS] done` stays last in the marker.

⚠ **And a worker thread spawned *inside* the arm would ALSO have failed**, for a second reason an
offline lane found independently: the ladder holds the game thread for a further ~4.4–5.2 s after
`BsPsExperiment()` returns (its trailing `Sleep(750)` plus the A2 census), so the first several
samples would still have been taken with zero frames passing.

### 3.1 ★★ And the `[M]` that motivated the whole worry is an INSTRUMENT ARTIFACT

`tutorial_launch.cpp:15883` says *"one hit is all this world state delivers (flight 1: hitsGT=1 at
t=+15 s, hot list EMPTY)"*. **Both numbers are self-inflicted.** `OnPI` increments `g_hitsGT`
**after** its `if(g_done || g_inHook) return;` early-out, so **a one-shot ladder can never report
more than 1, whatever the dispatch rate**, and the `hot:` profile window was measured while our own
A0 census held the thread. The decisive control is `docs/fk24-s128-poolspawn-RESULT.txt`: identical
`KFSNAME=""`, identical `swapped=17563`, but a **paced** ladder that releases the game thread —
`hitsGT=588`, **~73 dispatches/s**. ⇒ a multi-hit state machine is viable after all; it was simply
not needed once the sampler moved to the worker thread.

### 3.2 Two further corrections to `BsLadderStep`'s own controls

- **The A0→A1 "stability control" is substantially vacuous.** Its whole window (A0 census ~4.0 s +
  `Sleep(750)` + A1 census ~3.6 s ≈ 8.4 s, from the census's own printed timings) is game-thread
  blocked, and actor spawning is game-thread-only. `A0 == A1` is evidence that the census is
  *repeatable* and that nothing **off-thread** created objects — **not** that no actor spawned.
- **The post-call `Sleep(KBSSETTLEMS)` "give a spawned actor a tick to register" is genuinely
  vacuous and its stated reason is FALSE.** No tick can occur while the game thread sleeps inside
  our own frame. The census works because `GUObjectArray` registration is *synchronous*.
  ⚠ **The dangerous corollary: anything that genuinely needs a TICK has NOT happened when this
  ladder reads it.**

---

## 4. THE POISON — why it was necessary, and why it is safe

**The handoff's sentinel-only design is degenerate, and Tier 1 §7 says so.** With `Velocity` resting
at `(0,0,0)` and `NewObject` zero-filling, "snapshotted a zero Velocity" and "never written" are
**the same bytes**. S139 already banked `R1.velsnap@0x16B0 (0.000,0.000,0.000)`
(`docs/s139-f1-BOT.txt:19`, `-BASELINE.txt:20`) and **it means nothing**; it is not a second
independent negative and must never be cited as one.

★ **Pre-poisoning breaks the degeneracy without touching `Velocity` at all** — which is what makes
the PLAYER arm a *velocity-write-free* test of the same proposition.

★ **The poison is provably unreachable by any consumer.** The payload's only reader is
`GetRecentVelocity` (`.data 0x09BC9AD0` → impl `0x0530AC10`; same `cmove` idiom at `0x0530C7FF` and
`0x0559C59E`): it returns the payload **only when the flag at `+0x16C8` is non-zero**, and the only
writer of `flag = 1` overwrites the payload `0x1A` bytes earlier in the same straight-line block.
The arm reads the flag first and **refuses to poison if it is set** (it read 0 on both objects in
both flights: `botFlag0=0 plrFlag0=0`).

★ **The sentinel was inert, as designed.** `2^-10 = 0.0009765625` uu/s. **P-F held: neither pawn
translated** — BOT `(600, 0, 13240)` and PLAYER `(0, 0, 13240)`, bit-stable across all five samples.

---

## 5. ⇒ WHERE THE WALL IS NOW, AND THE ONE READ THAT SETTLES IT

`Acceleration` is correct and live on the treated bot — it changes direction sample to sample at
constant magnitude 50,000: `(36170.2, -34521.2, 0)` → `(28338.7, -41193.7, 0)` →
`(-17345, -46895.1, 0)` → `(-21698.5, 45046.4, 0)`. **The untreated PLAYER read `(0,0,0)` in every
sample** — the within-run specificity control (P-E), passed.

And **`Velocity` is written to zero every frame**: flight 2's burst shows `Velocity` losing the
sentinel in 36 of 400 2 ms windows — exactly the windows a physics step landed in — while the
payload faithfully tracked whatever we had just put there.

★★★★★ **AN OFFLINE LANE FOUND THE MECHANISM, AND IT IS ONE COMPARE.** In `CalcVelocity`:

```
0x035D605B  mulss  xmm11, [rbx+0x3d0]        ; MaxSpeed *= AnalogInputModifier
0x035D607A  maxss  xmm11, xmm0               ; MaxInputSpeed = max(that, GetMinAnalogSpeed())
   ...
0x035D64F2  comisd xmm8, xmm9                ; NewMaxInputSpeed  vs  1.0e-4  (.rdata 0x076B49E8)
0x035D650F  jae    0x035D6534                ; >= 1e-4 -> the normal clamp
0x035D6511  movups xmm1, [.data 0x99C86A0]   ; ZeroVector
0x035D6520  movups [rbx+0xe8], xmm1          ; *** Velocity.XY := 0 ***
0x035D6527  movsd  [rbx+0xf8], xmm2          ; *** Velocity.Z  := 0 ***
```

`MaxInputSpeed < 1e-4` ⇒ **`Velocity` is written to exactly `(0,0,0)` every frame whatever
`Acceleration` is** — including immediately after the `Velocity += Acceleration*DeltaTime` store two
instructions earlier. That is a complete mechanical account of everything measured since S139
flight 4. ⚠ Grade it **[I, strong]**: the disassembly is read, the live inputs are not.

Its three inputs, and what we now know:

| term | address | status |
|---|---|---|
| `AnalogInputModifier` | `CMC+0x3D0` | **[M] = 1 on the ARM-G-treated bot** (0 on the untreated player). It was **0** in S139 flight 1, i.e. before ARM G. **So it is NOT the zero.** |
| `GetMaxSpeed()` | vt disp `0x4C8` → `0x055ACB90` | **GAS-backed** — tail-jumps to `[Owner_vt+0xC00]`, which returns `0.0f` when `Character+0xF08 AttributeSetStorage == NULL` (`0x055ACB73 xorps xmm0,xmm0; ret`). ARM G filled that storage and wrote `MoveSpeed`/`MaxMoveSpeed = 500`. **NEVER READ LIVE.** |
| `GetMinAnalogSpeed()` | vt disp `0x7C8` → `0x035E3D20`, **not overridden** | returns `MinAnalogWalkSpeed @CMC+0x290` for `MovementMode ∈ {1,2,3}` — and both pawns are **`MOVE_Falling(3)`, which is in that set**. **NEVER READ LIVE.** |

⚠⚠ **NOT OBTAINED: `CMC+0x290` was never read.** The probe for it was written
(`scratchpad/s140t2/minanalog.py`) and the client died — FK-32 — between writing it and running it.
It is now wired into `tools/re/cmc_earlyout_readout.py` so the next sitting gets it **free, with no
injection at all**, and the probe prints the disjunction rather than a verdict:

- **`MinAnalogWalkSpeed ≥ 1e-4`** ⇒ the `max()` cannot fall below `1e-4`, so **this clamp is NOT
  what zeroes `Velocity`** and the lane's headline is refuted.
- **`MinAnalogWalkSpeed < 1e-4`** ⇒ the clamp fires iff `GetMaxSpeed()` is also `< 1e-4`, which
  reduces the whole question to **what `GetMaxSpeed()` returns on an ARM-G-treated bot** — and that
  needs either an S55 reflected call or reading the attribute the getter selects.

**S141's first move is one read-only RPM run against a staged client. No injection.**

---

### 2.1 ★ Independent convergence: an offline verifier reached this arm's design without seeing it

Six offline lanes and their adversarial verifiers ran in parallel with the build, and lane 1's
verifier — working only from the binary and Tier 1 — arrived at the same conclusion the arm had
already implemented:

> *"the shipped instruction — poke Velocity, **wait >= 3 frames**, then read `+0x16B0` — has a
> FALSE-NEGATIVE MODE in exactly the world where the answer is YES. … The fix is cheaper, safer and
> one-sided: **poke the PAYLOAD, never Velocity.** It is provably inert, needs no `+0xE8` write at
> all, and removes the perturbation Tier 1 itself warned about."*

That is the PLAYER arm exactly — poison-only, velocity-write-free — and it is the arm that produced
the cleanest reading. ⚠ Its stated reason is worth keeping: **the payload is durable against the
`0xA50` CLEAR but NOT against the next frame's SET.** It is a per-frame refresh, not a write-once
receipt. That is precisely why the poison (a value the refresh must overwrite) is the receipt, and
why flight 2 had to re-write its sentinel continuously rather than once.

Its independent CFG of engine `PerformMovement` — a **seventh** instrument — reproduced
`1461` instructions · `148` calls · `0` indirect jumps · `0` decode failures · `0` coverage gaps ·
`|reach_backward| = 1075`, identical to all five prior instruments.

---

## 6. CORRECTIONS

### 6.1 `CLAUDE.md` — the S139 block

**STALE (verbatim):**
> `⚠⚠⚠ THE SECOND HALF OF THAT HEADLINE IS RETRACTED (S140) — "StartNewPhysics NEVER RUNS" was
> never measured; its sole support was the +0x16C8 latch, which is invalid (see below and
> docs/s140-tier1-cfg.md). It is now UNGRADED, not [M].`

**REPLACEMENT:**
> ★★★★★ **SETTLED AT S140 TIER 2, AND IT IS THE OPPOSITE: `ULokiCMC::StartNewPhysics 0x055C2430`
> RUNS, on the bot and the player, essentially every frame [M].** Tier 1 showed the latch was an
> invalid instrument (UNGRADED); Tier 2 *measured* the answer with a **pre-poisoned payload**:
> the poison at `+0x16B0` is overwritten within 250 ms on both components, and a 2 ms burst catches
> the payload holding a `Velocity` sentinel **396 times in 400**. S139's "never runs" is **REFUTED**.
> Read `docs/s140-tier2-sentinel.md`.

### 6.2 `CLAUDE.md` — the "NEXT (S141)" line

**STALE:** *"★ NEXT (S141), and it is one experiment: THE VELOCITY-SENTINEL TEST … ⚠ It needs an
external `WriteProcessMemory`, a repo-recorded unresolved hazard."*

**REPLACEMENT:** **DONE, and it needed no external `WriteProcessMemory`** — the write is in-process
on the game thread (`gasattr-sentinel`), which sidesteps that hazard entirely. ⚠ And the recipe as
written would have produced a **false negative**: a write–Sleep–read inside the arm blocks the game
thread, so no frames pass. The sampling must run on the **worker thread after `FsDisarm`**.
Next is `CMC+0x290` + `GetMaxSpeed()` — §5 above.

### 6.3 `CLAUDE.md` — the S139 "residual" line

**STALE:** *"`StartNewPhysics` is STILL never entered (latch 0 on the bot, the player, and all 37
movement components)"* — already marked VOID by Tier 1, now positively **refuted**. The
**phenomenon** it described stands unchanged: `Velocity` stays `(0,0,0)`, the pawn translates
**0.00 uu**, and a `MOVE_Falling` pawn with `GravityScale 1.000` does not fall. **What is new is
that `Velocity` is now known to be actively written to zero, not merely never written.**

### 6.4 `docs/s140-tier1-cfg.md` §5 — the recommended next move

Its decision rule (*"`+0x16B0` still `(0,0,0)` while `+0xE8` holds the sentinel ⇒ it did not run
[M]"*) is **unsound as stated** — its own §7 explains why, and the two halves were never
reconciled. Replace with the **poison-first** design: without a poison, `(0,0,0)` cannot
discriminate "snapshotted a zero" from "never written", which is precisely the trap §7 names.

### 6.5 `driverecompute a2a952babfed256b` IS NOT A VALID REGRESSION GATE

`build.ps1` gives `driverecompute` `-DKBSPSARMS=0xA0` and `gasattr-ctrl` `-DKBSPSARMS=0x0A0` — the
**same value** — so from one source state they must be **byte-identical**, and today both build to
`4465ebc4d7168c03`. The archived `driverecompute.dll` has a different `.text` **size**
(134,144 vs 134,656), so **it predates a source change and was never rebuilt**. Same pattern as
`botspawn_readonly`. `text_digest.py --dupes` independently flags the pair as a **HAZARD**.
**Do not cite `a2a952babfed256b`.**

---

## 7. INSTRUMENT DEFECTS FOUND THIS SESSION

| # | defect | how it would have misled |
|---|---|---|
| S140T2-a | **`cmc_earlyout_readout.py`'s `RANK-1 VERDICT` block printed the RETRACTED latch inference** — a confident `S1`/`S2` verdict built on `+0x16C8`. | A successor running the trusted S139 instrument would have been handed a confident wrong answer. **Fixed**: replaced with the retraction plus a payload recogniser. |
| S140T2-b | **An `#else` "ARM H skipped" marker line moved `gasattr` `2fcc2536e21f18e3` → `6d81e34e675f97f1` while leaving its `.text` SIZE at 137,728 bytes.** | The repo's *"diff the hash, never the size"* rule demonstrating itself. A skip message compiled into the **control** builds is not free. **Fixed**: no `#else`; the gate then reproduced exactly. |
| S140T2-c | **`"one hit is all this world state delivers (hitsGT=1)"` is an artifact of the one-shot ladder**, not a property of the world (`g_hitsGT` increments *after* `OnPI`'s early-out). | It forecloses the multi-hit design permanently. Control: `fk24-s128-poolspawn-RESULT.txt`, identical flags, **hitsGT=588**. |
| S140T2-d | **`BsLadderStep`'s post-call *"give a spawned actor a tick to register"* `Sleep` is vacuous and its stated reason is FALSE.** No tick can occur while the game thread sleeps in our own frame. | Anything genuinely needing a TICK has not happened when that ladder reads it. |
| S140T2-e | **The A0→A1 "stability control" cannot see game-thread actor spawning**, because its whole ~8.4 s window is game-thread-blocked. | `A0 == A1` is repeatability, not "nothing spawned". |
| S140T2-f | **`cmc_earlyout_readout.py` prints `"!! NOT the ULokiCMC vtable … TEST VOID"` for a side whose CMC is simply absent** (`None ≠ True`). Seen on the BOT row of the baseline, *before any bot existed*. | Cosmetic, but it reads as a hard failure. Not yet fixed — noted. |
| S140T2-g | Backslash escapes in a `Bash` tool `command` are collapsed by JSON encoding, so a Python anchor string containing `\r\n` silently failed to match C source containing a literal `\r\n`. | Cost two failed patch attempts. Workaround: build anchors from `chr(92)`, or use the `Write` tool. |

---

## 8. HEALTH, COST AND SCOPE

**Both clients died of FK-32** — exit `0x0000DEAD`, the protector's `NtTerminateProcess` kill, no
artifact of any kind: flight 1 at **T+350.5 s**, flight 2 at **T+318.0 s**, both on the **4th**
manual-map (gft, fo, sp, arm). Neither was caused by the arm; both are the known class.
⚠ Updating the recorded series: `0xDEAD` kills have now come at injection counts
**7 (S132) / 6 / 4 / 4 / 4**, at 1144 / 334 / 350 / 318 s elapsed. Still **no dose-response** and
still not established that repeated injection accumulates risk — but 4 is now the modal count.

★ **Nothing was lost to either death.** Every result was captured as it was produced — marker copied,
external probe run, `dumpimage` taken — before the client died. The one casualty is the
`MinAnalogWalkSpeed` read, and it is recorded as **NOT OBTAINED**, not reinterpreted.

★ **Free by-product:** `dumps/s140-t2-startnewphysics/` (67.70 % of image readable) contributed
**8 `.text` pages new to the corpus**. Small — because everything on this path was already LIT in
`merged13`: `ULokiCMC::StartNewPhysics`, `PhysFalling`, engine `StartNewPhysics`, engine and Loki
`PerformMovement`, `GetRecentVelocity`, the disp-`0xA50` clear, `GetMaxSpeed` and
`ConstrainInputAcceleration` are **all LIT**. ⇒ **the entire downstream investigation can proceed
offline today with no coverage blocker.**

### Scope — do not overstate

⛔ **This is not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 → 0xF7EB60`) remain stripped folds; nothing here went through `SpawnBot`; the AI pawn's
`PlayerState`, `LokiBotController` and behaviour tree exist only because of pokes the game never
performs itself.
⛔ **ARM G is a process-wide CDO poke and ARM H writes a live component's `Velocity`. Diagnoses, not
shipping fixes.** Neither belongs in the default shim set.
⛔ **The pawn still moves 0.00 uu.** What changed is that we now know *why not*: it is not that the
physics step never runs — it runs, and it computes zero.

---

## 9. ARTIFACTS

| build | RAW `.text` | role |
|---|---|---|
| `botai` | `5e47c13cf7f0a158` | regression gate — **UNCHANGED** |
| `gasattr` | `2fcc2536e21f18e3` | regression gate — **UNCHANGED** |
| `gasattr-ctrl` | `4465ebc4d7168c03` | regression gate — **UNCHANGED** |
| **`gasattr-sentinel`** | **`ce56fd715de835a1`** | **flight 1** — ARM D+F+G+H (`KBSPSARMS 0x3A0`) |
| **`sentinel-burst`** | **`62b5423febd6f779`** | **flight 2** — + ARM H2 (`0x7A0`) |
| `sentinel-nogas` | `f62d3a9cc4cf0562` | ARM H without the GAS port (`0x2A0`), built, **unflown** — redundant, since `gasattr-sentinel` already contains a GAS-treated object (bot) and an untreated one (player) in the same run |

All verified **mutually distinct** — an A/B against a copy of itself has burned a live run here.
Pre-edit artifacts archived at `dumps/s140-arms-pre/` with their digests.

**S136 emitted-code control, two-sided and discriminating:** the ARM H / ARM H2 banner literals are
present in exactly the builds whose bit is set and **absent from all others**, and ARM G's own
literal tracks bit 8 exactly (present in `gasattr` and `gasattr-sentinel`, absent from
`gasattr-ctrl`, `botai`, `driverecompute`, `sentinel-nogas`). ARM H sits behind a **preprocessor**
`#if (KBSPSARMS & 0x200)`, not a runtime `if`, so S136's constant-folding mechanism cannot apply —
and the byte-scan is run anyway.
