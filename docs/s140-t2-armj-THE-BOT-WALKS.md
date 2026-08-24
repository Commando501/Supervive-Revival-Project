# S140 TIER 2, FLIGHT 3 — **THE BOT FALLS, LANDS, AND WALKS AT EXACTLY ITS CONFIGURED SPEED.**

**2026-08-23. One staged client, one injection. ARM J, `sentinel-big 52fceb9be6de532f`, PID 64680.**
Pre-registration: **`docs/s140-t2-armj-PREREGISTERED.txt`**, committed at `888386a` **before** the
injection and unedited since. Evidence: `docs/s140-t2-marker-armj.txt` ·
`docs/s140-t2-f3-AFTER.txt` · `dumps/s140-t2-walking/`.

---

## HEADLINE

> **[M] PRE-REGISTERED OUTCOME A, ON THE BOT.** One write of `Velocity = (600, 0, 0)` — **once, never
> re-written** — and the AI-controlled hero **fell under gravity at terminal velocity, landed on the
> tutorial floor at `Z = 90.150`, and then moved horizontally with its speed CAPPED at exactly
> `500.0 uu/s` (two of three ground samples sit on the cap) and its direction changing between them.**
>
> **`sqrt(233.334² + 442.216²) = 500.0` — EXACTLY the `MoveSpeed` / `MaxMoveSpeed` ARM G wrote.**
> It travelled **13,187 uu** and later walked off the island edge under its own AI.
>
> ⇒ **THE MOVEMENT CHAIN IS COMPLETE AND IT WORKS.** Gravity, landing, ground movement, speed
> clamping to the GAS attribute, and AI steering all function. **The wall was never in the mover.**
>
> ⇒ **THE STANDING NULL IS A FIXED POINT** — `Velocity == 0` ⇒ nothing engages ⇒ stays 0. One kick
> off zero and the entire system runs. **That is a completely different and far smaller problem than
> "the physics does not work", which is what this project has believed since S138.**

---

## 1. THE TRAJECTORY — raw, per sample

`Velocity` written ONCE at t=0. The sampler never re-writes it.

| t | BOT `Velocity` | BOT location | moved | `TimeSinceFallingStart` |
|---|---|---|---|---|
| arm | `(600, 0, 0)` *(written)* | `(600, 0, 13240)` | 0 | 0.0000 |
| +250 ms | `(34.039, 0, **-4000**)` | `(1560.235, 0, **3348.922**)` | 9,937.6 uu | 3.8000 |
| +750 ms | `(22.759, 0, **-4000**)` | `(1574.061, 0, **1348.809**)` | 11,931.0 uu | 4.3334 |
| +2 s | `(-240.132, -438.562, 0)` | `(1356.434, -409.393, **90.150**)` | 13,177.9 uu | 5.5667 |
| +5 s | `(-137.500, 351.364, 0)` | `(872.694, 277.616, **90.150**)` | 13,155.6 uu | 8.6001 |
| +10 s | `(-233.334, 442.216, 0)` | `(819.725, 964.733, **90.150**)` | 13,187.0 uu | **1.5357** |

**Read it line by line — every row is a distinct physical event:**

1. **It fell.** `Z` went `13240 → 3349 → 1349` with `Velocity.Z` pinned at **`-4000`** — a terminal
   velocity, i.e. gravity integrated and then clamped. A `MOVE_Falling` pawn with `GravityScale
   1.000` that "does not fall" has been a standing unexplained phenomenon since S138. **It falls.**
2. **It landed.** `Z = 90.150` from +2 s onward — **the exact ground-rest Z this repo already
   recorded for a hero standing on the tutorial floor** (S132 measured a dismounted hero settling to
   `Z = 90.15` and holding it bit-for-bit). Independent, pre-existing corroboration that this is the
   floor and not an arbitrary number.
3. **It walks.** From +2 s the `Z` component of `Velocity` is exactly `0` and the horizontal
   magnitude is **capped at exactly `500.0`**:
   `|(-240.132, -438.562)| = **500.0**` · `|(-137.500, 351.364)| = 377.3` ·
   `|(-233.334, 442.216)| = **500.0**`.
   ⚠ **Two of the three ground samples are 500.0, not all three** — the middle one is 377.3, which is
   what a turn or a re-acceleration between wander headings looks like. The load-bearing claim is the
   **CAP**: nothing exceeds 500.0, and two independent samples sit exactly on it. Do not restate this
   as "500.0 at every sample" — I did, and it is wrong.
4. **The direction changes between samples**, and `Acceleration` tracks it
   (`(-43921.6, -23893.3, 0)` → `(-49279.7, -8456.2, 0)`, magnitude 50,000) — **the AI wander driver
   is steering it.**
5. ★ **`TimeSinceFallingStart` RESET from 8.6001 to 1.5357** between +5 s and +10 s — a real state
   transition: it walked off the island edge and began falling again. The external probe caught it
   mid-fall at `(3364.362, 2611.051, **-29425.4**)` with `Velocity = (0, 0, -1000)`.

★★ **AND A FREE CONFIRMATION OF THE WHOLE ARM-H MECHANISM.** At +250 ms the payload and `Velocity`
**differ slightly**: payload `(34.906, 0, -4000)` vs `Velocity` `(34.039, 0, -4000)`. The payload is
the **pre-step snapshot** and `Velocity` is **post-step** — so `+0x16B0` is visibly a per-frame copy
taken *before* the step modifies the field, exactly as `0x055C2448 / 0x055C244F` says. Nothing was
designed to show this; it fell out of a moving object.

---

## 2. THE PLAYER — outcome C, and the two arms DISAGREE (pre-registered outcome E)

The player is **untreated by ARM G** (no `AttributeSetStorage`, `AnalogInputModifier = 0`) and got
`Velocity = (0, 600, 0)` on a **different axis** so cross-contamination would be visible.

| t | PLAYER `Velocity` | location | moved |
|---|---|---|---|
| arm | `(0, 600, 0)` *(written)* | `(0, 0, 13240)` | 0 |
| +250 ms | `(0, 33.193, 0)` | `(0, 752.711, 13240)` | 752.7 uu |
| +750 ms | `(0, 22.194, 0)` | `(0, 766.193, 13240)` | 766.2 uu |
| +2 s | `(0, 8.749, 0)` | `(0, 784.296, 13240)` | 784.3 uu |
| +5 s | `(0, 0.887, 0)` | `(0, 794.426, 13240)` | 794.4 uu |
| +10 s | `(0, **0**, 0)` | `(0, 795.559, 13240)` | 795.6 uu |

**It moved 795 uu and then stopped dead.** A smooth monotone decay `600 → 33 → 22 → 8.7 → 0.9 → 0`,
and it **never fell** (`Z` constant at 13240).

⇒ **Pre-registered outcome E: BOT and PLAYER disagree, and the disagreement IS the result.**
**A real GAS-treatment dependency in the MOVER**, in exactly the predicted direction: the treated bot
sustains its `MaxMoveSpeed`; the untreated player is damped to zero.

---

## 3. ⇒ THE `CalcVelocity` CLAMP IS REAL AFTER ALL — AND THE VERIFIER'S STEP 3 IS REFUTED

The NOT-OBTAINED read from flight 1 is now obtained, on both objects:

> **`MinAnalogWalkSpeed @CMC+0x290` = `0`** — on the BOT **and** the PLAYER. **`< 1e-4`.**

So `GetMinAnalogSpeed()` contributes nothing, and
`MaxInputSpeed = max(GetMaxSpeed() × AnalogInputModifier, 0)` reduces to the first term alone. Then:

| | `AnalogInputModifier` | ⇒ `MaxInputSpeed` | clamp at `0x035D64F2` | observed |
|---|---|---|---|---|
| **BOT** (ARM-G treated) | **1** | `GetMaxSpeed() × 1` | must NOT fire | **sustains 500.0 uu/s** |
| **PLAYER** (untreated) | **0** | `GetMaxSpeed() × 0 = 0 < 1e-4` | **MUST FIRE** | **damped to exactly 0** |

⇒ ★★★★★ **The clamp is the PLAYER's wall, and it fires for the reason the offline lane described.**
The bot escapes it *because ARM G gave it a non-zero `MaxSpeed`*, and its sustained speed is
**numerically equal to the `MoveSpeed` ARM G wrote** — which is as direct a confirmation as this
surface can produce.

⚠⚠ **AND THIS REFUTES STEP 3 OF THE LANE-2/L5 VERIFIER'S CHAIN**, which argued
*"`GetMaxSpeed` reaches the SAME `+0xC00` slot as `GetMaxAcceleration`, and flight 4 measured
`GetMaxAcceleration() = 50000`, therefore `GetMaxSpeed() != 0`, therefore the clamp did not fire."*
That reasoning is **sound for the BOT and invalid for the PLAYER**, and the verifier applied it
without separating them: the player has **no `AttributeSetStorage` at all**, so *both* getters return
`0.0f` there and the clamp fires. The `AnalogInputModifier = 0` measured on the player in flight 1
was the tell, and it was in the data an hour before the refutation was written.

⇒ **The S141 handoff's §1.2 must be corrected: the clamp is [M] REAL, not [S].** What is genuinely
refuted is only *"the clamp explains the BOT's null"* — and the bot's null had a different cause.

---

## 4. SO WHY DID THE BOT NOT MOVE BEFORE? — THE FIXED POINT

The bot had `Acceleration = 50000 × input`, `MaxSpeed = 500`, `MovementMode = MOVE_Falling`,
`GravityScale = 1.000`, `StartNewPhysics` running every frame — **and `Velocity == (0,0,0)`, zero
translation, and no falling.** One 600 uu/s kick and all of it engaged at once.

⇒ **[M] `Velocity == 0` is a FIXED POINT of this system**: at exactly zero, nothing — not the
acceleration integration, not gravity — moves it off zero; perturbed by any real amount, the whole
chain runs correctly and self-sustains.

★★ **The MECHANISM is NAMED and it is one `comisd` — see §4b.** It was `[S]` for about an hour.

---


## 4b. ★★★★★ THE FIXED-POINT MECHANISM IS NAMED — AND IT RETRODICTS BOTH FLIGHTS, IN OPPOSITE
##      DIRECTIONS, FROM A DERIVATION THAT NEVER SAW THEM

The 13-agent offline workflow finished after this flight. Its adjudicator — working only from
`merged13`, with its own PE reader and CFG, and with no knowledge of ARM H or ARM J — derived:

> **[M] Engine `PhysFalling` ZEROES `Velocity` below a gravity-space `SizeSq2D` threshold.**
> `0x035ED98E comisd xmm1, [rip → .rdata 0x077F5180]`, where that constant is
> **`0.0009999999747378752` = `(double)(float)1e-3`**; `0x035ED996 ja` skips it, so the
> fall-through `0x035ED998 xorps xmm0,xmm0 … 0x035ED9BB movups [rsi],xmm0 /`
> `0x035ED9C3 movsd [rsi+0x10],xmm1` **writes `Velocity`**.
> `rsi = &Velocity` is **[M] by dominance**: the only defining `lea rsi,[rdi+0xe8]` in the body is
> `0x035EC9AC` (the other `rsi` def, `0x035EE519`, is the epilogue restore), and node-removal shows
> it **DOMINATES both writes** (reachable-avoiding-the-lea = `False` for each).

**Checked against every bot observation this session produced:**

| state | `SizeSq2D` | ratio to the gate | predicted | MEASURED |
|---|---|---|---|---|
| ARM H sentinel `2^-10` | `9.5367e-07` | **0.00095×** — below | **zeroed** | zeroed within 250 ms ✓ |
| the resting state `(0,0,0)` | `0` | **0×** — below | **zeroed** | `Velocity` has never left `(0,0,0)` ✓ |
| ARM J sentinel `600` | `360000` | **3.6e8×** — above | **kept** | fell, landed, walked 13,187 uu ✓ |
| the bot at +10 s, walking | `250000` | **2.5e8×** — above | **kept** | still walking at the 500 cap ✓ |

⇒ ★★★★★ **THE FIXED POINT IS EXPLAINED, AND ITS GRADE GOES `[S]` → `[M, offline; retrodicts 4/4
in both directions]`.** `Velocity == 0` ⇒ `SizeSq2D = 0` ⇒ below the gate ⇒ **written back to zero
every frame** ⇒ it can never leave zero on its own. Any perturbation above `|V_xy| ≈ 0.0316` escapes
and the whole chain runs. **That is the entire wall, and it is one `comisd`.**

★★ **This is the strongest form of evidence available here**: a mechanism derived offline, blind to
the flights, that predicts a *reversal* — zeroed below, kept above — and both arms of the reversal
were measured. Neither could have been fitted to the other.

⚠⚠ **AND IT SAYS THE "INERT SENTINEL" INSTINCT WAS EXACTLY BACKWARDS.** ARM H chose `2^-10`
*because* it was physically negligible — and negligible is precisely what puts it under the gate.
**A smaller, "more inert" sentinel is zeroed HARDER.** The adjudicator recommends `2^-20` for a
different gate (`SizeSq2D < 1e-8`, `|V_xy| < 1e-4`) in `ULokiCMC::PhysFalling` at `0x055B877D`, and
that is worth keeping for any future *inertness* argument — but for THIS gate no inert value exists.
⇒ ★★ **ARM H's poison-the-payload design is what saved the flight.** Had it depended on the
sentinel surviving, it would have returned a false negative for a reason nobody had identified yet.

⚠ **[I], not [M]: whether `Velocity.Z` is zeroed too.** The Z store takes `xmm1`, and this document
does not establish `xmm1 == 0` there. Flight 1 read `(0,0,0)` including Z, and flight 3 shows Z
accumulating to terminal velocity once above the gate — consistent with Z also being zeroed below
it, which would explain the no-fall phenomenon as well. **One read of the instruction settles it.**

⚠ **The PLAYER's decay is a DIFFERENT site.** Its `600` on +Y is also far above this gate, yet it
decayed monotonically to 0 — that is the `CalcVelocity` `MaxInputSpeed` clamp of §3, which fires
because the untreated player has `AnalogInputModifier = 0`. **Two distinct zeroing sites, each with
its own measured signature. Do not merge them.**

---

## 5. WHAT THIS CHANGES

- ⛔ **"the physics does not work" is dead.** Falling, landing, ground movement, speed clamping and
  AI steering are all measured working on a client this project has been calling broken since S138.
- ⇒ **The remaining problem is a KICK-OFF problem**, and it is small. Anything that puts a real
  velocity into the pawn once — a jump, a knockback, a launch, a gravity tick that actually
  accumulates — releases the whole system.
- ★ **And it is already actionable without understanding the mechanism**: writing `Velocity` once is
  a single 24-byte DATA write with a readback, and it makes an AI-controlled hero walk. That is not
  a shipping fix, but it is the first time anything in this project has made a character move under
  its own AI rather than by having its transform driven every frame.

⚠ **Scope, unchanged.** Still not a bot: `ServerSetHeroClass` and `SetPlayerTeam` are stripped folds,
nothing went through `SpawnBot`, and ARM G is a process-wide CDO poke. ARM J perturbs by design and
does not restore the PLAYER's velocity. **None of these arms belongs in the default shim set.**

---

## 6. INSTRUMENT DEFECTS THIS FLIGHT

| # | defect | how it showed |
|---|---|---|
| S140T2-h | **My own page-census script unpacked the PE section header as `(VirtualAddress, VirtualSize, …)` instead of `(VirtualSize, VirtualAddress, …)`.** | Every function graded **dark in every image**, including seven I had measured LIT an hour earlier. ⇒ ★ **a census that returns all-negative is far more likely to be a broken instrument than a discovery** — and the give-away was the *contradiction with a prior measurement*, not the values themselves. Re-run with a passing negative control (`Respawn 0x5A6AC40` dark in both) beside the positives. |
| S140T2-i | **The ARM H verdict block printed `UNMODELLED payload value` for the BOT** — correctly, because ARM J deliberately moves outside ARM H's outcome table. | Not a defect in the arm; a defect in **reusing a verdict function across a changed question**. The raw samples carried the entire result. ⇒ ★ when an arm changes what it does, its inherited verdict logic becomes an uncalibrated instrument. Read the samples. |
| S140T2-j | **The flown `gasattr-sentinel ce56fd715de835a1` was overwritten in `build/` before being archived**, against this repo's own "archive every A/B arm before rebuilding" rule. | Recoverable from commit `3176139` with an unmodified `build.ps1`; the flight-2 artifact `sentinel-burst 62b5423febd6f779` **is** intact in `dumps/s140-arms-t2/`. Recorded rather than quietly re-digested. |

---

## 7. THE OTHER TWO UNSPENT TIER-2 ITEMS, BOTH SPENT HERE

- ★ **`MinAnalogWalkSpeed @CMC+0x290` — NOT OBTAINED in flight 1, now MEASURED = `0` on both.**
  It came free with this staging, exactly as planned, and it is load-bearing in §3.
- **T2-D: `LogCharacterMovement=Log` pinned in the USER `Engine.ini`** (FK-11 channel, via
  `set-log-verbosity.ps1 -Preset ClassA -Categories @{ LogCharacterMovement='Log' }`).
  **Result: 0 occurrences in the flight-3 log.**
  ⚠⚠ **THAT ZERO IS UNINTERPRETABLE AND WAS PRE-REGISTERED AS SUCH.** The only reachable site fires
  when `IsSimulatingPhysics()` is TRUE, which S139 measured FALSE — so the category has **no
  positive control on this route** and its silence is evidence about nothing. It is pinned to give
  the category a voice for future sessions. **Do not cite this zero.**

## 8. HEALTH

FK-32 again: exit `0x0000DEAD`, no artifact, at **T+320.2 s** on the **4th** manual-map — the third
consecutive flight to die that way at that injection count. The `0xDEAD` series is now
**7 / 6 / 4 / 4 / 4 / 4** injections at 1144 / 334 / 350 / 318 / 320 s.
★ **Nothing was lost again**: the marker, the external probe read and the `dumpimage` were all
captured before the death. **Capture as you go.**

## 7. FREE BY-PRODUCT

`dumps/s140-t2-walking/` — the walking image alone holds **16 `.text` pages** not in `merged13`
(8 of them new even beyond flight 1's dump). Everything on the movement path was already LIT, so the
yield is small, but this is the first image ever taken of this client **while a character was walking
on the ground**.

**`dumps/merged14.dump.exe` — `16,816 / 30,281 = 55.53 %`**, verified a **STRICT SUPERSET** of
`merged13` before adoption (**pages LOST 0**, gained **+16**, 0 byte conflicts on shared pages).
`tools/strxref/strxref.py`'s `DEFAULT_DUMP` moved to it.
⚠⚠ **AND THE FIRST MERGE ATTEMPT SILENTLY DID NOTHING.** Given DIRECTORIES rather than `.dump.exe`
paths, `mergedumps` printed `skip … : Incorrect function.` for both donors, still wrote a
`merged14.dump.exe`, and still reported a plausible-looking `51.91 % non-zero merged` — while the
page census showed **gained 0, identical to `merged13`**. It exited **0**. ⇒ ★ **`mergedumps` needs
FILE paths; and always page-census the output against the seed before adopting it, because the
manifest's own byte-percentage cannot distinguish a real merge from a no-op.**
⚠ Quote the unit: `mergedumps` prints pages **taken from each donor** (8 and 8 here); the corpus
**coverage delta** is the separate number (+16).
