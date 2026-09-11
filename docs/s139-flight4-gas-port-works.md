# S139 flight 4 — the GAS port WORKS. `Acceleration = input × 50000`. And the walls are TWO, not one.

> ## ⚠⚠⚠ PARTIALLY SUPERSEDED — READ THIS FIRST (banner added S142, 2026-08-24)
>
> **WHAT STILL STANDS:** **the headline: `Acceleration = ControlInputVector × 50000`** (ratio mean 49999.63 over 40 components) with its **perfect within-run specificity control** — the untreated player non-zero in 0 of 20 samples. The GAS attribute port works and the input wall is closed. That result is untouched.
>
> **WHAT IS DEAD:** every claim resting on `CMC+0x16C8`. **[M] that byte is NOT a latch.** `ULokiCMC`
> vtable disp `0xA50` = `0x0530ABF0` clears it, and engine `PerformMovement` calls that slot at
> `0x035EB569` — later in the same call, on a path the `StartNewPhysics` call site **dominates**. So
> it reads `0` whether the physics step runs every frame or never runs at all. It is a per-frame
> `TOptional<FVector>` validity flag over the `+0x16B0` Velocity snapshot, named from its own consumer
> `GetRecentVelocity` (`.data 0x09BC9AD0` → impl `0x0530AC10`). Those claims are **UNGRADED, not
> negative.** Read `docs/s140-tier1-cfg.md` §4.
>
> ⚠ **The MEASUREMENT was correct** — `+0x16C8` really did read `0`. Only the **inference** is dead.
> Nothing here misread a byte.
>
> **AND THE UNDERLYING QUESTION IS ANSWERED THE OTHER WAY NOW.** The engine mover chain runs on this
> client: `GravityScale = 1.0f` made the player fall 23,189 uu, and one `Velocity = (600,0,0)` kick
> made the bot fall, land and walk **13,196 uu at 500.0 uu/s**, reproduced in a second sitting. The
> remaining wall is narrower: the bot does not escape `Velocity == 0` on a *Z-only* kick, and the
> discriminator is the kick axis. See `docs/next-session-prompt-s142.md` and
> `docs/s141-tier3-settled.md`.

Written 2026-08-23. Pre-registration: `docs/s139-f4-PREREGISTERED.txt` (UNEDITED, written before
staging finished). Client PID 36844, staged on **attempt 1**, one injection.
Arm: `tutorial_launch_gasattr.dll` RAW **`2fcc2536e21f18e3`**.
Predecessor: `docs/s139-flight3-controlledcharactermove-runs.md`.

---

## 0. HEADLINE

**Porting the DS route's GAS recipe onto the bot turned `GetMaxAcceleration()` from 0 into 50000,
and the input path now produces a real acceleration vector — while the untreated player's stays
exactly zero.** ~~The physics step still never runs, so~~ ⚠ **(S142: that clause is void — the latch
cannot support it.)** **The input wall and the movement wall are nonetheless TWO separate problems**,
which is the branch the pre-registration deliberately refused to predict — and that conclusion
SURVIVES, on the independent observations that `Velocity` stayed `(0,0,0)` and the pawn moved
**0.00 uu** while `Acceleration` was correct.

| # | prediction | outcome |
|---|---|---|
| **P1** | ARM G writes 3/3 storages and 6/6 attributes, all readback-verified | **HELD** |
| **P2** | the BOT's `Acceleration` becomes non-zero and collinear with `ControlInputVector` | **HELD — 20/20 samples** |
| **P3** | the UNTREATED player's `Acceleration` stays a signed zero (specificity) | **HELD — 0/20 non-zero** |
| **P4** | latch `+0x16C8` → 1 (one problem) **or** stays 0 (two problems) — *deliberately not predicted* | ⚠⚠ **VOID (S142): the latch reads 0 in BOTH branches, so P4 could only ever land on "stays 0". A pre-registered disjunction whose two arms are not distinguishable by the instrument is not a test.** The two-wall conclusion happens to be right for other reasons |
| **P5** | if the latch flips, the bot should fall | not reached (latch did not flip) |

---

## 1. ★★★★★ THE MEASUREMENT

    [GASX] CDO = 0x20D0C96FB00 (using its DEFAULT SUBOBJECTS -- deliberately NOT spawning)
    [GASX]   src AbilitySystemComponent @0x3E8 = 0x20D0C96FF10 (LokiAbilitySystemComponent)
    [GASX]   src AttributeSet           @0x3F0 = 0x20D0C971710 (LokiAttributeSet)
    [GASX]   src AttributeSetHealth     @0x3F8 = 0x20D0C971F20 (LokiAttributeSetHealth)
    [GASX]   dst AbilitySystemComponentStorage @0xF00  0 -> 20D0C96FF10  OK
    [GASX]   dst AttributeSetStorage           @0xF08  0 -> 20D0C971710  OK
    [GASX]   dst AttributeSetHealthStorage     @0xF10  0 -> 20D0C971F20  OK
    [GASX]   attr MoveSpeed                  @+0xF0  = 500    readback 500    OK
    [GASX]   attr MaxMoveSpeed               @+0x100 = 500    readback 500    OK
    [GASX]   attr MaxAcceleration            @+0x120 = 50000  readback 50000  OK
    [GASX]   attr GroundFriction             @+0x130 = 8      readback 8      OK
    [GASX]   attr BrakingDecelerationWalking @+0x140 = 2048   readback 2048   OK
    [GASX]   attr Mass                       @+0x170 = 100    readback 100    OK
    [GASX] ARM G done: storages written 3/3, attributes written 6/6

Then, live, over 20 samples:

    t       | BOT ControlInputVector      BOT Acceleration              latch | PLAYER Acceleration  latch
    + 0.0s  | (-0.7284,  0.6852)          (-36417.504,  34260.260)       0    | (0.000, 0.000)        0
    + 1.0s  | (-0.7831, -0.6219)          (-39154.264, -31095.717)       0    | (0.000, 0.000)        0
    + 3.0s  | (-0.3346, -0.9423)          (-16732.100, -47117.267)       0    | (0.000, 0.000)        0
    + 7.0s  | (-0.9523,  0.3051)          (-47616.413,  15253.761)       0    | (0.000, 0.000)        0
    +15.0s  | (-0.1596,  0.9872)          ( -7981.009,  49358.925)       0    | (0.000, 0.000)        0

**`Acceleration / ControlInputVector` over all 40 components: min 49991.15, max 50006.32,
mean 49999.63.** (The ±0.01 % spread is the 4-decimal printing of the input, nothing else.)

⇒ ★★★ **`Acceleration = ControlInputVector × 50000` — i.e.
`ScaleInputAcceleration = GetMaxAcceleration() * input`, with the getter now returning exactly the
`MaxAcceleration` ARM G wrote into the borrowed attribute set.** The input path is fixed, and the
number it produces is the number we supplied.

★★ **THE SPECIFICITY CONTROL IS PERFECT AND IT IS WITHIN-RUN.** The player hero was deliberately
left untreated — `+0xF08` still **NULL** on it — and its `Acceleration` read exactly `0` in **0 of
20** samples non-zero, in the same process, in the same pass, sampled by the same code. Bot treated,
player untreated, one field changed, one side moved.

---

## 2. ⇒ THE WALLS ARE TWO, AND THIS FLIGHT SEPARATED THEM

| | status |
|---|---|
| **input → acceleration** | ★ **FIXED.** `GetMaxAcceleration()` 0 → 50000; `Acceleration` is real and tracks the AI's wander direction. |
| **acceleration → velocity → displacement** | ⛔ **UNTOUCHED** — but ⚠ **for the record (S142): the latch clause is void**; `Velocity` staying `(0,0,0)` and the pawn moving **0.00 uu** are the real, surviving observations. Both were later explained: a *horizontal* kick makes this bot fall, land and walk 13,196 uu. |

This is P4's second branch, written down in advance precisely so it could not be reinterpreted
afterwards. **A zero acceleration was never able to explain the absent GRAVITY, and now that
acceleration is non-zero, the absence is unchanged.**

⚠⚠ **AND THE PHYSICS-STEP CONTRADICTION IS NOW SHARPER, NOT SOFTER.** `Acceleration` being written
every frame *proves* `ControlledCharacterMove` runs; `ControlledCharacterMove` calls
`PerformMovement` at `0x035DCDAC` whenever `Role == ROLE_Authority` (measured **3**); and engine
`PerformMovement`'s six exits all have their inputs measured passing (flights 1–2). ~~Yet
`StartNewPhysics` is never entered. **Something in that function bails for a reason none of the six
named gates accounts for.**~~
⚠⚠⚠ **REFUTED (S142). Nothing bails.** The six exits are complete and exact (four independent CFGs;
0 indirect jumps, 0 coverage gaps, 2 backward edges and neither reaching the call), and
"`StartNewPhysics` is never entered" was never measured — the latch reads `0` regardless. **The
premise of this paragraph does not exist.**

⚠ **NOT OBTAINED:** a re-read of the six gate inputs on the bot *after* ARM G. The client died
mid-probe and the script threw rather than printing partial values. Nothing suggests they changed —
ARM G writes GAS storages and attribute floats, none of which is a gate input — but it is unread.

---

## 3. ARM G — what it is, and its scope

`tools/sigbypass-mod/tutorial_launch.cpp`, `BsPsGasAttrs()`, `KBSPSARMS` bit 8 (`0x100`).
Builds: **`gasattr`** RAW `2fcc2536e21f18e3` · **`gasattr-ctrl`** RAW `4465ebc4d7168c03`
(ARM G compiled out; **verified DISTINCT**, so it is not an A/B against a copy of itself).
**Regression gate `botai` RAW `5e47c13cf7f0a158` — UNCHANGED**, as is `driverecompute`
`a2a952babfed256b`; every edit sits behind the arm bit.

It is a direct port of `ds_hybrid.cpp:2370-2430`, and it keeps that code's hard-won warnings:
- ⛔ **it does NOT spawn `LokiPlayerState_HeroAffiliated`** — S80 live-proved an instant client
  crash. It borrows the CDO's already-constructed default subobjects.
- ⚠⚠ **it writes the WHOLE block**, because `ds_hybrid.cpp` records from experience that wiring
  `AttributeSetStorage` makes the Loki CMC read *every* movement value from attributes, so a set
  with only `MoveSpeed` yields `MaxAcceleration = 0` and still no movement.
- ⚠ **SCOPE: the attribute values live in a CDO default subobject** — process-wide, for the process
  lifetime, not undone. **A diagnosis, not a shipping fix.** Do not add it to the default set.
- Risk class **DATA**: three aligned pointer stores on the pawn plus float pairs inside an existing
  allocation. No module-image write, no PI hook, no `SpawnActor`.

★ **`tutorial_launch`'s own `KWIREGAS` deliberately writes only `+0xF00`**
(`tutorial_launch.cpp:11899` says so in as many words), which is exactly the gap this arm fills —
and every staged marker in this project has been printing `AttributeSetStorage @0xF08 = 0x0 (NULL)`
the whole time.

---

## 4. ★ THE METHOD NOTE

The recipe was **already in this repo, live-proven, and never ported.**
`docs/coverage-audit-s101.md:283` recorded it ≈38 sessions ago — `GetMaxSpeed()` 0 → 500,
`GetMaxAcceleration()` 0 → 50000, hero translating via the stock engine chain — and `:630` ranked
porting it *"Single highest-value experiment available."* Method rule #2: **read the shipped
artifacts first**, and that includes this repo's own docs and sibling shims.

⚠ One honest qualifier on the old claim: the DS route reported the hero **translating**. Here the
identical recipe produced acceleration but **no translation**, because the physics step is blocked
by something the DS route did not have. **Do not read `coverage-audit-s101.md:283` as promising
movement on the force-open route.**

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `docs/s139-f4-PREREGISTERED.txt` | P1–P5 incl. the deliberately-unpredicted P4, unmodified |
| **`docs/s139-f4-accel.txt`** | **the 20 samples: bot treated vs player untreated** |
| `docs/s139-f4-marker.txt` | ARM D/F/G receipts (3/3 storages, 6/6 attributes) |
| `tools/sigbypass-mod/tutorial_launch.cpp` | `BsPsGasAttrs()` — ARM G |

## 6. NEXT

The input wall is closed. **The whole remaining question is the physics step**, and it is now
isolated with everything upstream of it proven working:

1. **Why does engine `PerformMovement` not reach `StartNewPhysics`** when it is provably called and
   all six enumerated exits have passing inputs? A CFG walk gave the six; one of them must be
   measuring something other than what it tests, or a seventh path exists that the walk's
   `target > call` predicate cannot see (⚠ that predicate is blind to **backward** bails).
2. **Pin `LogCharacterMovement=Log`** in the user `Engine.ini` — engine `StartNewPhysics` logs
   *"UpdateComponent (%s) is simulating physics - aborting."* and the category is currently silent
   with **no positive control**, so its absence proves nothing.
3. Re-read the six gate inputs on a treated bot (not obtained here).

⛔ Unchanged: **not a bot.** `ServerSetHeroClass` / `SetPlayerTeam` are still stripped folds, and
none of this happens without pokes the game never performs itself.
