# S141 — `StartNewPhysics` RUNS. The wall is `CalcVelocity`, and the first move is ONE READ-ONLY RPM RUN.

**Paste this whole file as the opening prompt of a fresh session.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first (auto-loaded; current as of this commit), then
**`docs/s140-tier2-sentinel.md` — its §5 is this session's brief** — then
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
    *** Velocity is ACTIVELY COMPUTED AND WRITTEN TO ZERO every frame ***           [M, S140 T2]
    Velocity == (0,0,0).  Translation 0.00 uu.  A MOVE_Falling pawn does not fall.  [M]

⚠⚠ **S139's `[M]` "StartNewPhysics has NEVER run on either component" is REFUTED.** Tier 1 showed
the `+0x16C8` latch is an invalid instrument (it reads 0 in every world, because ULokiCMC vtable
disp `0xA50` = `0x0530ABF0` clears it later in the same `PerformMovement` call); Tier 2 measured the
opposite with a **pre-poisoned payload** — poison overwritten within 250 ms on both components, and
a 2 ms burst caught the payload holding a `Velocity` sentinel **396 times in 400**.

⇒ **The question is no longer "does the physics step run". It is "why does `CalcVelocity` produce
zero from a correct `Acceleration`".**

---

## 1. THE TARGET — one compare, three inputs, two of them never read

An offline lane transcribed the mechanism [I, strong — the bytes are read, the live inputs are not]:

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
instructions earlier. That is a complete mechanical account of everything measured since S139 f4.

| term | address | status going into S141 |
|---|---|---|
| `AnalogInputModifier` | `CMC+0x3D0` | **[M] = 1 on the ARM-G-treated bot** (0 on the untreated player; **0 on both in S139 f1, i.e. BEFORE ARM G**). **NOT the zero.** |
| `GetMaxSpeed()` | vt disp `0x4C8` → `0x055ACB90` | **GAS-backed** — tail-jumps to `[Owner_vt+0xC00]`, which returns `0.0f` when `Character+0xF08 AttributeSetStorage == NULL` (`0x055ACB73 xorps xmm0,xmm0; ret`). ARM G fills that storage and writes `MoveSpeed`/`MaxMoveSpeed = 500`. **NEVER READ LIVE.** |
| `GetMinAnalogSpeed()` | vt disp `0x7C8` → `0x035E3D20`, **not overridden** | returns **`MinAnalogWalkSpeed @CMC+0x290`** for `MovementMode ∈ {1,2,3}`, and both pawns are **`MOVE_Falling(3)`, which is in that set**. **NEVER READ LIVE.** |

---

## 2. ★ MOVE 1 — FREE, NO INJECTION, AND IT MAY SETTLE THE WHOLE THING

`CMC+0x290` is **already wired into `tools/re/cmc_earlyout_readout.py`** (S140 T2 added it). Stage a
client and run the probe. That is the entire first experiment.

```powershell
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s141
# gate on '[SP] done step=4' in docs\tutorial-launch-marker.txt AND a live process
python tools\re\cmc_earlyout_readout.py <PID> <BASE>
```

**PRE-REGISTERED DISJUNCTION — the probe prints it, do not improve on it after the fact:**

- **`MinAnalogWalkSpeed >= 1e-4`** ⇒ the `max()` **cannot** fall below `1e-4`, so **this clamp is NOT
  what zeroes `Velocity`** and the lane's headline is **REFUTED**. Go to §3.
- **`MinAnalogWalkSpeed < 1e-4`** ⇒ the clamp fires iff `GetMaxSpeed() * AnalogInputModifier` is also
  `< 1e-4`. With `AnalogInputModifier = 1` measured on a treated bot, **the whole question reduces to
  what `GetMaxSpeed()` returns**, which needs §2.1.

⚠ Note the asymmetry: **the untreated PLAYER has `AnalogInputModifier = 0`**, so on the player the
first term is 0 regardless and only `MinAnalogWalkSpeed` can save it. The bot is the informative
object here; the player is the control.

### 2.1 If `GetMaxSpeed()` is needed

It is **reflected** (`ULokiCMC` vt disp `0x4C8` → `0x055ACB90`), so the **S55 direct-thunk primitive
reaches it with zero writes**. Two routes, in order of preference:

1. **Read the attribute the getter selects.** ARM G wrote `MoveSpeed` and `MaxMoveSpeed = 500` into
   the CDO's default `AttributeSet` subobject at `FGameplayAttributeData +0x8` **and** `+0xC`.
   Transcribe `[Owner_vt+0xC00]` offline first and find out **which attribute it reads** — if it
   reads a third attribute ARM G never wrote, that is the answer and it needs no call at all.
2. Call `GetMaxSpeed()` through the thunk on the treated bot and on the untreated player.
   Pre-register: treated returns **500**, untreated returns **0.0f**. **A treated bot returning 0 is
   the interesting outcome** — it would mean the GAS port does not reach this getter.

---

## 3. IF THE CLAMP IS REFUTED — the ranked alternatives

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
