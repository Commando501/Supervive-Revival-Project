# S139 flight 3 — the input path RUNS, and the wall is `GetMaxAcceleration() == 0`

Written 2026-08-23. Pre-registration: `docs/s139-f3-PREREGISTERED.txt` (UNEDITED).
Read-only RPM; one injection (`driverecompute`) into the already-staged flight-2 client, PID 35608.
Predecessors: `docs/s139-flight2-gate-refuted.md`, `docs/s139-flight1-the-bot-is-not-special.md`.

---

## 0. HEADLINE

**`ControlledCharacterMove` RUNS. The whole tick early-out ladder is passed. S2 is REFUTED — and the
proof is a SIGNED ZERO.**

    t        ControlInputVector +0x418         Acceleration +0x328
    + 0.0s   ( 0.4224, -0.9064, 0)             ( 0.0000, -0.0000, 0)
    + 1.0s   (-0.9650,  0.2622, 0)             (-0.0000,  0.0000, 0)
    + 3.0s   (-0.2485, -0.9686, 0)             (-0.0000, -0.0000, 0)
    + 7.0s   ( 0.8681,  0.4964, 0)             ( 0.0000,  0.0000, 0)
    + 9.0s   ( 0.7665, -0.6423, 0)             ( 0.0000, -0.0000, 0)
    +17.0s   ( 0.8637, -0.5041, 0)             ( 0.0000, -0.0000, 0)

**`Acceleration`'s SIGN tracks `ControlInputVector`'s sign in 22 of 22 samples — 44 sign bits, all
agreeing.** A field that is never written is `+0.0` and prints `0.0000` forever; it **cannot** track
the sign of a churning input. ⇒ `Acceleration` was **computed from** `ControlInputVector` and
multiplied by ~0 — i.e.

    0x035DCD5F  call [rbx+0xA40]          ScaleInputAcceleration = GetMaxAcceleration() * input
    0x035DCD6B  movups [rsi+0x328], xmm0  <- this store HAPPENED, every frame

⇒ ★★★★★ **The wall on the input path is `GetMaxAcceleration()` returning 0.**

---

## 1. WHY THE BOT WAS REQUIRED, AND WHAT IT EXCLUDED

`Acceleration == 0` is normally three-way ambiguous. The pre-registration named all three and said
which the bot kills:

| arm | mechanism | status |
|---|---|---|
| (a) `ControlledCharacterMove` never ran | the tick ladder bails (S2) | **REFUTED** — a never-written field cannot carry the input's sign |
| (b) `ULokiCMC::ConstrainInputAcceleration 0x055A75B0` wrote literal `ZeroVector` on its `IsStunned` arm | needs `IsStunned` true | **UNREACHABLE BY CONSTRUCTION** — `IsStunned 0x055B2930`'s first guard is *NULL ASC → return false*, and the bot's `AbilitySystemComponentStorage +0xF00` reads **NULL** (P2 held). ⚠ This is exactly why the test needed the BOT: the player's `+0xF00` is non-null (KWIREGAS wires only the player's), so arm (b) is live there and the same read would prove nothing. |
| (c) `GetMaxAcceleration()` returns 0 | GAS-backed getter, `AttributeSetStorage +0xF08` **NULL** | **THE SURVIVOR** |

Prediction scorecard: **P1 held** (both identity controls PASS) · **P2 held** (`+0xF00` NULL) ·
**P3 held** (12 distinct `ControlInputVector` values in 22 samples) · **P4 resolved** to the
signed-zero arm, which the pre-registration did not anticipate and which is *stronger* than either
branch it wrote down.

---

## 2. ⚠⚠ MY OWN VERDICT LINE GOT IT WRONG — READ THE SAMPLES, NOT THE VERDICT

The probe printed **`distinct Acceleration values: 1`** and concluded "bit-frozen at (0,0,0)".
**That count is an artifact:** Python hashes `-0.0 == 0.0`, so a `set()` of the tuples collapses
signed zeros onto one entry. The *printed samples* showed the sign structure the *set* destroyed.

★ This is the S138 lesson recurring verbatim — *"a verdict line can lie; read the samples"* — and it
is the second time this session that **deriving before recording** hid the answer (the first was
`rootset_census.py`'s derived-boolean defect quoted in CLAUDE.md). **Record raw; derive afterwards.**

⚠ **NOT OBTAINED:** the bit-level re-confirm (are they exactly `0x8000000000000000` / `0x0`, or
merely tiny magnitudes?). **The client died before it ran** — the probe reported `0/0` samples and
correctly refused to print the conclusion. It does not change the inference: signed zero and a tiny
signed magnitude *both* require the store to have executed with the input as a factor. **Re-run it
first thing next sitting** (`docs/s139-f3-signedzero.txt` is the harness, and it self-voids on a
dead client).

---

## 3. ★★★★★ THE FIX ALREADY EXISTS IN THIS REPO, LIVE-PROVEN, AND WAS NEVER PORTED

`docs/coverage-audit-s101.md:283` — written ~38 sessions ago:

> the DS route **already solved this**, and nobody has ported it. Commits `349c250 / 0f9ac7b /
> 5b13f81 / 6a7bbda` … solved the problem *without* the carrier by borrowing the CDO's default
> subobjects into the hero's three storage slots (`+0xF00/+0xF08/+0xF10`) and writing the attribute
> block directly. That code is live in `ds_hybrid.cpp:2370-2430` … and it was **live-proven**:
> **`GetMaxSpeed()` 0 → 500, `GetMaxAcceleration()` 0 → 50000, and the hero physically translated
> through the world via the stock engine chain** (`AddMovementInput → ControlInputVector → CMC →
> CalcVelocity`).

and `:630` ranks porting it **"Single highest-value experiment available"**.

★ **That is the exact chain this flight just measured stuck**, and the exact getter this flight just
named. **It is a textbook method-rule-#2 instance: the answer was in the repo's own docs and a
sibling shim's source.**

**The recipe** (`ds_hybrid.cpp:2370-2430`), with its own hard-won warnings:
- ⛔ **DO NOT SPAWN `LokiPlayerState_HeroAffiliated`** — S80 live-proved it crashes the client
  instantly. Use `Default__LokiPlayerState_HeroAffiliated`'s **default subobjects**, which already
  exist fully constructed.
- Borrow its `AbilitySystemComponent@+0x3E8` / `AttributeSet@+0x3F0` / `AttributeSetHealth@+0x3F8`
  into the hero's `+0xF00` / `+0xF08` / `+0xF10`.
- ⚠⚠ **A PARTIAL PORT FAILS, and the source says so from experience:** *"Wiring AttributeSetStorage
  makes the Loki CMC read EVERY movement value from attributes instead of its base UPROPERTYs — so a
  set with only MoveSpeed filled in gives MaxAcceleration=0 ⇒ Acceleration = 0*input = 0 ⇒ still no
  movement (observed)."* Write the **whole block**: `MoveSpeed`, `MaxMoveSpeed`, `MaxAcceleration`
  (50000), `GroundFriction` (8), `BrakingDecelerationWalking` (2048), `Mass` (100), each at
  `FGameplayAttributeData` `+0x8` BaseValue **and** `+0xC` CurrentValue.
- ⚠ **SCOPE:** this writes into a **CDO's default subobject**, so every hero borrowing it shares one
  attribute set, process-wide. A diagnosis, not a shipping fix.
- ★ `tutorial_launch`'s own `KWIREGAS` **deliberately writes only `+0xF00`** — the source says so at
  `tutorial_launch.cpp:11899` (*"Deliberately writes ONLY the ASC cache, not AttributeSetStorage/
  AttributeSetHealthStorage"*). That is precisely the gap, and every staged run's marker has been
  printing `[GAS] AFTER AttributeSetStorage @0xF08 = 0x0 (NULL)` the whole time.

---

## 4. ⚠ WHAT THIS DOES **NOT** EXPLAIN — the residual, stated plainly

**`StartNewPhysics` still never runs** (`latch +0x16C8 == 0` on the bot here, and on all 37
components in flight 2), and **a zero `Acceleration` does not stop gravity.** So:

- The **input** wall is now named and has a known fix (§3).
- The **gravity / physics-step** wall is **still unexplained**. `ControlledCharacterMove` runs and
  calls `PerformMovement` at `0x035DCDAC`; Loki's `PerformMovement` reaches its Super
  unconditionally; and yet the latch says `ULokiCMC::StartNewPhysics` was never entered.

⚠ **Do not assume porting the GAS fix also fixes this.** It may — the DS route reportedly moved the
hero via the stock chain with exactly this fix — or the two may be independent. **Fly the port and
read the latch in the same pass**; that settles it in one sitting.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `docs/s139-f3-PREREGISTERED.txt` | P1–P5 and the three-arm ambiguity, written before the injection |
| **`docs/s139-f3-accel.txt`** | **the 22 samples — the signed-zero evidence** |
| `docs/s139-f3-signedzero.txt` | the bit-level harness; **NOT OBTAINED**, client died, self-voided |
| `docs/s139-f3-marker-pre.txt` | pre-injection marker |

Client PID 35608 died after the samples (3rd injection into that process, FK-32 class).
`WeldParent` was read from it first: **`capsule+0x5F0 = NULL`**, which refutes the weld hypothesis
and confirms `BodyInstance @+0x3F0` from `GetBodyInstance`'s own `lea rax,[rcx+0x3f0]`.
