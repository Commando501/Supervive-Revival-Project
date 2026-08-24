# S141 TIER 3 / ARM L — **THE BOT WALKS ON A HORIZONTAL KICK**, and my own A/B failed to test what it was built for

**2026-08-24.** One staged client (PID 53376, base `0x7FF704F00000`), one injection,
`axisab` RAW `83bcf5c178846022`. Pre-registration `docs/s141-t3-arml-PREREGISTERED.txt`, committed
at `a0ebba8` **before** the client was launched. Evidence: `docs/s141-t3-marker-arml.txt` (407
lines), `docs/s141-t3-Loki-arml.log`, `dumps/s141-arml/`.

---

## HEADLINE

> **1. [M] THE BOT FELL, LANDED AND WALKED 13,195 uu ON A HORIZONTAL KICK.** `Velocity = (600,0,0)`
> once, from rest: it fell at terminal velocity (`Vz = -4000`), landed, and walked with `|V_xy|`
> pinned at **exactly 500.0 uu/s** — the `MoveSpeed` ARM G wrote — steered by its own AI
> (`Acceleration` = |50000|, rotating). **This is the ARM K bot, same arms, same staging, and in
> ARM K it moved 0.000 uu five times.**
>
> **2. [M] `CMC+0x3D0` IS `AnalogInputModifier`** — resolved BY NAME on the live class, AGREEING
> with the hardcoded offset, on both pawns at every sample. This closes defect **S141-d** (the read
> ARM K missed) and confirms the offset I had inferred from `CalcVelocity`'s
> `mulss xmm11,[rbx+0x3d0]`.
>
> **3. [M] AND IT REFUTES §4.1 FOR THIS RUN: `AnalogInputModifier = 1` at every sample**, so
> `MaxInputSpeed = GetMaxSpeed() × 1 = 500`, and engine `CalcVelocity`'s `< 1e-4` ZeroVector clamp
> **cannot** be firing. The clamp is not what stops this bot, because this bot is not stopped.
>
> **4. [M] THE PLAYER RESULT REPLICATED EXACTLY, in an independent sitting** — `GravityScale`
> 0 → 1.0 and it fell to `Z = -10,052`, moving 23,306 uu, `AnalogInputModifier = 0`,
> `Acceleration = (0,0,0)` throughout. **n = 2 on the S141 GravityScale finding.**
>
> **⚠⚠ 5. AND MY OWN A/B FAILED TO TEST THE THING IT WAS BUILT FOR — see §2. Kick B landed on a
> bot that was already walking at 500 uu/s, so it tested "vertical added to a moving body", not
> "vertical from rest". The within-sitting axis comparison did not happen.**

---

## 1. THE DATA — raw, both pawns, one pass

    BOT (ARM G treated, GravityScale 1.0, MOVE_Falling, AI wander steering)
    sample        Velocity                          moved        AnalogIM   Acceleration
    s0 +250 ms    (22.171,   0,      -4000)         12,202 uu    1          ( 41972.1, -27172.5, 0)
    s1 +750 ms    (-17.254,  499.702,    0)         13,187 uu    1          ( -1725.4,  49970.2, 0)
    s2 +2000 ms   ( 91.697,   16.911,    0)         13,196 uu    1          ( -1725.4,  49970.2, 0)
    >>>>>>>>>>>>>> ARM L: kick B (0, 0, -600) written; start location RE-LATCHED <<<<<<<<<<<<<<
    s3 +5000 ms   (251.652, -432.055,    0)            502 uu    1          ( 25165.2, -43205.5, 0)
    s4 +10000 ms  (-499.878, -11.049,    0)          1,478 uu    1          (-49987.8,  -1104.9, 0)

    PLAYER (ARM K1 storages, GravityScale poked 0 -> 1.0, ARM J +Y 600, NO input driver)
    s0 +250 ms    (0, 21.620, -4000)      12,321 uu   0   (0,0,0)   Z =    943.4
    s1 +750 ms    (0, 14.456, -1186.875)  13,670 uu   0   (0,0,0)   Z =   -407.8
    s2 +2000 ms   (0,  5.557, -1000)      15,079 uu   0   (0,0,0)   Z =  -1818.0
    s3 +5000 ms   (0,  0.577, -1000)      18,183 uu   0   (0,0,0)   Z =  -4925.7
    s4 +10000 ms  (0,  0,     -1000)      23,306 uu   0   (0,0,0)   Z = -10052.9

**Speed check on the bot's ground samples:** `|(-17.254, 499.702)| = 500.0` ·
`|(251.652, -432.055)| = 500.0` · `|(-499.878, -11.049)| = 500.0`. Three samples exactly on the cap.
`s2` is 93.2 — a turn between wander headings, the same shape S140 flight 3 recorded.

★ **A HORIZONTAL kick produced a FALL.** `Vz` was `-4000` at s0 having been given only `(600,0,0)`.
That is the 2-D gate mechanism of §1 working in the affirmative direction: `|V_xy|` above the
`0.0316` threshold ⇒ the `SizeSq2D` clamp does not fire ⇒ `PhysFalling` proceeds ⇒ gravity
accumulates into Z. **Nothing needed to kick Z at all.**

---

## 2. ⚠⚠ THE PRE-REGISTERED TEST DID NOT HAPPEN, AND THAT IS MY ERROR

The pre-registration named four outcomes. The data lands on **P2 — "both sustain"** — whose stated
reading is *"the axis is NOT the variable; §4.1b is REFUTED."*

**That reading DOES NOT FOLLOW, because kick B was not the test I designed it to be.**

Kick B was written after sample 2, by which time the bot **was already walking at 500 uu/s**. So B
added `-600` on Z to a body with `|V_xy| = 93` — it tested *"a vertical impulse added to a moving
character"*, which nothing predicted anything about. **The axis hypothesis is about escaping from
`Velocity == 0`,** and B never started from rest.

The arm re-latched the *location* at the B write — I thought about that — and **did not re-latch, or
even consider, the velocity state.** A within-sitting A/B on "escape from rest" needs the bot to BE
at rest when arm B starts, which means zeroing Velocity and letting it settle first.

⇒ **Recorded as instrument defect S141-l**, and the honest verdict is:

| | verdict |
|---|---|
| within-sitting axis A/B | **DID NOT RUN.** P2 is an artifact of the arm, not a result about the game. |
| §4.1b (the axis mechanism) | **NEITHER confirmed nor refuted by this flight.** |
| §4.1 (the `CalcVelocity` clamp as the bot's zeroing site) | **REFUTED for this run** — `AnalogInputModifier = 1` ⇒ `MaxInputSpeed = 500` ⇒ the `< 1e-4` guard is unsatisfiable. |

★ **What DOES bear on the axis is the CROSS-SITTING comparison**, which is what ARM L was built to
replace and which therefore still stands alone:

| | ARM K (2026-08-23) | ARM L (2026-08-24) |
|---|---|---|
| kick, from rest | **vertical** `(0,0,-600)` | **horizontal** `(600,0,0)` |
| `AnalogInputModifier` | **NOT READ** (defect S141-d) | **1** |
| `Velocity` | `(0,0,0)` at all five samples | fell, landed, walked at 500 |
| moved | **0.000 uu ×5** | **13,196 uu** |

Same arms, same treatment, same staging script, same instrument, two sittings. **Consistent with
the axis mattering — and it is one uncontrolled variable away from being evidence**, because
`AnalogInputModifier` was never read in ARM K.

---

## 3. THE CLEAN TEST, AND WHY IT DID NOT HAPPEN

Vertical-from-rest **with `AnalogInputModifier` read** is now a one-injection experiment, and the
arm for it already exists: `armk` rebuilt with the new read — **`armk_v2` RAW
`988fd61853669d5c`**, archived at `dumps/s141-arms/tutorial_launch_armk_v2.dll`.

I built it during this sitting and tried to inject it as a 5th manual-map into the still-live
client. **The client died in the gap between the liveness check and the injection**, and the
guard refused rather than injecting into a dead PID. FK-32 again: **0 crashpad handoffs, 0 `Fatal`,
no artifact**, on the 4th manual-map.

★ **Two process notes worth keeping.**
1. **Taking the `dumpimage` EARLY worked** — it is banked at `dumps/s141-arml/`, which ARM K lost by
   leaving it until last. ⚠ **Its yield was ZERO** (`dump_coverage_ledger.py`: union unchanged at
   16,816 pages / 55.53 %, no orphans). Everything on this path was already lit. The process was
   right even though the payoff was nil — record both.
2. **The `if(Get-Process …)` guard on the injection earned its keep.** Injecting into a dead PID
   prints an `OpenProcess` failure that reads like a tooling fault; refusing prints
   `*** CLIENT GONE — not injecting ***`.

---

## 4. WHAT THIS FLIGHT SETTLES

* **[M] `CMC+0x3D0` = `AnalogInputModifier`** — by-name AGREES with the offset, both pawns, all
  samples. Defect S141-d closed.
* **[M] `MinAnalogWalkSpeed` (`+0x290`) = 0 on both pawns** — replicates S140 T2 flight 3.
* **[M] An ARM-G-treated, AI-steered bot walks at exactly its configured `MoveSpeed`** on a single
  horizontal kick, in a second independent sitting. S140 T2 flight 3 is **reproduced**.
* **[M] The player's `GravityScale` result replicates** (n = 2, independent sittings).
* **[M] §4.1 is refuted for a walking bot** — the clamp cannot fire at `AnalogInputModifier = 1`.
* **⚠ Still open:** whether a **vertical-from-rest** kick is zeroed, and if so whether
  `AnalogInputModifier` is 0 in that state. **One injection, arm already built.**
* **⚠ Still open, unchanged:** T3-C's Q2 — the player has no input driver, `Acceleration` read
  `(0,0,0)` at every sample exactly as predicted in the pre-registration, so its 600 → 0 decay
  remains correct physics and discriminates nothing. **This was stated up front, not discovered
  afterwards.**

## 5. HEALTH

Staged on **attempt 1**. One injection. FK-32 at the **4th** manual-map: 0 crashpad, 0 `Fatal`, no
artifact. The `0xDEAD` series is now **7 / 6 / 4 / 4 / 4 / 4 / 4 / 4**.
Gates `botai 5e47c13cf7f0a158` · `gasattr 2fcc2536e21f18e3` · `gasattr-ctrl 4465ebc4d7168c03` all
reproduced EXACTLY before the flight. `axisab 83bcf5c178846022` / `axisab-ctrl 90d90aacec2a38d3`
verified DISTINCT despite an identical `.text` size.
