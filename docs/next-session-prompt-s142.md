# S142 — the mover WORKS. One pawn does not move, and it is the one with input.

**Paste this whole file as the opening prompt of a fresh session.**

⚠ **This supersedes `docs/next-session-prompt-s141-tier3.md` and `docs/next-session-prompt-s141.md`.**
Keep both as the dated record; do not work from their plans. S141 Tier 3 answered T3-A, T3-B and
T3-D, half-answered T3-C, and **moved the wall to a different pawn and a different function**.

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` (auto-loaded), then **`docs/s141-tier3-settled.md`** — its §4 and §6 govern —
then `docs/s141-t3-armk-PREREGISTERED.txt` and the raw evidence `docs/s141-t3-marker-armk.txt`.

---

## 0. WHERE THIS STANDS — three walls fell, and one moved

**[M] THE ENGINE MOVER CHAIN RUNS ON THIS CLIENT.** One 4-byte write of `GravityScale = 1.0f` and
the PLAYER hero fell **23,189 uu** from `Z = 13240` to `Z = -9935` in 10 s at terminal velocity —
having been given `Velocity = (0, 600, 0)`, i.e. **`Vz` exactly zero**. So
`TickComponent → ControlledCharacterMove → PerformMovement → StartNewPhysics → PhysFalling` all
execute, and **gravity integrates from `Velocity.Z == 0`.**
⇒ ⛔ **"`Velocity == 0` stops the mover" is DEAD. Do not re-open it.**

**[M] THE PLAYER'S NON-FALL WAS OURS.** `sp`'s LIFT-TO-SEE step
(`tutorial_launch.cpp:12877-12890`) sets `GravityScale = 0`, and `CMC+0x1A0` **is** `GravityScale`
(engine `GetGravityZ 0x035E3680 mulss xmm0,[rbx+0x1a0]`, three agreeing instruments).
`docs/s138-flight9-movement-not-simulating.md:17` had recorded BOT 1.000 / PLAYER 0.000 the day before.

**[M] THE FIXED-POINT GATE IS 2-D.** Engine `PhysFalling`'s `SizeSq2D` gate zeroes only the
gravity-space horizontal components — the store at `0x035ED9AC` is `movups`, **16 bytes over a
24-byte `FVector` of doubles**. Four independent derivations. And **[M] gravity is integrated BEFORE
that clamp on every iteration**, so the clamp can never suppress a fall.

**[M] S132's DISMOUNT WAS A `GravityScale` RESTORE**, not a velocity write — which is exactly why
that hero fell with X and Y frozen.

### ⇒ AND HERE IS THE WALL, IN ONE LINE

**The BOT is now the only thing that does not move, and it is the pawn that HAS INPUT.**

Same world, same frame, same pass, both `MOVE_Falling`, both `GravityScale 1.0`, both
`GravityDirection (0,0,-1)`, both ARM-G-treated, both identity controls passing:

| | Acceleration | Velocity written | Velocity read | moved |
|---|---|---|---|---|
| **BOT** | **\|50000\|, rotating (AI wander)** | `(0, 0, -600)` | **`(0,0,0)` at +250 ms and every sample to +10 s** | **0.000 uu ×5** |
| **PLAYER** | **(0, 0, 0)** | `(0, 600, 0)` | `(0, 18.99, -4000)` → … | **23,189 uu** |

**[M] the bot's zero is NOT self-inflicted**: `KBSPSARMS = 0x1BA0` has ARM H2 (the re-write burst,
bit 10) **OFF**, the only two `Velocity` writes are marker lines 218/219 (before the armed dump),
and the restore is line 344 — **after** all five samples (244/263/282/301/320).

---

## 1. ★ MOVE 1 — PARTLY ANSWERED BY ARM L. The clean test is ONE INJECTION, and the arm is BUILT.

**Read `docs/s141-t3-arml-result.md` first — its §2 governs.**

**[M] ARM L (2026-08-24) answered the read that ARM K missed:** `CMC+0x3D0` **is**
`AnalogInputModifier` (by-name resolve AGREES with the offset, both pawns, every sample), and on a
**walking** bot it reads **1** — so `MaxInputSpeed = GetMaxSpeed() × 1 = 500` and engine
`CalcVelocity`'s `< 1e-4` ZeroVector clamp at `0x035D6511-0x035D652F` **cannot fire.**
⇒ **§4.1 is REFUTED for a walking bot.** `MinAnalogWalkSpeed` (`+0x290`) = 0 on both, replicating
S140 T2 flight 3.

**[M] AND THE BOT WALKS, REPRODUCIBLY.** One `Velocity = (600,0,0)` from rest: fell at terminal
velocity, landed, walked at **exactly 500.0 uu/s** (three samples on the cap), 13,196 uu, steered
by its own AI. **A horizontal kick produced the fall with no Z kick at all** — the 2-D gate of §1
working in the affirmative direction. S140 T2 flight 3 is now **reproduced in a second sitting.**

⚠⚠ **BUT THE AXIS A/B STILL HAS NOT RUN, AND THE REASON IS MY ERROR.** ARM L's kick B landed on a
bot **already walking at 500 uu/s**, so it tested "vertical added to a moving body", not "vertical
from rest". The data reaches pre-registered outcome **P2**, whose written reading ("the axis is not
the variable") **does not follow**. Filed as **S141-l**. ⇒ **§4.1b is neither confirmed nor
refuted.**

### THE CLEAN TEST — do this first, it is one injection and the arm exists

**`armk_v2` RAW `988fd61853669d5c`**, archived at `dumps/s141-arms/tutorial_launch_armk_v2.dll`.
It is `armk` (vertical `(0,0,-600)` from rest) **rebuilt to include the `AnalogInputModifier` read.**

    stage -> inject armk_v2 -> read the samples
      Velocity zeroed AND AnalogInputModifier == 0  -> §4.1 CONFIRMED, and the axis matters because
                                                       a Z-only kick leaves AnalogInputModifier 0. [M]
      Velocity zeroed AND AnalogInputModifier == 1  -> §4.1 REFUTED outright; the zeroing is
                                                       something else entirely.                   [M]
      Velocity SUSTAINED (the bot walks)            -> ARM K's freeze does not reproduce; look for
                                                       what differed between SITTINGS, not kicks.  [M]

★ **And if you want the within-sitting A/B, restore the PRECONDITION**: zero `Velocity`, let it
settle for a sample, THEN apply kick B. ARM L re-latched the start *location* and not the *velocity
state*, which is the whole subject of the hypothesis.

⚠ **The cross-sitting comparison is all that currently bears on the axis**, and it is one
uncontrolled variable away from evidence:

| | ARM K | ARM L |
|---|---|---|
| kick, from rest | **vertical** | **horizontal** |
| `AnalogInputModifier` | **NOT READ** | **1** |
| result | `(0,0,0)`, moved **0.000 uu ×5** | fell, landed, walked **13,196 uu** |

### 1a. ★★ THE AXIS DISCRIMINATOR IS FOUND — and it turns MOVE 1 into a two-arm A/B

§4.1 shipped with a hole: S140 T2 flight 3 measured the **same bot**, **same treatment**, **same
acceleration**, *sustaining 500 uu/s*. `docs/s141-tier3-settled.md` **§4.1b** closes it:

**[M] engine `PhysFalling` brackets only ONE of its four `CalcVelocity` calls with
`Velocity.Z = 0` / restore** (`0x035ECBD8` is bracketed; `0x035ECB75` and `0x035ED549` are **not**,
and `0x035ED5D5`'s restore is NOT ESTABLISHED). So (i) a clamp firing on an unbracketed call leaves
`Velocity.Z` zeroed **permanently**, and (ii) **inside the bracketed call a Z-only velocity is
INVISIBLE to `IsExceedingMaxSpeed`**, which tests `SizeSquared() > MaxInputSpeed² × 1.01`:

* **flight 3, horizontal `(600,0,0)`** → `360000 > 252500` ⇒ TRUE ⇒ compared value is `|V| = 600`
  ⇒ `jae` ⇒ normal clamp ⇒ **scaled to 500. Exactly what was measured.**
* **S141, vertical `(0,0,-600)`** → the bracket zeroes Z ⇒ `SizeSq = 0` ⇒ FALSE ⇒ compared value is
  `MaxInputSpeed` ⇒ if that is `< 1e-4`, **ZeroVector, all three components.**

**Grade `[I]`** — the table is `[M]`, the composition needs `MaxInputSpeed < 1e-4`, never read.

⇒ ★★ **SO FLY MOVE 1 AS A TWO-ARM A/B ON THE AXIS, IN ONE SITTING.** Same arm, same treatment:
kick the bot **horizontally** (must sustain ~500, reproducing flight 3) and **vertically** (must
zero, reproducing S141) — two bots, or two consecutive kicks on one bot with a sample between.
**If both arms behave the same, this hypothesis is dead and so is §4.1.** Read
`AnalogInputModifier` / `[CMC+0x3D0]` / `GetMaxSpeed()` in the same pass and the whole thing closes
or dies in one flight.

⚠ **ARM L HAS SINCE READ IT (§1): `AnalogInputModifier = 1` on a walking bot, and
`CMC+0x3D0` is confirmed as that field. So the §1a composition above is REFUTED for a
walking bot -- the clamp cannot fire at 1. It survives ONLY for the unmeasured
vertical-from-rest state, which is what `armk_v2` tests.**

## 2. MOVE 2 — enumerate what else can zero all three components. Purely offline.

`docs/s141-tier3-settled.md` §4 already excludes: `ULokiCMC::PerformMovement` (**[M] ZERO writes to
`+0xE8/+0xF0/+0xF8`**), the `PhysFalling SizeSq2D` gate (2-D, and downstream of gravity), the
`Velocity.Z = 0` / restore brackets around `CalcVelocity` (`r13 == 0` at all three sites by reaching
definitions), and `ULokiCMC::PhysCustom 0x55B88E0` (mode 7 only).

There are **13 Velocity write sites in `CalcVelocity`** and **36 in engine `PhysFalling`** — both
enumerated in `scratchpad/s141/lanes/L1-physfalling-cfg.md` §2.2 and
`scratchpad/s141/lanes/L5-velocity-writers-imagewide.md` §2.4 (25 CMC-vtable writers with vtable
displacements). **Work that table against the constraint set**, which is now tight:

    must zero ALL THREE components · must fire when Acceleration != 0 · must NOT fire when
    Acceleration == 0 · must leave MovementMode 3, GravityScale 1.0 and TimeSinceFallingStart
    advancing at 1.0x · must have fired tonight and NOT in S140 T2 flight 3

## 3. MOVE 3 — T3-C's second half, which my arm could not answer

`docs/s141-tier3-settled.md` §6: **Q2 is NOT ESTABLISHED and that is a design error, not a null.**
The player's `Acceleration` read `(0,0,0)` at every sample — **it has no input driver at all** — so
its 600 → 0 decay is correct physics and cannot discriminate "the clamp still fires" from "nothing
sustains it". ARM K1 *did* land (`PLAYER storages written 3/3`).

**To answer it: give the player acceleration**, then re-read. Either drive `AddMovementInput`, or
possess it with an AI controller so the wander driver steers it. ★ And that is the same experiment as
MOVE 1's discriminator from the other side: **a player WITH input either moves (⇒ §4.1 dead) or is
zeroed like the bot (⇒ §4.1 confirmed, and it is about input, not about being a bot).**

## 4. THE KICK ROUTES ARE ANSWERED -- including the full jump chain

**[M] S141 closed T3-B's residual after lane L3 died.** The complete jump chain, zero folds:
`ACharacter::Jump() 0x3536610` (3 instructions: `or dword [char+0x580],4`, `mov dword [+0x584],0`,
`ret` -- one bit, no authority check, NOT Loki-overridden) -> `CheckJumpInput 0x3520930` ->
`CMC->DoJump()` **vtable disp 0x730** = engine `0x35DEAD0` / Loki wrapper `0x55A8110`, which writes
Velocity at `0x35DEB31`/`0x35DEB40` and calls `SetMovementMode(MOVE_Falling)`.
See `docs/s141-tier3-settled.md` §5.2 and §5.5.

### 4a. The original T3-B route
 — use it, don't re-derive it

**T3-B: `PendingLaunchVelocity` @ `CMC+0x5C8`.** Write 24 bytes; the game's own
`ULokiCMC::HandlePendingLaunch` (vtable disp `0x750`, Loki `0x55AEB60`) then sets `Velocity`, forces
`MOVE_Falling`, sets `bForceNextFloorCheck`, and **zeroes the field behind itself** — nothing to
restore, no `.text` write, no PI hook, no authority check on the path. Its call site `0x035EA160` in
engine `PerformMovement` **dominates** the `StartNewPhysics` call `0x035EB13A` (1461 → 181 reachable
with it removed). Setter is `Launch`, disp `0x748` = `0x35E7340`.
⚠ **Pending adversarial verification** (all four S141 verifiers were lost to API 529s).
Before flying it, settle: is `PendingLaunchVelocity` doubles (24 B) or floats (12 B), and what is
`[this+0xB2] & 8` in `Launch()` — if that bit is clear the setter is a silent no-op.
⚠ And note the honest limit: **tonight the bot's `Velocity` was zeroed within 250 ms however it was
set**, so on the bot this route changes the *source* of the kick, not its *survival*.

**And the vertical kick is already proven:** `GravityScale @ CMC+0x1A0 = 1.0f`, one 4-byte
readback-verified DATA write. Flown; 23,189 uu.

---

## 5. STILL NOT A BOT — keep this visible

* `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam` (`0x556DE53 → 0xF7EB60`) are
  stripped folds; nothing went through `SpawnBot`; the pawn has no hero class and no team.
* `LivingState` still has no native writer that sets Alive — ARM F pokes it.
* `ALokiBotController::Tick`'s only motion driver is a **random wander**: no targeting, no ability
  use, no combat.
* ARM G mutates a **CDO default subobject**, process-wide, never undone. **T3-D scoped a
  per-instance replacement (`scratchpad/s141/lanes/L6-gas-per-instance.md` §B) but did NOT build
  it.** Its value is removing the permanent mutation, not changing the physics.
* **None of these arms belongs in the default shim set.**

---

## 6. FLIGHT PROCEDURE AND BUDGET

```bash
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s142
```
Staged on **attempt 1** last time. Gate on **`[SP] done step=4` AND a live process** — never on the
stager's completion message. Then `tools\inject\inject.exe mmap <pid> <dll>`, wait for **`[BS] done`**,
then read externally.

⚠⚠ **FK-32 IS NOW FULLY PREDICTABLE: `0xDEAD` at 7 / 6 / 4 / 4 / 4 / 4 / 4 injections
(1144 / 334 / 350 / 318 / 320 / ~300 s).** Staging spends 3. **YOU GET ONE INJECTION.**
★ **Take the `dumpimage` EARLY, not last** — S141 left it until after the samples and the client had
already gone. That is the one artifact S141 lost.
★ **Capture as you go.** Copy the marker off after every phase; that is the only reason nothing else
was lost across the last four flights.

**Regression gates** (`python tools/sigbypass-mod/text_digest.py`, RAW recipe):
`botai 5e47c13cf7f0a158` · `gasattr 2fcc2536e21f18e3` · `gasattr-ctrl 4465ebc4d7168c03`.
**S141 arms** (archived `dumps/s141-arms/`): `armk` RAW **`8278c6031d05756c`** (FLOWN) ·
`armk-ctrl` RAW **`3f7323f6f4ba3e57`** (built, unflown, verified DISTINCT).
⚠⚠ **`sentinel-big 52fceb9be6de532f` and the other `sentinel-*` / `gasattr-sentinel` digests have
MOVED** — S141's new free reads live inside `#if (KBSPSARMS & 0x200)`. **Re-digest before reusing
any of them as a gate or a control.**

---

## 7. ⚠ TRAPS — all fired in S140 or S141

1. **`CMC+0x16C8` IS NOT A LATCH.** It reads 0 in every world. Any verdict drawn from it is void.
2. **A displacement scanner must be controlled on sites you already know, in the same run.** S141's
   first one had two off-by-ones and a premature `break`, and reported a clean-looking
   "2 writes, 0 reads" that was wrong. It was caught **only** because a known site came back MISSED.
3. **A marker line can name a value it does not write.** `[SNP] BOT sentinel Velocity = (2^-10,0,0)`
   was hardcoded while the arm wrote `(0,0,-600)`. Fixed, but assume others exist: **read the RAW
   dump, not the announcement.**
4. **`+0x12B0 TimeSinceFallingStart` can NEVER be a `PhysFalling` receipt** — [M] neither
   `PhysFalling` ever calls `StartNewPhysics` (vtable disp `0x720` absent from both call sets), so its
   substep writer is unreachable and a 1.0× advance is expected either way.
5. **"StartNewPhysics runs" ≠ "the physics step runs."** The payload write at `0x055C244F` is in the
   Loki wrapper's prologue, upstream of `jmp 0x3600990`; the engine has four further early-outs.
6. **The player is a CONTAMINATED control on `CMC+0xE8`/`+0x328` whenever `play` is injected**
   (`tutorial_launch.cpp:3047`, `:12599` write both every game-thread hit).
7. **`MOVE_Custom == 7` on this build** — `MOVE_Dashing` is inserted at 6. Stock tables are off by one.
8. **Do not cross a function boundary with an inference.** S139 and S141 both did, in opposite
   directions.
9. **A census that returns all-negative is far more likely a broken instrument than a discovery.**
10. **Classify writes from `operands[0].type == MEM`, never from capstone `regs_access`** — it
    reports `movups` stores as reads.

---

## 8. WHAT S141 COULD NOT GET

* ⚠⚠ **ALL adversarial verification was lost to API `529 Overloaded`** — 7 of 12 agents in the main
  workflow (every verifier + the adjudicator) and then 4 of 4 in a focused retry. The five lane
  analyses that landed are **un-refuted except where they independently converge** — which they do,
  4-ways, on T3-A and the gate constant. ★ Partial recovery: the dead L1 verifier's own scripts
  (`scratchpad/s141/verify/V1/`) were re-run and **confirmed §1, §3 and §4.1's attribution from
  independently written code**, and produced the new gravity-before-clamp ordering fact
  (`vdom2.py`). **Anything marked "pending verification" in `docs/s141-tier3-settled.md` has had
  exactly one derivation — treat it as `[I]`.** Re-running those four verifiers is cheap and is
  worth doing first if the API is healthy.
* **`AnalogInputModifier` was not read** (S141-d). MOVE 1.
* **T3-C's sustaining half** (§6). MOVE 3.
* **The S140-flight-3 discriminator** for §4.1. The most important open question.
* **No `dumpimage`** of the armed client — attempted after the samples, client already gone.
* **T3-D was scoped, not built** — deliberately, so it could not confound the flight.
