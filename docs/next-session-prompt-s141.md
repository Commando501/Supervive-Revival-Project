# S141 — `StartNewPhysics` RUNS, and `Velocity` is written to ZERO. Find the writer.

**Paste this whole file as the opening prompt of a fresh session.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first (auto-loaded; current as of this commit), then
**`docs/s140-tier2-sentinel.md` (the measurements) and `scratchpad/s140t2/V5-L5-verify.md` §2 and
§9 (which refute the obvious next target)** — then
`docs/s140-tier1-cfg.md` §4 (why the latch is not an instrument).

---

## 0. WHERE THIS STANDS — the movement chain runs end to end

S140 Tier 2 measured, on two staged clients:

    the AI runs -> ControlInputVector written and CONSUMED every frame              [M, S138/S139]
    the whole tick early-out ladder E1..E7 is PASSED                                [M, S139]
    ControlledCharacterMove RUNS (the signed-zero proof)                            [M, S139 f3]
    Acceleration = ControlInputVector x 50000, player untreated non-zero in 0/20    [M, S139 f4]
    ULokiCMC::PerformMovement runs with a real DeltaTime (+0x12B0 at 1.002x)        [M, S139/S140]
    *** ULokiCMC::StartNewPhysics 0x055C2430 RUNS, bot AND player, ~every frame *** [M, S140 T2]
    something WRITES the bot Velocity once it holds a small non-zero value        [M, S140 T2]
      ^ QUALIFIED: both flights put that value there. Whether anything writes an
        EXACTLY-ZERO Velocity is NOT ESTABLISHED -- and a verifier found a mechanism
        by which the exactly-zero case SKIPS the write. See section 2, MOVE 2.
    Velocity == (0,0,0).  Translation 0.00 uu.  A MOVE_Falling pawn does not fall.  [M]

⚠⚠ **S139's `[M]` "StartNewPhysics has NEVER run on either component" is REFUTED.** Tier 1 showed
the `+0x16C8` latch is an invalid instrument (it reads 0 in every world, because ULokiCMC vtable
disp `0xA50` = `0x0530ABF0` clears it later in the same `PerformMovement` call); Tier 2 measured the
opposite with a **pre-poisoned payload** — poison overwritten within 250 ms on both components, and
a 2 ms burst caught the payload holding a `Velocity` sentinel **396 times in 400**.

⇒ **The question is no longer "does the physics step run". It is "WHICH SITE writes `Velocity` to
zero every frame, given a correct `Acceleration`".** ⚠ The obvious candidate — `CalcVelocity`'s input
clamp — is **[S] and the evidence leans AGAINST it**. Read §1 before planning anything.

---

## 1. TRAP: THE OBVIOUS TARGET IS PROBABLY NOT IT — READ THIS BEFORE PLANNING ANYTHING

An offline lane transcribed a complete mechanism and it is seductive. **Its own adversarial
verifier refuted the application**, and that refutation plus this session’s measurement leave a
genuine open contradiction. **Do not lead with the clamp.**

### 1.1 The mechanism (real, byte-exact; 34/34 checks reproduced by an independent instrument)

```
0x035D605B  mulss  xmm11, [rbx+0x3d0]        ; MaxSpeed *= AnalogInputModifier
0x035D607A  maxss  xmm11, xmm0               ; MaxInputSpeed = max(that, GetMinAnalogSpeed())
   ...
0x035D64F2  comisd xmm8, xmm9                ; NewMaxInputSpeed vs 1.0e-4 (.rdata 0x076B49E8)
0x035D650F  jae    0x035D6534                ; >= 1e-4 -> the normal clamp
0x035D6511  movups xmm1, [.data 0x99C86A0]   ; ZeroVector
0x035D6520  movups [rbx+0xe8], xmm1          ; Velocity.XY := 0
0x035D6527  movsd  [rbx+0xf8], xmm2          ; Velocity.Z  := 0
```

★ **The attribution is PROVEN, not asserted** (a control the lane itself never ran):
`preds(0x035D6511) = { 0x035D650F }` — **exactly one predecessor** — so the `ZeroVector` store is
**uniquely reached from the INPUT clamp**. ⚠ A second, nearly identical clamp pair exists in the same
function (the *requested* clamp, `0x035D668E comisd xmm7,xmm9` → `0x035D66A5/AC`); quoting the wrong
one changes which variable is on trial.

### 1.2 BUT IT ALMOST CERTAINLY DID NOT FIRE — [M, derived] — AND THAT LEAVES A CONTRADICTION

**[M, verifier, from bytes plus one banked measurement]:**

1. `ULokiCMC::GetMaxAcceleration 0x055AC910`, `MovementMode == 3`, routes to `0x055AC982`; the only
   non-zero exit requires `0x055AC9A0 call [rax+0xc00]` to return non-zero (`0x055AC9AC jne`). The
   fall-through is `0x055AC9AE xorps xmm0,xmm0; ret` = **0.0f**.
2. S139 flight 4 measured `Acceleration = ControlInputVector × 50000` ⇒ `GetMaxAcceleration()`
   returned **50000** on a `MOVE_Falling(3)` bot ⇒ **`[Owner_vt+0xC00]()` returned NON-ZERO**, and
   all three of `0x055AC9F0`’s zero-returning guards (`+0xF08` NULL, `0x055B18E0`, `[+0xB59]==0`)
   were passed.
3. **`GetMaxSpeed 0x055ACB90` reaches the SAME slot on the SAME object behind the SAME two guards**
   and **tail-jumps** to it (`0x055ACBE6 jmp qword [rax+0xc00]`) ⇒ **`GetMaxSpeed()` was NON-ZERO.**
4. `ComputeAnalogInputModifier` is vt disp `0x660` → `0x035DB6F0`, **not overridden by `ULokiCMC`**;
   with `|Accel| ≈ MaxAccel ≈ 50000` it returns **≈ 1.0** — and S140 Tier 2 **MEASURED it = 1** on
   the treated bot (0 on the untreated player).

⇒ `MaxInputSpeed ≫ 1e-4` ⇒ **the clamp did NOT fire.** Grade the clamp-as-explanation **[S], and
its own analysis leans against it.** The *mechanism* is [M]; only its **application** is refuted.

⚠⚠ **AND THE VERIFIER’S OWN CONCLUSION IS SUPERSEDED TOO.** It wrote *"flight 4’s null points
upstream — at the step not running"*, reasoning from S139’s then-current belief. **S140 Tier 2
measured that the step DOES run.** So the results do not all survive as stated:

> **[M] `StartNewPhysics` runs every frame. [M] `Velocity` is written to zero every frame.**
> **[M, derived] the input clamp did not fire.**
> ⇒ **EITHER (a) there is ANOTHER `Velocity`-zeroing site on this path, OR (b) one step of the
> derivation is wrong — most likely step 3, if `GetMaxSpeed` and `GetMaxAcceleration` pass
> DIFFERENT attribute selectors to the shared `+0xC00` slot.**

★ **(a) is the more likely answer, and step 3 is the weak link.** `GetMaxAcceleration` returns
**50000** while ARM G wrote `MaxAcceleration = 50000` **and** `MoveSpeed`/`MaxMoveSpeed = 500` — so
the two getters demonstrably return DIFFERENT numbers and cannot be selecting the same attribute.
If `GetMaxSpeed` selects `MoveSpeed` or `MaxMoveSpeed` it returns **500**, `MaxInputSpeed = 500`,
the clamp is dead, and (a) is what is left.

---

## 2. THE PLAN, RE-RANKED

### MOVE 1 — FREE, NO INJECTION. Stage a client and run the probe.

```powershell
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s141
python tools\re\cmc_earlyout_readout.py <PID> <BASE>
```

Gate on `[SP] done step=4` in `docs\tutorial-launch-marker.txt` **AND** a live process — never on
the stager’s own completion message.

`MinAnalogWalkSpeed @CMC+0x290` is **already wired into the probe** (S140 T2 added it) and is
**NOT OBTAINED** — the reader was written and the client died (FK-32) before it ran. It is a
**confirmation read now, not a discriminator**, and the probe prints the disjunction, not a verdict:

- **`>= 1e-4`** ⇒ the `max()` cannot fall below `1e-4` **whatever `GetMaxSpeed()` does** ⇒ the input
  clamp is **dead** and §1.2 branch (a) is the answer. **This is the expected outcome.**
- **`< 1e-4`** ⇒ the clamp still hangs on `GetMaxSpeed()` and branch (b) is live → MOVE 3.

⚠ Note the asymmetry: the untreated PLAYER has `AnalogInputModifier = 0`, so on the player the first
term is 0 regardless. **The treated bot is the informative object; the player is the control.**

### MOVE 2 — THE REAL QUESTION, AND IT IS ENTIRELY OFFLINE

**Enumerate EVERY writer of `CMC+0xE8..+0xFF` reachable from `PhysFalling`.** `Velocity` is now
*measured* to be written to zero every frame, so a writer **exists and is on this path** — this is no
longer a hypothesis to test but a site to find. Start from what the verifier established [M]:

- **`ULokiCMC::PhysFalling 0x055B89F0` calls the engine Super UNCONDITIONALLY**
  (`|reach_backward(0x055B8A2B)| = 14`, entry in R, **exit edges empty**).
  ⚠ This **REFUTES `docs/s140-tier1-cfg.md:622`.**
- **engine `PhysFalling 0x035EC850`**, 1482 instructions, `0x035EC850..0x035EE593`.
- **`CalcVelocity` is vt disp `0x7B0 = 0x035D5D20` and is NOT overridden by `ULokiCMC`**
  (547 instructions, `0x035D5D20..0x035D6786`).
- ⚠⚠ **`CalcVelocity` is called up to FOUR times per `PhysFalling`** — `0x035ECB75`, `0x035ECBD8`,
  `0x035ED549`, `0x035ED5D5` — and `NewFallVelocity` (disp `0x7A0`) **three** times (`0x035ECCEF`,
  `0x035ED617`, + one). **So "the wall is ONE compare" was wrong on the count too.**
- ★★ **A NAMED CANDIDATE SITE, from the lane-2 verifier:** in engine `PhysFalling`, a `2^-10`
  velocity gives `SizeSq = 9.5367431640625e-07` (`0x035ED9B3 call 0x035F4620`) and then
  **`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write `Velocity`** on the
  `<= 1e-3` arm. ⚠ It did **not** establish that `0x035ED98E` is reached on a given frame.
- ★★★ **AND THE STANDING NULL MAY BE A FIXED POINT.** On the below-tolerance arm of a
  `GetSafeNormal`-shaped block the three `ucomisd` at `0x055B8838/3E/4A` all fall through to
  `je 0x55B8865` and **the write is SKIPPED**. If `Velocity == 0` skips the write path, then
  zero ⇒ no write ⇒ stays zero, which is a **much simpler wall** than a routine that computes zero
  — and it predicts that a LARGE injected `Velocity` would persist and move the pawn. **That is a
  cheap, decisive follow-up arm** (⚠ and deliberately NOT the inert `2^-10`: this experiment needs
  a value ABOVE the tolerance, so it perturbs by design and must be flown as such).
- **`GetGravityZ 0x055AB8C0` (disp `0x4C0`) and `NewFallVelocity 0x055B6AD0` (disp `0x7A0`) ARE Loki
  overrides.** A `MOVE_Falling` pawn with `GravityScale 1.000` that does not fall is a standing
  unexplained phenomenon. **★ Read `GetGravityZ` FIRST** — if it returns 0, the no-fall observation
  and the zero `Velocity` may be explained together, and it is a one-function read.

★ **Everything on this path is LIT in `merged13` today** (verified S140 T2): `ULokiCMC::PhysFalling`,
engine `StartNewPhysics`, `GetMaxSpeed`, `ConstrainInputAcceleration`, `GetRecentVelocity`, the
disp-`0xA50` clear. **There is no coverage blocker — this is all offline work.**

### MOVE 3 — only if MOVE 1 reads `< 1e-4`

`GetMaxSpeed()` is reflected (vt disp `0x4C8` → `0x055ACB90`), so the S55 direct-thunk primitive
reaches it with zero writes. **Prefer reading the attribute it selects over calling it:** transcribe
`0x055AC9F0` and find which attribute the `+0xC00` slot fetches — its base value is
**`min(AttrSet+0xF0+0xC, AttrSet+0x100+0xC)`** [M]. If it reads an attribute ARM G never wrote, that
is the answer and it needs no call at all.

---
## 3. FURTHER OFFLINE TARGETS (all LIT; no coverage blocker)

Everything on this path is **LIT in `merged13` today** (verified S140 T2): `ULokiCMC::PhysFalling
0x055B89F0`, engine `StartNewPhysics 0x03600990`, `GetMaxSpeed 0x055ACB90`,
`ConstrainInputAcceleration 0x055A75B0`, `GetRecentVelocity 0x0530AC10`, the disp-`0xA50` clear.
**There is no coverage blocker — the whole downstream investigation can be done offline.**

1. **`ULokiCMC::PhysFalling 0x055B89F0`** (vt disp `0x830`). Its body opens
   `cmp byte [rcx+0x231], 7` — note **7**, because this build **inserts `MOVE_Dashing` at index 6**,
   so `MOVE_Custom == 7` and `MOVE_MAX == 8`. Any probe carrying stock UE's `MOVE_Custom == 6`
   mis-decodes by one. Transcribe it; grade every callee REAL / FOLD / DARK, and watch for the
   **sixth stub shape** (`sub rsp,0x28; call GetWorld; xor eax,eax; ret`) which grades REAL under a
   two-state test.
2. **`MaxSimulationIterations = 1`** (**[M], S140 T2 — NOT the stock default of 8**, and
   `MaxSimulationTimeStep = 0.2`, not 0.05). A one-iteration substep budget is a real constraint;
   read engine `StartNewPhysics 0x03600990..0x03600A40` in full and see what a single iteration does.
3. The engine's 8-entry jump table at `.text 0x03600BF8` bounded by `cmp esi,7`, case 3 →
   `PhysFalling`. Verify it and print all 8 targets.

---

## 4. ⚠ TRAPS — every one of these has fired in this project

1. **`CMC+0x16C8` IS NOT A LATCH.** It reads 0 in every world. Any tool or doc that reads a verdict
   off it is wrong. `cmc_earlyout_readout.py` was fixed in S140 T2; **grep the tools before trusting
   a retraction has landed.**
2. **`R1.velsnap@0x16B0 (0,0,0)` in the S139 evidence files is UNINTERPRETABLE**, not a negative —
   with `Velocity` at zero and `NewObject` zero-filling, written-with-zeros and never-written are the
   same bytes. **Pre-poison the buffer** if you need to read it again.
3. **`BsLadderStep` runs ON THE GAME THREAD.** Every `Sleep()` in it blocks the game thread and no
   frames pass. **Sample from the existing Worker thread between `FsDisarm()` and
   `BsFinalReport()`** (the `RM_DROPPLANE` B4 precedent) and carry an independent frames-are-passing
   control (`TimeSinceFallingStart @+0x12B0`, measured advancing at 1.002× real time).
4. **`hitsGT=1` is an artifact of the one-shot ladder**, not a property of the world. Control:
   `docs/fk24-s128-poolspawn-RESULT.txt` — identical flags, **hitsGT=588**.
5. **A `#else` skip message compiled into the CONTROL builds moves their digest.** Put arm code
   behind a preprocessor `#if` with **no** `#else`, and **re-digest every gate after every edit** —
   `gasattr` moved while its `.text` SIZE stayed at 137,728 bytes.
6. **`driverecompute a2a952babfed256b` IS NOT A VALID GATE** — `driverecompute` (`0xA0`) and
   `gasattr-ctrl` (`0x0A0`) are the same compile and both build to `4465ebc4d7168c03` today. Use
   `botai 5e47c13cf7f0a158` / `gasattr 2fcc2536e21f18e3` / `gasattr-ctrl 4465ebc4d7168c03`.
7. **A verdict line can lie.** Compute verdicts from observed data and print the data beside them.
8. **`set()` collapses `-0.0` and `0.0`** — record raw, derive afterwards.
9. **FK-32 budget: both S140 T2 clients died at the 4th manual-map** (T+350.5 s and T+318.0 s,
   `0x0000DEAD`, no artifact). Staging spends 3. **Capture every result as you produce it.**

---

## 5. ARTIFACTS AND TOOLS

| build | RAW `.text` | role |
|---|---|---|
| `botai` | `5e47c13cf7f0a158` | regression gate |
| `gasattr` | `2fcc2536e21f18e3` | regression gate |
| `gasattr-ctrl` | `4465ebc4d7168c03` | regression gate |
| `gasattr-sentinel` | `ce56fd715de835a1` | S140 T2 flight 1 (ARM D+F+G+H) |
| `sentinel-burst` | `62b5423febd6f779` | S140 T2 flight 2 (+ ARM H2) |
| `sentinel-nogas` | `f62d3a9cc4cf0562` | built, unflown |

`python tools/sigbypass-mod/text_digest.py <dll>...` (and `--dupes <dir>`, which flags degenerate
control arms — **run it before any A/B**).

**Probes:** `tools/re/cmc_earlyout_readout.py` (the instrument; now carries `+0x290`, `+0xC0`,
`+0x3DC/0x3E0/0x3E4`, the vptr check, raw hex of both 24-byte ranges, and the payload recogniser) ·
`scratchpad/s140t2/minanalog.py` (standalone, takes explicit CMC pointers) ·
`tools/re/movementmode_readout.py` (keep it on hand as an **instrument control** — running a
known-good probe against the same live process localised two probe defects in minutes in S139).

**Evidence from S140 T2:** `docs/s140-t2-PREREGISTERED.txt` · `-BASELINE.txt` · `-marker-armh.txt` ·
`-AFTER.txt` · `-marker-burst.txt` · `-f2-AFTER.txt` · `docs/Loki-s140t2-f1.log` ·
`docs/capture.log.s140t2-f1` · `dumps/s140-t2-startnewphysics/`.

---

## 6. SCOPE — do not overstate

⛔ **This is not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 → 0xF7EB60`) are stripped folds; nothing went through `SpawnBot`; the AI pawn's
`PlayerState`, `LokiBotController` and behaviour tree exist only because of pokes the game never
performs itself.
⛔ **ARM G is a process-wide CDO poke; ARM H writes a live component's `Velocity`. Diagnoses, not
shipping fixes.** Neither belongs in the default shim set.
⛔ **The pawn still moves 0.00 uu.** What S140 changed is that we now know the physics step *runs*
and *computes zero* — which is a different problem from the one the project thought it had.
