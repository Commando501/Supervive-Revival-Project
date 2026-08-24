# S141 TIER 3 — THE FIXED POINT IS 2-D, THE PLAYER'S NON-FALL WAS OURS, AND THE MOVER RUNS

**2026-08-23/24.** Six offline lanes over `dumps/merged14.dump.exe` + **one** staged flight
(PID 25800, base `0x7FF704F00000`, one injection, `armk` RAW `8278c6031d05756c`).
Pre-registration: `docs/s141-t3-armk-PREREGISTERED.txt`, committed at `825aeda`/`ee0f0a1`
**before** the client was launched. Evidence: `docs/s141-t3-marker-armk.txt` (377 lines),
`docs/s141-t3-Loki-armk.log`, `docs/s141-autostage.out.txt`, `scratchpad/s141/`.

---

## HEADLINE

> **1. [M] `Velocity.Z` is NOT zeroed by the S140 fixed-point gate. The gate is 2-D.**
> Derived four times independently (session lead + lanes L1, L2, L4, L5), agreeing on every byte.
>
> **2. [M] The PLAYER's non-fall was SELF-INFLICTED, and restoring one float made it fall 23,189 uu.**
> `sp`'s own LIFT step sets `GravityScale = 0`. `CMC+0x1A0` is `GravityScale`; one 4-byte write of
> `1.0f` and the player fell from `Z = 13240` to `Z = -9935` in 10 s at terminal velocity.
>
> **3. [M] AND THE WHOLE ENGINE MOVER CHAIN DEMONSTRABLY RUNS ON THIS CLIENT.** The player was
> given `Velocity = (0, 600, 0)` — **Z exactly zero** — and `Velocity.Z` accelerated to `-4000`.
> ⇒ gravity integrates from `Vz == 0`; `TickComponent → ControlledCharacterMove → PerformMovement
> → StartNewPhysics → PhysFalling` all execute. **"`Velocity == 0` stops the mover" is dead.**
>
> **4. [M] S132's dismount was a `GravityScale` RESTORE, not a velocity write** — which is why that
> hero fell with X and Y frozen. T3-B's dismount question is answered.
>
> **5. ⇒ THE BOT IS NOW THE ONLY THING THAT DOES NOT MOVE, AND IT IS THE PAWN WITH INPUT.**
> Pre-registered outcome **P1**: the bot's `Velocity` was written to `(0, 0, -600)` and read
> **`(0,0,0)` at +250 ms and at every sample to +10 s**, with `moved 0.000 uu` five times — in the
> same world, same frame, same instrument, same pass as the player that fell.

---

## 0. THE FLIGHT — raw, both pawns, one pass

Both `ShResolveCmc` identity controls PASSED on both objects (`CharacterOwner@0x198 == pawn`,
`TickFn.Target@0x68 == cmc`), both `vptr == base+0x088F8570` (ULokiCMC), both
`WorldPrivate@0xC0 = 'LVL_Tutorial'`.

| | BOT | PLAYER |
|---|---|---|
| GravityScale `+0x1A0` | **1.0000** | **0.0000 → poked 1.0000** |
| MovementMode `+0x231` | 3 `MOVE_Falling` | 3 `MOVE_Falling` |
| GravityDirection `+0x1D8` | **(0, 0, -1)** | **(0, 0, -1)** |
| `byte +0x1001` | 0 | 0 |
| latLimit `+0x1678` | -1.0000 (disabled) | -1.0000 (disabled) |
| `Acceleration +0x328` | **\|50000\|, rotating** (AI wander) | **(0, 0, 0)** |
| Velocity written | **(0, 0, -600)** | (0, 600, 0) |
| payload `+0x16B0` poison | overwritten with **zeros** | overwritten |
| ARM G / K1 storages | 3/3 | **3/3** |

    t          BOT Velocity      BOT moved      PLAYER Velocity            PLAYER Z      PLAYER moved
    armed      (0, 0, -600)      –              (0, 600, 0)                 13240.0      –
    +250 ms    (0, 0, 0)         0.000 uu       (0, 18.991, -4000)            301.9      12,961 uu
    +750 ms    (0, 0, 0)         0.000 uu       (0, 12.978, -1178.194)       -531.0      13,793 uu
    +2 s       (0, 0, 0)         0.000 uu       (0,  5.031, -1000)          -1889.6      15,150 uu
    +5 s       (0, 0, 0)         0.000 uu       (0,  0.524, -1000)          -4909.6      18,167 uu
    +10 s      (0, 0, 0)         0.000 uu       (0,  0,     -1000)          -9935.7      23,189 uu

### 0.1 The bot's zero is NOT self-inflicted [M]

The project's dominant failure mode is exactly this, so it was checked before anything was written up:

* `KBSPSARMS = 0x1BA0` decodes to bits 5,7,8,9,11,12 and the ON bits sum back to `0x1BA0`.
  **Bit 10 — ARM H2, the 2 ms re-write burst — is OFF**, so nothing re-wrote `Velocity` during
  sampling.
* The **only** two `Velocity` writes in the whole run are marker lines **218** (bot, once) and
  **219** (player, once). Both precede the armed dump at 224–237.
* `restore: BOT Velocity -> (0,0,0)` is marker line **344** — **after all five samples**
  (244, 263, 282, 301, 320).

⇒ the `(0,0,0)` at +250 ms is the game's, not ours.

---

## 1. T3-A — **ANSWER: `Velocity.Z` IS NOT ZEROED. THE FIXED POINT IS 2-D.** [M]

```
035ed96e  call   0x35F4770                ; RotateWorldToGravity(Velocity) -> [rbp+0x168]
035ed973  movups xmm0,[rbp+0x168]         ; gravity-space X, Y (two doubles)
035ed97a  movsd  xmm1,[rbp+0x170]         ; Y
035ed982  mulsd  xmm0,xmm0                ; X*X
035ed986  mulsd  xmm1,xmm1                ; Y*Y
035ed98a  addsd  xmm1,xmm0                ; SizeSq2D   <- Z at [rbp+0x178] IS NEVER READ
035ed98e  comisd xmm1,[rip -> .rdata 0x077F5180]
035ed996  ja     0x35ed9c8                ; ABOVE the gate -> skip
035ed998  xorps  xmm0,xmm0
035ed9ac  movups [rbp+0x168],xmm0         ; *** 16 BYTES: gravity-space X and Y ONLY ***
035ed9b3  call   0x35F4620                ; RotateGravityToWorld ; `mov rax,rdx` -> returns the OUT buffer
035ed9b8  movups xmm0,[rax]
035ed9bb  movups [rsi],xmm0               ; Velocity.X, Velocity.Y
035ed9be  movsd  xmm1,[rax+0x10]          ; <- from the TRANSFORM OUTPUT, not from a zero
035ed9c3  movsd  [rsi+0x10],xmm1          ; Velocity.Z
```

`movups` is 16 bytes over a **24-byte** `FVector` of doubles, so `[rbp+0x178]` (gravity-space Z)
is never written and is round-tripped back verbatim. **`xmm1` at `0x035ED9C3` is loaded at
`0x035ED9BE` from the transform's output.** Under default gravity the quat is identity, so the round
trip is a pass-through.

* `rsi = &Velocity` — **the sole defining `lea rsi,[rdi+0xe8]` is `0x035EC9AC`**; the only other
  `rsi` def is the epilogue restore `0x035EE519`. L1 showed by iterative dominators that
  `0x035EC9AC` **dominates all 32 rsi-based Velocity writes (32/32)**.
* **36 Velocity write instructions** in engine `PhysFalling` (`0x035EC850`, sound CFG: 1482 insns,
  79 calls, **0 indirect jumps, 0 decode failures**).

⇒ CLAUDE.md's open `[I]` — *"whether `Velocity.Z` is zeroed too … it would explain the no-fall"* —
is **SETTLED NEGATIVELY: it does not, so it does not explain it.**

### 1.1 CORRECTION — the gate constant's identity in `docs/s140-t2-armj-THE-BOT-WALKS.md` §4b is WRONG

`.rdata 0x077F5180` = **`0.00099999997473787516`**.

| candidate | value | verdict |
|---|---|---|
| `(double)(float)1e-3` | 0.0010000000474974513 | **what the doc asserts — REFUTED** |
| `(double)(float)1e-4 * 10.0` | **0.00099999997473787516** | **this** — `UE_KINDA_SMALL_NUMBER` (float) × 10 |

Stock UE's guard is `Velocity.SizeSquared2D() <= UE_KINDA_SMALL_NUMBER * 10.f`. The doc's decimal
string was right; only its *identification* was wrong. Escape threshold `sqrt(gate)` =
**0.03162277644…** (the doc's ~0.0316 stands). Confirmed independently by the lead, L1, L2 and L5.

### 1.2 ⇒ AND THE LIVE RESULT IS PRE-REGISTERED OUTCOME **P1**, NOT P2

The bot was given a **purely vertical** `(0, 0, -600)` — `SizeSq2D == 0`, maximally below the 2-D
gate, and at the **same magnitude** S140 flight 3 measured escaping on X, so magnitude cannot
explain a null. **It read `(0,0,0)` at +250 ms.**

⚠⚠ **Scope this precisely, because it is easy to over-read.** What the flight refutes is *"the 2-D
gate accounts for this bot"* — it does not. It does **NOT** refute §1: the gate really is 2-D
(four independent byte-level derivations, and the player's Z surviving to −4000 in the same pass
is live corroboration). **Something ELSE zeroes all three components on the bot.** Two distinct
facts; merging them would repeat this project's recorded error of pooling mechanisms under one label.

---

## 2. `CMC+0x1A0` IS `GravityScale`, AND IT RESOLVES TWO RECORDED PHENOMENA [M]

Read from its own consumer — engine `UCharacterMovementComponent::GetGravityZ`
(engine CMC vtable disp `0x4C0` = `0x035E3650`):

```
035e3678  mov   rcx, rbx
035e367b  call  0x3632e20                       ; Super::GetGravityZ()
035e3680  mulss xmm0, dword ptr [rbx + 0x1a0]   ; * GravityScale
035e368d  ret
```

Three agreeing instruments (L4): those bytes; `binds_members.csv` giving
`UCharacterMovementComponent` **property index 0 = `float32 GravityScale`**; and the shim resolving
the offset **by name** at runtime and printing `GravityScale@0x1A0` in every staged marker.

**(a) S132's dismount.** `AuthPlayerDetachPlayerFromRidable` at `0x55CCDC9` does
`mov dword [r14+0x1a0], 0x3f800000` = `GravityScale = 1.0f`. L4's exhaustive write scan finds
**no velocity write anywhere in that function**. ⇒ the S132 hero's free fall — *"Z −117,462.8 →
−121,560.9 over 4.0 s with X and Y FROZEN"* — is **pure gravity, switched back on.** That signature
is exactly a vertical-only escape, and no velocity-write hypothesis produces it.

**(b) The player's non-fall.** `tools/sigbypass-mod/tutorial_launch.cpp:12877-12890` — `sp`'s
**LIFT-TO-SEE** block — sets `*(float*)(cmc+gsOff) = 0.0f` and teleports the hero +1800.
`[LIFT] gravity OFF` appears at line 24 of **every** staged `sp` marker in the repo, and
`docs/s138-flight9-movement-not-simulating.md:17` already recorded **BOT 1.000 / PLAYER 0.000
"(zeroed by `sp`'s LIFT step)"**. Tonight the shim read `PLR-before GravityScale@0x1A0=0.0000` and
fired its own warning; ARM K2 wrote `1.0000` and the player fell within 250 ms.

⇒ `docs/s140-t2-armj-THE-BOT-WALKS.md` §2 presents the player's non-fall as an observation about the
game and infers *"a real GAS-treatment dependency in the MOVER"* partly from it. **The horizontal-decay
half of that inference stands** (that is the `CalcVelocity` braking/clamp story, §3 of that doc);
**the non-fall half is refuted — it is a `GravityScale` of zero that we set ourselves.**

### 2.1 CORRECTION — "bot and player read IDENTICALLY on EVERY structural field" is false

CLAUDE.md and `docs/s139-flight1-the-bot-is-not-special.md` list ~19 fields and conclude the two
pawns are identical. **`GravityScale` is not among the fields read** — and it is the one field that
governs falling. The honest form is *"identical on every structural field that was read."*
Measured tonight in one pass: **BOT 1.0000 / PLAYER 0.0000.**

---

## 3. GRAVITY IS NOT SUPPRESSED, AND THAT IS NOW MEASURED, NOT INFERRED

**[M] Exactly TWO mandatory gates** guard gravity integration in engine `PhysFalling`
(edge-removal — not node-removal — over the sound CFG, for all three of `GetGravityZ 0x035ECC21`,
`NewFallVelocity 0x035ECCEF`, `0x035ED617`):

```
0x035EC881  jb  0x35ee577   fallthrough MANDATORY   comiss DeltaTime, MIN_TICK_TIME (1e-6f)
0x035EC97C  jge 0x35ee507   fallthrough MANDATORY   cmp Iterations, [rdi+0x3E4] MaxSimulationIterations
```

**Neither depends on velocity, on the `SizeSq2D` gate, or on `Acceleration`.**
`ULokiCMC::StartNewPhysics` passes `Iterations` through UNCHANGED (tail `jmp 0x3600990`, `r8d`
untouched) and engine SNP forwards it as `edi`→`r8d`; with `Iterations == 0` and
`MaxSimulationIterations == 1` (read live on **both** pawns tonight) both gates pass.

The gravity block itself, from the bytes:

```
035ecc05  movups xmm6,[rdi+0x1d8]   ; GravityDirection X,Y      -- read LIVE tonight: (0,0,-1)
035ecc12  movsd  xmm7,[rdi+0x1e8]   ; GravityDirection Z
035ecc21  call   [rax+0x4c0]        ; GetGravityZ()
035ecc4d/51/55  mulsd x3            ; * gz
035ecc59/5d/71  xorps x3            ; negate  =>  Gravity = -GravityDirection * GetGravityZ()
035eccef  call   [rax+0x7a0]        ; NewFallVelocity(Velocity, Gravity, dt)
035eccfb  movups [rsi],xmm0         ; Velocity.X, .Y  <- the result
035ecd06  movsd  [rsi+0x10],xmm1    ; Velocity.Z      <- the result
```

**Every candidate for a statically-zero gravity is REFUTED, three of them live:**

| candidate | verdict |
|---|---|
| `GravityDirection == (0,0,0)` (lane L1's top hypothesis) | **REFUTED LIVE: `(0, 0, -1)` on both pawns.** |
| `GravityScale == 0` on the bot | **REFUTED LIVE: 1.0000.** |
| engine `GetGravityZ`'s `return 0.0f` arm (`0x035E366F`) | **not taken.** It needs `[CMCvt+0xCE0]()` true; disp `0xCE0` = **`0x035E6810`** on **both** CMC vtables, which this repo identifies as `IsDashing` (`cmp byte [rcx+0x231],6`), and `MovementMode == 3`. Its second input `byte [CMC+0x1001]` read **0** live. |
| `ULokiCMC::GetGravityZ 0x055AB8C0` zeroing it | **REFUTED [M]:** its zero arm is behind `cmp byte [rcx+0x231], 7` (`MOVE_Custom` in this build). At mode 3 the first branch `0x055AB8D4 jne` takes the general path and returns the engine value unmodified. |
| `ULokiCMC::NewFallVelocity 0x055B6AD0` swallowing it | **REFUTED [M]:** it calls the engine at `0x055B6AEC` and only modifies the result under `MovementMode==7 && CustomMovementMode==1`; at mode 3 it returns `rax = rbx` unchanged. |
| engine `NewFallVelocity 0x035E8B00` | integrates unconditionally when `dt > 0` (`0x035E8B31 comiss / jbe`), `Result += Gravity*dt` at `0x035E8B4E..0x035E8B85`. **No `Gravity.IsZero()` gate.** |

⇒ **[M] gravity is live on this client**, and the player's fall to terminal velocity from `Vz == 0`
is the direct confirmation.

---

## 4. THE BOT — what is left, and it is one function

`payload@0x16B0` was poisoned and read **`(0,0,0)`** ⇒ `ULokiCMC::StartNewPhysics` was entered and
snapshotted `Velocity` **already zero**. So the zeroing is at or upstream of the snapshot, which
sits in the Loki wrapper's prologue:

```
055c2448  movups xmm0,[rcx+0xe8]      ; read Velocity
055c244f  movups [rcx+0x16b0],xmm0    ; THE PAYLOAD WRITE
055c2470  jmp    0x3600990            ; only NOW is the engine entered
```

⚠⚠ **AND THAT IS A SCOPE CORRECTION TO S140 TIER 2 WORTH RECORDING ON ITS OWN.** Tier 2's headline
— *"`ULokiCMC::StartNewPhysics 0x055C2430` RUNS"* — is literally correct, but `CLAUDE.md` and
`docs/next-session-prompt-s141.md` restate it as **"the physics step runs every frame"**, and that
crosses a function boundary: the payload write is **upstream of the engine call**, and engine
`StartNewPhysics 0x03600990` has **four** further early-outs (`dt < MIN_TICK_TIME` `0x036009AF`,
`Iterations >= Max` `0x036009BC`, `HasValidData` `0x036009CD`, `IsSimulatingPhysics` `0x036009EC`)
before its jump table. Same class of error S139 committed in the opposite direction with `+0x12B0`.
⇒ **Tonight's player result is what actually establishes that the step runs** — because the pawn
physically fell 23,189 uu — not the payload write.

**[M] `ULokiCMC::PerformMovement 0x055B8370` contains ZERO writes to `+0xE8/+0xF0/+0xF8`.**
(And a correction: CLAUDE.md's *"the three `ucomisd` at `0x055B8838/3E/4A` … the write is SKIPPED"*
describes a write to **`[rsi+0x12F0]`/`[rsi+0x1300]`**, not to `Velocity`.)

### 4.1 THE LEADING CANDIDATE — engine `CalcVelocity`'s clamp `[I, strong]`

⚠ **Pending adversarial verification at the time of writing** (`scratchpad/s141/verify2/`).

```
035d6467  call   [rax+0x4d0]              ; IsExceedingMaxSpeed(xmm1 = MaxInputSpeed)
035d646f  je     0x35d64a3                ;   not exceeding -> xmm0 = xmm11 (MaxInputSpeed)
035d6471..9d                              ;   exceeding     -> xmm0 = sqrt(Vx²+Vy²+Vz²)
035d64c6..ea  mulsd by [rbx+0x328] / addsd from [rbx+0xe8/f0/f8]   ; Velocity += Acceleration*dt
035d64e6  cvtps2pd xmm8, xmm0
035d64f2  comisd xmm8, xmm9                ; xmm9 = .rdata 0x076B49E8 = 9.999999747378752e-05
035d64f7/ff/07  STORE Velocity = V + A*dt  ;                        = (double)(float)1e-4
035d650f  jae    0x35d6534                 ; >= 1e-4 -> normal clamp
035d6511  movups xmm1,[rip -> 0x099C86A0]  ; ZeroVector (16 zero bytes)
035d6520  movups [rbx+0xe8], xmm1          ; *** Velocity.X, Velocity.Y := 0
035d6527  movsd  [rbx+0xf8], xmm2          ; *** Velocity.Z := 0
```

`[CMCvt+0x4D0] = 0x0363BA00` on **both** CMC vtables, byte-matching stock
`UMovementComponent::IsExceedingMaxSpeed(float)` (`maxss xmm1,0` / `mulss xmm1,xmm1` /
`mulss xmm1,[rip](=1.01f)` / `comisd SizeSq, that` / `seta al`). `xmm11` is
`0x035D605B mulss xmm11,[rbx+0x3d0]` then `0x035D607A maxss xmm11,xmm0` — i.e.
`max(MaxSpeed × <+0x3D0>, GetMinAnalogSpeed())`. This is stock
`Velocity = Velocity.GetClampedToMaxSize(MaxInputSpeed)`, whose `MaxSize < KINDA_SMALL_NUMBER`
path returns `ZeroVector`.

**Why it fits tonight exactly:** the site is on the **ACCELERATE** branch, downstream of
`Velocity += Acceleration*dt`. The bot has `|Acceleration| = 50000`, so it reaches that branch;
the player has `Acceleration = (0,0,0)`, so it takes the **braking** branch — its Y decays by
friction (600 → 19 → 13 → 5 → 0.5 → 0, exactly the observed shape) and its Z is never clamped, so
gravity accumulates. **The pawn with input is the one that is zeroed.**

⚠⚠ **THE COUNTER-EVIDENCE THIS DOES NOT YET EXPLAIN, STATED PLAINLY:** S140 Tier 2 flight 3 measured
the **same bot** with the **same ARM G treatment** and the **same AI acceleration** *sustaining
500 uu/s and walking 13,187 uu.* Under this claim the clamp should have fired there too.
**Until that discriminator is found, §4.1 is `[I, strong]`, not `[M]`.**

### 4.1a ★ INDEPENDENT CONFIRMATION, RECOVERED FROM A DEAD VERIFIER'S OWN SCRIPTS

The first workflow's L1 verifier died to an API error **after** writing its scripts to
`scratchpad/s141/verify/V1/` and **before** writing any conclusion. Those scripts are read-only and
were written by different code than mine, so re-running them is a genuine second instrument. All of
its controls pass (DARK `0x5A6AC40` = 0/4096, folds 5/5, eight LIT controls). Results:

* `vcvzero.py` reproduces the CalcVelocity clamp block byte-for-byte and adds
  **`preds(0x035D6511) = ['0x35D650F']`** and **`preds(0x035D6520) = ['0x35D6518']`** — a
  **unique-predecessor chain**, so the `ZeroVector` write is reached from **only** the
  `jae 0x35d6534` at `0x035D650F`. That is an independent confirmation of §4.1's attribution.
* `vclamp.py` likewise gives **`preds(0x035ED998) = ['0x035ED996']`**,
  `preds(0x035ED9AC) = ['0x035ED9A9']`, `preds(0x035ED9B3) = ['0x035ED9AC']` — the §1 zeroing block
  is uniquely reached from the `ja` at `0x035ED996`.
* `vdom.py` independently reproduces **exactly the two TRUE EXITS** dominating gravity
  (`0x035EC881`, `0x035EC97C`), classifying the other four dominating branches as RECONVERGING — by
  successor-reachability rather than my edge-removal. Two methods, same answer.
* ★★ **`vdom2.py` — NEW, and it strengthens §1 and §3.** Re-rooted at the loop head `0x035EC967`
  (i.e. on a *second* substep iteration):
  ```
  Is the SizeSq2D clamp write 0x035ED9BB dominated by the gravity write 0x035ECCFB?  True
  Is the gravity write dominated by the clamp write?                                 False
  ```
  ⇒ **[M] gravity is integrated BEFORE the `SizeSq2D` clamp on every iteration.** The clamp can
  only zero the horizontal *afterwards*; it can never prevent gravity from having been applied.

### 4.1b ★★★★★ THE AXIS DISCRIMINATOR — one hypothesis now explains BOTH flights

§4.1 was published with an explicit hole: *"S140 T2 flight 3 measured the same bot, same treatment,
same acceleration, SUSTAINING 500 uu/s. Under this claim the clamp should have fired there too."*
The only bot-side difference between the two flights is the **kick axis** (X = +600 then, Z = −600
now). Here is why the axis matters.

**[M] Engine `PhysFalling` zeroes `Velocity.Z` before `CalcVelocity` and restores it after — but on
only ONE of its four `CalcVelocity` calls:**

| call site | `Velocity.Z = 0` before (`mov [rdi+0xf8], r13`, `r13 == 0` by reaching-defs) | `OldVelocity.Z` restored after | |
|---|---|---|---|
| `0x035ECB75` | **no** | **no** | **NOT bracketed** |
| `0x035ECBD8` | yes (`0x035ECBD1`) | yes (`0x035ECBDE movsd [rdi+0xf8], xmm14`) | **BRACKETED** |
| `0x035ED549` | **no** | **no** | **NOT bracketed** |
| `0x035ED5D5` | yes (`0x035ED5CE`) | not within 3 insns — **NOT ESTABLISHED** | — |

Two consequences, and they compose:

1. **A clamp firing on `0x035ECB75` or `0x035ED549` leaves `Velocity.Z` zeroed permanently** — there
   is no restore to undo it. That alone is a route to the observed all-three zero.
2. ★★ **Inside the BRACKETED call, a Z-only velocity is INVISIBLE.** `IsExceedingMaxSpeed` tests
   `Velocity.SizeSquared() > MaxInputSpeed² × 1.01`, and the bracket has just set `Z = 0`:
   * **flight 3, horizontal `(600,0,0)`:** `SizeSq = 360000 > 500² × 1.01 = 252500` ⇒ **TRUE** ⇒
     `xmm0 = |Velocity| = 600` ⇒ `comisd 600, 1e-4` ⇒ `jae` ⇒ **normal clamp, scaled to 500.**
     **That is exactly the sustained 500 uu/s that was measured.**
   * **tonight, vertical `(0,0,-600)`:** the bracket zeroes Z ⇒ `SizeSq = 0`, not exceeding ⇒
     **FALSE** ⇒ `xmm0 = xmm11 = MaxInputSpeed`. If `MaxInputSpeed < 1e-4` the **ZeroVector** branch
     is taken and all three components go to zero.

⇒ **ONE hypothesis retrodicts both flights, and the axis is the variable that switches it.**
**Grade: `[I]`** — the control-flow facts in the table are `[M]`, but the composition depends on
`MaxInputSpeed < 1e-4`, which has never been read.

★★ **AND IT GIVES S142 A CLEAN WITHIN-SESSION A/B ON ONE VARIABLE — THE AXIS.** Same arm, same
treatment, same session: kick the bot **horizontally** and it should sustain ~500 (reproducing
flight 3); kick it **vertically** and it should zero (reproducing tonight). Two bots, or two
consecutive kicks on one bot. **If both behave the same, this hypothesis is dead and so is §4.1.**

### 4.2 The read that settles it, and it is one read

**`AnalogInputModifier` and `GetMaxSpeed()` on the bot.** `MaxInputSpeed = MaxSpeed ×
AnalogInputModifier`; if it is below `1e-4` the clamp zeroes all three components.
⚠ **I did not read `AnalogInputModifier` this flight** — I added `GravityScale`,
`GravityDirection`, `MovementMode` and `+0x1001` to the free reads and **missed the one field the
mechanism now hinges on.** That is the honest gap. It is a read-only RPM read on a staged client.

---

## 5. T3-B — THE RANKED KICK TABLE

| # | route | address | grade | axis | needs | reachable today | class |
|---|---|---|---|---|---|---|---|
| **1** | **`PendingLaunchVelocity` @ `CMC+0x5C8`** → the game's own `HandlePendingLaunch` | setter `Launch` disp `0x748` = `0x35E7340`; handler disp `0x750`, Loki `0x55AEB60` | REAL | any | 24 bytes at `+0x5C8` | **yes** — its call site `0x035EA160` in engine `PerformMovement` **dominates** the `StartNewPhysics` call `0x035EB13A` (1461 → 181 reachable with it removed) | **one 24-byte DATA write, SELF-CLEARING** — the handler zeroes the field behind itself, forces `MOVE_Falling`, sets `bForceNextFloorCheck`. No `.text` write, no PI hook, no authority check on the path. ⚠ pending verification |
| **2** | **`GravityScale` @ `CMC+0x1A0` = `1.0f`** | — | REAL | **vertical only** | one 4-byte write | **yes — FLOWN TONIGHT, 23,189 uu** | one aligned DATA write, readback-verified. **This is what S132's dismount did.** |
| 3 | `SetComponentTickEnabled(true)` | CMC vtable disp `0x3E0` | REAL | none (enabler) | a call | yes; also reflected | **CALL-ONLY** |
| 4 | external `Velocity` write | — | — | any | 24 bytes | yes — S140 flight 3 | DATA write, **not** self-clearing; superseded by #1 |
| — | `LokiLaunchCharacter` | see `L5` §4.6 | REAL | any | heavier than it looks | — | not preferred |

**⇒ The T3-B answer the brief asked for — "a kick the GAME performs" — is #1.**
⚠ But note what tonight showed: **the bot's `Velocity` is zeroed within 250 ms however it is set**,
so on the bot #1 changes the *source* of the kick, not its *survival*. #1's value is that it is
game-native, authority-free and self-restoring; the zeroing (§4) is a separate, upstream problem.

### 5.1 THE ENGINE KICK SURFACE — graded by hand after lane L3 died

⚠ **Lane L3 (the engine kick surface) was lost to an API error and its output is absent.** An audit
against the brief's own target list showed that the surviving lanes had incidentally covered
`LaunchCharacter` / `Launch` / `HandlePendingLaunch` / `AddImpulse` / `SetMovementMode` (via L5's
image-wide census) but that **`DoJump`, `CheckJumpInput`, `CanJump`, `AddForce`, `AddRadialImpulse`
and root motion had 0 mentions across every surviving lane.** Graded here from the `.data`
`{name_ptr, exec_thunk, impl}` record table.

**Instrument control first:** the reader was validated against the repo's recorded triple —
`.data 0x09BC9AD0` = `{"GetRecentVelocity", thunk 0x0530C7E0, impl 0x0530AC10}` — and reproduced
both, confirming the layout is `name @+0x00, thunk @+0x08, impl @+0x10`.
⚠ **`.rdata` rows matching a name pointer are a DIFFERENT table** (their `+0x10` decodes as ASCII —
the next record's name). Only `.data` rows are records. My first pass printed those `.rdata` rows as
if they were records; that is defect **S141-i**.

| UFunction | exec thunk | impl | vtable disp | ULokiCMC | engine CMC | Loki override? |
|---|---|---|---|---|---|---|
| `CanJump` | `0x354E0D0` REAL | `0x3520580` **REAL** | — | — | — | — |
| `CanJumpInternal` | `0x354E140` REAL | `0x3520580` **REAL** | — | — | — | ⚠ **same impl as `CanJump`** |
| `AddForce` | `0x331DC90` REAL | `0x3317490` **REAL** (not a dispatch stub) | — | — | — | — |
| `AddImpulse` | `0x331E260` **DARK** | `0x3316C58` REAL → dispatch | `0x6F8` | `0x3604B60` REAL | `0x3604B60` | no |
| `AddRadialImpulse` | `0x331E770` **DARK** | `0x3316C88` REAL → dispatch | `0x718` | `0x35D3A30` REAL | `0x35D3A30` | no |
| `AddRadialForce` | `0x331E590` **DARK** | `0x3316CB8` REAL → dispatch | `0x738` | **`0x55AC000` REAL** | `0x35E3890` | **YES** |
| `Jump` | `0x354FB00` REAL | `0x3316B08` REAL → dispatch | `0x958` | **`0x55B2B20` REAL** | `0x35E6E00` | **YES** |
| `StopJumping` | `0x3554000` REAL | `0x3316B14` REAL → dispatch | `0x960` | `0x35F1DE0` REAL | `0x35F1DE0` | no |
| `SetMovementMode` | `0x3609180` REAL | `0x35D09F0` REAL → dispatch | `0x670` | **`0x55C0AC0` REAL** | `0x35FACD0` | **YES** |

**[M] ZERO FOLDS. Every impl and every resolved vtable target is REAL code.** So none of the engine
kick surface is stripped on this client.

★ **A free cross-validation of L5:** `SetMovementMode` resolves to vtable disp **`0x670`**, which is
exactly the displacement L5 independently transcribed in `HandlePendingLaunch`
(`0x55AEBE2 call [vt+0x670], edx = 3`). Two lanes, two routes, same number.

⚠ **Three exec thunks are DARK** (`AddImpulse`, `AddRadialImpulse`, `AddRadialForce`) — reflected but
never executed in any captured image, so the **S55 direct-thunk route cannot read them today** even
though the impl is REAL. Reach those through the vtable displacement instead.

⚠ **STILL NOT GRADED — the honest residual:** `DoJump`, `CheckJumpInput`, `LaunchCharacter` and
`HasAnimRootMotion` have **no whole ASCII name string** in `.rdata`/`.data`, so they are not in the
reflected record table by that name and need a different route (vtable neighbourhood, or an xref
from `HandlePendingLaunch` / `Jump`'s Loki override `0x55B2B20`). ⚠ `LaunchCharacter` **is**
`BlueprintCallable` in stock UE, so its absence as ASCII is itself worth one check — FK-13 records
that UHT names are prefix-stripped and that some are stored wide.

**Refuted / de-ranked as kick routes:** the S132 dismount as a *velocity* source (it is #2, gravity);
the `PhysFalling` `SizeSq2D` gate as a 3-D fixed point (it is 2-D); `ULokiCMC::PhysCustom`
(`0x55B88E0`, disp `0x990`) zeroes velocity but is not on our path (mode 7 only).

---

## 6. T3-C — THE PLAYER GENERALISATION: **half yes, and the other half was mis-designed**

**ARM K1 landed: `PLAYER storages written 3/3`** (`+0xF00` `1A3D4948080 → 1A236DFFF10`,
`+0xF08` `0 → 1A236E01710`, `+0xF10` `0 → 1A236E01F20`), and the attribute values are shared through
the CDO default subobject so both pawns necessarily see the same numbers.

**Q1 (Z / falling): YES, decisively.** See §2.
**Q2 (Y / sustaining): the arm CANNOT ANSWER IT, and that is my design error, not a null.**
The player's `Acceleration` read `(0,0,0)` at every sample — **it has no input driver at all** (the
AI wander driver belongs to the bot's `LokiBotController`). With no input, decay to zero is *correct
physics*, so the observed 600 → 0 does not discriminate "the clamp still fires" from "nothing is
sustaining it". **T3-C's sustaining half is NOT ESTABLISHED.** The fix is to give the player
acceleration — either drive `AddMovementInput`, or possess it with an AI controller — before reading
the decay.

---

## 7. T3-D — PER-INSTANCE ATTRIBUTE SET (scoped, NOT built)

Full design: `scratchpad/s141/lanes/L6-gas-per-instance.md` §B. Summary:

* **What ARM G does now:** borrows `Default__LokiPlayerState_HeroAffiliated`'s **default subobjects**
  (`AbilitySystemComponent @+0x3E8`, `AttributeSet @+0x3F0`, `AttributeSetHealth @+0x3F8`) into the
  pawn's `+0xF00/+0xF08/+0xF10`, then writes six floats at `FGameplayAttributeData +0x8` and `+0xC`
  inside that shared subobject. **Live offsets confirmed tonight:** `MoveSpeed @+0xF0`,
  `MaxMoveSpeed @+0x100`, `MaxAcceleration @+0x120`, `GroundFriction @+0x130`,
  `BrakingDecelerationWalking @+0x140`, `Mass @+0x170`.
* **Why it is process-wide:** the mutated object is a **CDO default subobject**, shared by every
  actor that borrows it, for the process lifetime, and nothing undoes it. It works because the
  consumers dereference the pawn's `+0xF08` **pointer** — not because a CDO poke propagates
  (it does not, for a native-owned property; that is the S137-refuted precedent).
* **The replacement:** construct a per-instance `ULokiAttributeSet` and register it on the pawn's own
  ASC. Routes graded in L6 §B.2–B.5 (`InitStats`, `AddSpawnedAttribute`,
  `GetOrCreateAttributeSubobject`, `SpawnedAttributes`). Use
  **`UGameplayStatics::SpawnObject`, not `NewObject`** — shipping has `DO_CHECK == 0`, so
  `NewObject`'s `ClassWithin` assert is compiled out and a wrong Outer would be **silent**.
* ⛔ **Do NOT spawn `LokiPlayerState_HeroAffiliated`** — S80 live-proved an instant client crash.
* **Deliberately not built this session.** Mixing an untested construction into the one available
  injection would have confounded the flight. Its value is removing a permanent CDO mutation, not
  changing the physics.

---

## 8. CORRECTIONS THIS SESSION PRODUCES

1. `docs/s140-t2-armj-THE-BOT-WALKS.md` §4b — the gate constant is `(double)(float)1e-4 × 10`
   (`UE_KINDA_SMALL_NUMBER × 10`), **not** `(double)(float)1e-3`. 4 independent derivations.
2. Same doc §4b — the open `[I]` on `Velocity.Z` is **settled NEGATIVELY**: it is not zeroed, so it
   does not explain the no-fall.
3. Same doc §2 — the PLAYER's non-fall is **self-inflicted** (`sp` zeroes `GravityScale`); the
   "GAS-treatment dependency in the MOVER" inference survives only for the horizontal decay.
4. `CLAUDE.md` / `docs/next-session-prompt-s141.md` — *"the physics step runs every frame"*
   over-reads S140 T2. The payload write is upstream of the engine call. **Tonight's fall is what
   establishes the chain runs.**
5. `CLAUDE.md` / `docs/s139-flight1-the-bot-is-not-special.md` — *"identical on EVERY structural
   field"* → *"every structural field that was read"*. `GravityScale` differs 1.0 vs 0.0.
6. `CLAUDE.md` — the `0x055B8838/3E/4A` block writes `[rsi+0x12F0]`/`[+0x1300]`, **not** `Velocity`.
   `ULokiCMC::PerformMovement` has **zero** `Velocity` writes.
7. `CLAUDE.md` — `GetMaxSpeed` (disp `0x4C8` = `0x0055ACB90`) and `GetMaxAcceleration`
   (disp `0x7D0` = `0x0055AC910`) are **two distinct functions**, not one shared `+0xC00` slot.
   ⚠ pending verification; L6 §4.
8. `docs/fk22-dropphase-reachability.md` / `docs/s132-dismount-settled.md` — `[mv+0x1A0] = 1.0f`
   is `GravityScale = 1.0`, and it is **why** that hero fell.
9. New offsets, all [M]: `CMC+0x1A0 GravityScale` · `+0x1D8/+0x1E8 GravityDirection` (offsets and
   arithmetic [M]; the *name* is [I, strong] — from the shape, not a UHT record) ·
   `+0x1F0..0x208` / `+0x210..0x228` the two gravity quats · `+0x1678` `ULokiCMC::PhysFalling`'s
   lateral fall-speed limiter (`-1.0f` = disabled) · `+0x5C8` `PendingLaunchVelocity`.

---

## 8a. ⚠ WHAT TIER 3 DID **NOT** CLOSE — audited against the brief's own task list

**T3-A: COMPLETE.** `[M]`, four independent derivations, plus a live pre-registered test.
**T3-D: COMPLETE** as specified (scoped, deliberately not built).

**T3-B: SUBSTANTIALLY complete, with a named residual.** Lane L3 — the engine kick surface — died to
an API error, and an audit showed that of the brief's explicit target list the surviving lanes had
**0 mentions** of `DoJump`, `CheckJumpInput`, `CanJump`, `AddForce`, `AddRadialImpulse` and root
motion. Nine of those were then graded by hand (§5.1 above): **zero folds, every impl REAL.**
**Still ungraded: `DoJump`, `CheckJumpInput`, `LaunchCharacter`, `HasAnimRootMotion`** — no whole
ASCII name string, so they need the vtable-neighbourhood route rather than the record table.

**T3-C: HALF complete, and the missing half is a design error rather than a null.** Q1 (does the
player fall) answered decisively YES. Q2 (does the GAS port let it *sustain* velocity) is **NOT
ESTABLISHED**: the player's `Acceleration` read `(0,0,0)` at every sample because it has no input
driver at all, so its 600 → 0 decay is correct physics and discriminates nothing. Fixing it means
giving the player acceleration first (`AddMovementInput`, or an AI controller), then re-reading.

**PROCESS: the adversarial-verification layer was lost entirely** — 7 of 12 agents in the main
workflow (every verifier plus the adjudicator) and then 0 of 4 in each of two focused retries, all
to API `529 Overloaded`. Partial recovery: the dead L1 verifier's own scripts were still on disk and
re-running them confirmed §1, §3 and §4.1's attribution from independently written code, and
produced the new gravity-before-clamp ordering fact. **Every claim in this document marked "pending
verification" has had exactly one derivation and should be read as `[I]`.**

⇒ **Carried into S142** (`docs/next-session-prompt-s142.md`): the axis A/B + the
`AnalogInputModifier` read (MOVE 1/1a), the `CalcVelocity` writer table (MOVE 2), T3-C's sustaining
half (MOVE 3), the four ungraded kick targets, and re-running the four verifiers if the API is
healthy.

---

## 9. INSTRUMENT DEFECTS FOUND THIS SESSION

| # | defect | how it showed |
|---|---|---|
| **S141-a** | **A byte-pattern displacement scanner with TWO off-by-ones** (back-scan started at 3 instead of 1; extent test used `<=` instead of `<`) and a `break` on the first matching alignment. | It reported "2 writes, 0 reads" for `CMC+0x1678` — a plausible-looking result that would have been recorded as a finding. **Caught only because I gave the scanner two KNOWN sites as positive controls and one was MISSED.** Fixed: start at 1, use `<`, and collect **all** alignments (over-report, then adjudicate). ⇒ ★ **a displacement scanner must be controlled on sites you already know, in the same run.** |
| **S141-b** | **A marker line that names a value it does not write.** `[SNP] BOT sentinel Velocity = (2^-10, 0, 0)` was a hardcoded string; ARM K wrote `(0, 0, -600)`. | The RAW/dec dump two lines later carried the truth, which is the only reason the flight was interpretable. Fixed to print `kShSentinel` itself. |
| **S141-c** | **My own §8 inference, refuted by my own follow-up before publication.** I wrote *"`+0x12B0` has two writers, S139 measured 1.0× not 2.0×, therefore the substep re-entry never happens and `PhysFalling` never reaches its tail — [I, strong]"*. | **[M] NEITHER `PhysFalling` ever calls `StartNewPhysics`**: vtable disp `0x720` is in neither function's call set, there is no direct call to `0x3600990`/`0x055C2430`, and neither has a tail jump outside its body. So the substep writer is unreachable there and 1.0× is expected **either way**. The measurement did not discriminate. ⇒ **`+0x12B0` can never be a `PhysFalling` receipt.** |
| **S141-d** | **A free read added, and the load-bearing one missed.** I extended the arm with `GravityScale`, `GravityDirection`, `MovementMode`, `+0x1001` and `+0x1678` — and not `AnalogInputModifier`, which is the field §4.1 now turns on. | ⇒ ★ when you add free reads, add the ones the *leading hypothesis* needs, not the ones the *current* hypothesis needs. |
| **S141-e** | **A control designed out of the experiment.** ARM K1 treated the player, which was the point — but it also removed the within-run specificity control ARM G was built around. Recorded in the source and in the pre-registration, and replaced by the **different-axis** design (bot Z, player Y), which held: no cross-contamination. | Not a defect in the result; a cost that had to be paid explicitly rather than silently. |
| **S141-f** | **`ULokiCMC+0x1678` is not a clean receipt** and I nearly used it as one. It has **seven** writers in the Loki CMC band (`0x0559E9F3`, `0x0559FDD4`, `0x055A7500`, `0x055A82C8`, `0x055B7CDF`, `0x055B9063`, `0x055BDD2E`), three of which write `-1.0f`. | Caught before the arm was built; the field is printed for information only. |

⚠ **AND ONE PROCESS FAILURE WORTH MORE THAN ANY OF THEM:** the 13-agent offline workflow lost
**all six adversarial verifiers and the adjudicator** to API `529 Overloaded` / server errors
(5 of 12 agents returned). The five lane analyses that landed are therefore **un-refuted** except
where they independently converge — which they do, 4-ways, on T3-A and the gate constant. A focused
4-verifier pass was re-run for the single-derivation claims; **anything still marked "pending
verification" in this document has had exactly one derivation and should be treated as `[I]`.**

---

## 10. HEALTH

Staged on **attempt 1** (`docs/s141-autostage.out.txt`). One injection (the 4th manual-map).
Client died at **~300 s** with **0 crashpad handoffs, 0 `Fatal`, no artifact of any kind** — the
FK-32 signature. The `0xDEAD` series is now **7 / 6 / 4 / 4 / 4 / 4 / 4** injections at
1144 / 334 / 350 / 318 / 320 / ~300 s. **Still no dose-response; 4 is firmly the modal count.**
★ Nothing was lost: the marker, both log backups and the full sample set were copied off as they
were produced. A `dumpimage` was attempted and failed — the client had already gone. **That is the
one thing that would have been worth having, and it is the cost of leaving the dump until last.**

**Regression gates, verified after every source edit:**
`botai 5e47c13cf7f0a158` · `gasattr 2fcc2536e21f18e3` · `gasattr-ctrl 4465ebc4d7168c03` —
**all three reproduce EXACTLY.**
**Arms:** `armk` RAW `8278c6031d05756c` (FLOWN) · `armk-ctrl` RAW `3f7323f6f4ba3e57` (built,
unflown, verified DISTINCT). Archived to `dumps/s141-arms/`.
⚠ `sentinel-big`/`gasattr-sentinel`/`sentinel-burst`/`sentinel-nogas` `.text` **has moved** — the
new free reads live inside `#if (KBSPSARMS & 0x200)`. Re-digest before reusing any of them.
