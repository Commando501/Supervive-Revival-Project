# S141 TIER 3 — LANE L1: sound CFG of ENGINE `PhysFalling`, every `Velocity` write, and what gates gravity

Image: `dumps/merged14.dump.exe`, ImageBase `0x7FF608F40000`, **FLAT verified (va==praw, 10/10 sections)**.
Instrument: `scratchpad/s141/tools/cfg.py` (provided harness, sound recursive descent) driven from
`scratchpad/s141/L1/*.py`. capstone 5.0.7. **Zero launches, zero injection, zero live-process access.**

---
## 0. MANDATORY CONTROLS — ALL PASS (`L1/controls.py`)

| control | expected | measured | verdict |
|---|---|---|---|
| DARK neg ctrl `ULokiRespawnComponent::Respawn 0x5A6AC40` | 0/4096 | **0/4096** | PASS |
| fold `0x0F7EC20` | `c20000` | `c20000` | PASS |
| fold `0x0F7EB50` | `33c0c3` | `33c0c3` | PASS |
| fold `0x0F7EB60` | `32c0c3` | `32c0c3` | PASS |
| fold `0x0B9E1F0` | `b001c3` | `b001c3` | PASS |
| fold `0x0FC6CF0` | `0f57c0c3` | `0f57c0c3` | PASS |
| LIT `0x035EC850` engine PhysFalling | >0 | 3610/4096 | PASS |
| LIT `0x055B89F0` ULokiCMC::PhysFalling | >0 | 3578/4096 | PASS |
| LIT `0x03600990` engine StartNewPhysics | >0 | 3705/4096 | PASS |
| LIT `0x035D5D20` engine CalcVelocity | >0 | 3660/4096 | PASS |
| LIT `0x035F4620` / `0x035F4770` quat helpers | >0 | 3687/4096 | PASS |

**Self-inflicted instrument defect, recorded:** my first dumper was named `L1/dis.py`, which shadows
Python's stdlib `dis` and made `import capstone` fail with a circular-import error. Renamed to
`pfdis.py`. Cost ~1 minute; noting it because a shadowed stdlib name fails in a way that looks like a
broken capstone install.

---
## 1. THE CFG (sound recursive descent from `0x035EC850`)

| metric | value |
|---|---|
| instructions | **1482** |
| calls | **79** (36 direct, 43 indirect) |
| **indirect jumps** | **0** |
| decode failures | **0** |
| noreturn candidates | 0 |
| `ret` instructions | **1** (`0x035EE592`) |
| pdata span | `0x035EC850..0x035EE593` (3 chained rows: `+0x37`, `+0x1CF0`, `+0x1C`) = **7491 bytes** |
| byte coverage | **7491 / 7491 = 100.00 %**, 0 gaps, 0 bytes outside the span |

⇒ **Because there are ZERO indirect jumps, every reachability answer in this lane is EXACT, not a
floor.** (The 43 indirect *calls* are opaque as to callee, but they do not affect intra-function
control flow — fallthrough is the only successor and none is a noreturn candidate.)

pdata rows came from `tools/strxref/index/pdata_union.csv`, **not** the image's own `.pdata` section,
which is all-zero in the dump (0 rows in `[0x35EC000,0x35EF000)`) — the documented dump property.

---
## 2. Q1 — EVERY WRITE TO `Velocity`

### 2.1 Which registers hold `&Velocity` — [M]

* `rdi = this`: defined at **`0x035EC87B mov rdi, rcx`** and nowhere else (only `push rdi`/`pop rdi`).
* `rsi = &Velocity`: the **sole** defining `lea` is **`0x035EC9AC lea rsi,[rdi+0xe8]`**.
  * **[M] it DOMINATES all 32 rsi-based Velocity writes (32/32, iterative dominators).**
  * The one redefinition, `0x035EE519 mov rsi,[rsp+0x918]`, is the epilogue restore of the caller's
    `rsi` (saved at `0x035EC92D mov [rsp+0x918], rsi`). **[M] forward reachability from it reaches
    0 of the 32 writes.**
* No sub-register aliasing: `esi/si/edi/di` are never written.
* `mov r8, rsi` occurs 5x — all are *argument passing* (`&Velocity` as an IN param), not aliases used
  for stores. No `lea` re-derives a Velocity pointer into another register.

**⇒ writes to `Velocity` are exactly {base `rsi`, disp 0/8/0x10} ∪ {base `rdi`, disp 0xE8/0xF0/0xF8}.**
Classification is from `operands[0].type == MEM` — **never `regs_access`**, per the S140T2-recorded
capstone defect that reports `movups` stores as reads.

### 2.2 The table — 36 write instructions

Guards = conditional branches that **dominate** the write **and** whose other successor cannot reach it.
`E` = `0x035EC881 jb` (DeltaTime < MIN_TICK_TIME `1e-6f`), `L` = `0x035EC97C jge`
(Iterations >= `MaxSimulationIterations` @CMC+0x3E4).

| # | rva | bytes | insn | fields | value written | guards |
|--:|---|---|---|---|---|---|
| 1 | `0x035ECA2C` | `0f1106` | `movups [rsi],xmm0` | X,Y | pending-impulse `[rdi+0xd88]` | E,L + `0x35ECA19 je` |
| 2 | `0x035ECA35` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | `[rdi+0xd98]` | same |
| 3 | `0x035ECB57` | `f20f1136` | `movsd [rsi],xmm6` | X | plane projection (`0x35F4620` result) | E,L |
| 4 | `0x035ECB5B` | `f2440f114608` | `movsd [rsi+8],xmm8` | Y | " | E,L |
| 5 | `0x035ECB61` | `f20f117e10` | `movsd [rsi+0x10],xmm7` | Z | " | E,L |
| 6 | `0x035ECB9C` | `f20f1106` | `movsd [rsi],xmm0` | X | post-`CalcVelocity` delta re-add | E,L |
| 7 | `0x035ECBA8` | `f20f114e08` | `movsd [rsi+8],xmm1` | Y | " | E,L |
| 8 | `0x035ECBB2` | `f20f114610` | `movsd [rsi+0x10],xmm0` | Z | " | E,L |
| 9 | **`0x035ECBD1`** | `4c89aff8000000` | `mov [rdi+0xf8],r13` | **Z** | **ZERO** (§2.3) | E,L |
| 10 | `0x035ECBDE` | `f2440f11b7f8000000` | `movsd [rdi+0xf8],xmm14` | Z | **restores** old Z (`xmm14`=`[rsi+0x10]`@`0x35ECA44`) | E,L |
| 11 | **`0x035ECCFB`** | `0f1106` | `movups [rsi],xmm0` | X,Y | **`NewFallVelocity` result — THE GRAVITY WRITE** | **E,L only** |
| 12 | **`0x035ECD06`** | `f20f114e10` | `movsd [rsi+0x10],xmm1` | **Z** | **`NewFallVelocity` result — THE GRAVITY WRITE** | **E,L only** |
| 13 | `0x035ECFBE` | `0f1106` | `movups [rsi],xmm0` | X,Y | air-control result via `0x35F4620` | E,L +4 |
| 14 | `0x035ECFC6` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | " | E,L +4 |
| 15 | `0x035ECFD4` | `f20f110e` | `movsd [rsi],xmm1` | X | alt air-control arm | E,L +4 |
| 16 | `0x035ECFD8` | `f20f115608` | `movsd [rsi+8],xmm2` | Y | " | E,L +4 |
| 17 | `0x035ECFDD` | `f20f114610` | `movsd [rsi+0x10],xmm0` | Z | " | E,L +4 |
| 18 | **`0x035ECFE2`** | `4c89aff8000000` | `mov [rdi+0xf8],r13` | **Z** | **ZERO**, *not* restored on this arm | E,L +4 |
| 19 | `0x035ED49A` | `0f1116` | `movups [rsi],xmm2` | X,Y | gravity-space Z-stripped velocity | E,L +5 |
| 20 | `0x035ED49D` | `f20f117610` | `movsd [rsi+0x10],xmm6` | Z | " | E,L +5 |
| 21 | `0x035ED52B` | `f20f1136` | `movsd [rsi],xmm6` | X | plane-projected | E,L +5 |
| 22 | `0x035ED52F` | `f20f117e08` | `movsd [rsi+8],xmm7` | Y | " | E,L +5 |
| 23 | `0x035ED534` | `f2440f114610` | `movsd [rsi+0x10],xmm8` | Z | " | E,L +5 |
| 24 | **`0x035ED5CE`** | `4c89aff8000000` | `mov [rdi+0xf8],r13` | **Z** | **ZERO** before lateral `CalcVelocity`@`0x35ED5D5` | E,L +5 |
| 25 | **`0x035ED658`** | `440f112e` | `movups [rsi],xmm13` | X,Y | **RESTORE** of snapshot taken at `0x35ED490` | E,L +5 |
| 26 | **`0x035ED65C`** | `f2440f117610` | `movsd [rsi+0x10],xmm14` | Z | **RESTORE** (`xmm14`=`[rsi+0x10]`@`0x35ED494`) | E,L +5 |
| 27 | `0x035ED946` | `0f1106` | `movups [rsi],xmm0` | X,Y | **Q4 block**, §4 | E,L +5 |
| 28 | `0x035ED949` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | **Q4 block** | E,L +5 |
| 29 | **`0x035ED9BB`** | `0f1106` | `movups [rsi],xmm0` | X,Y | **THE SizeSq2D CLAMP** — X,Y forced to 0 | E,L +2, **+ `0x35ED996 ja`** |
| 30 | **`0x035ED9C3`** | `f20f114e10` | `movsd [rsi+0x10],xmm1` | **Z** | **THE T3-A SITE** — §3 | E,L +2, **+ `0x35ED996 ja`** |
| 31 | `0x035EDAA6` | `0f1106` | `movups [rsi],xmm0` | X,Y | ledge/deflection result | E,L +5 |
| 32 | `0x035EDAA9` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | " | E,L +5 |
| 33 | `0x035EDE15` | `0f1106` | `movups [rsi],xmm0` | X,Y | slide-along-surface result | E,L +8 |
| 34 | `0x035EDE18` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | " | E,L +8 |
| 35 | `0x035EE3F9` | `0f1106` | `movups [rsi],xmm0` | X,Y | late/landing adjustment | E,L +11 |
| 36 | `0x035EE408` | `f20f114e10` | `movsd [rsi+0x10],xmm1` | Z | " | E,L +11 |

### 2.3 The three `Velocity.Z = 0` sites — [M] `r13 == 0` at all three

`r13` is **not** globally zero (it is reloaded as a pointer at `0x035ED00D movsxd r13,[rdi+0xd68]` /
`shl r13,4` / `add r13,r15`). I therefore ran a backward reaching-definitions walk rather than
assuming. The reaching defs at each site are **only** `xor r13d,r13d`:

* `0x035ECBD1` <- {`0x035EC92A xor r13d,r13d`, `0x035ED0AF xor r13d,r13d`}
* `0x035ECFE2` <- {`0x035EC92A`, `0x035ED0AF`}
* `0x035ED5CE` <- {`0x035EC92A`, `0x035ED0AF`}

**⇒ [M] all three write literal `Velocity.Z = 0`.** Sites 9 and 24 are the classic UE
`TGuardValue`-style *zero -> lateral `CalcVelocity` -> restore* pattern (site 9's restore is site 10;
site 24's restore is site 26, verified by reaching-defs: `xmm13 <- 0x035ED490 movups xmm13,[rsi]`,
`xmm14 <- 0x035ED494 movsd xmm14,[rsi+0x10]`).
**Site 18 (`0x035ECFE2`) has no restore on its arm** — it leaves `Velocity.Z == 0` and falls to
`0x035ECFE9`. A genuine asymmetry worth a second look, though it sits on the *air-control* arm, which
requires a non-zero `FallAcceleration` to be reached.

---
## 3. Q2 — IS `xmm1` ZERO AT `0x035ED9C3 movsd [rsi+0x10], xmm1`?

### **ANSWER: NO. `Velocity.Z` is NOT zeroed by this site. [M]**

The lead's read is **CONFIRMED in full**; I add the numeric proof.

```
0x035ED96E  call 0x35F4770        ; rcx=this, rdx=&[rbp+0x168] OUT, r8=rsi IN  -> RotateWorldToGravity(Velocity)
0x035ED973  movups xmm0,[rbp+0x168]        ; GravRelVel.X , .Y
0x035ED97A  movsd  xmm1,[rbp+0x170]        ; GravRelVel.Y
0x035ED982  mulsd  xmm0,xmm0
0x035ED986  mulsd  xmm1,xmm1
0x035ED98A  addsd  xmm1,xmm0                ; SizeSq2D = X*X + Y*Y   (Z at [rbp+0x178] NOT read)
0x035ED98E  comisd xmm1,[rip -> .rdata 0x077F5180]
0x035ED996  ja     0x35ED9C8                ; ABOVE the gate -> skip
0x035ED998  xorps  xmm0,xmm0
0x035ED9AC  movups [rbp+0x168],xmm0         ; *** 16 BYTES ONLY: X and Y ***
0x035ED9B3  call   0x35F4620                ; rdx=&[rbp+0x638] OUT, r8=&[rbp+0x168] IN
0x035ED9B8  movups xmm0,[rax]
0x035ED9BB  movups [rsi],xmm0               ; Velocity.X, Velocity.Y
0x035ED9BE  movsd  xmm1,[rax+0x10]
0x035ED9C3  movsd  [rsi+0x10],xmm1          ; Velocity.Z
```

**Step 1 — the 16-byte store leaves gravity-space Z alone. [M]**
`0x035F4770` writes its OUT at `[rdx]`, `[rdx+8]`, `[rdx+0x10]` (three stores, seen in its
disassembly), with `rdx = rbp+0x168` ⇒ the buffer is `X@+0x168, Y@+0x170, Z@+0x178`.
`0x035ED9AC movups [rbp+0x168], xmm0` is a **16-byte** store covering `+0x168..+0x177` = **X and Y
only**. `[rbp+0x178]` is untouched. Structurally decisive.

**Step 2 — `rax` is the OUT buffer. [M]** `0x035F462E mov rax, rdx`, and `rdx` is never redefined in
the callee (73 instructions, 0 calls, 0 indirect jumps). So `[rax+0x10]` is the rotated **Z**.

**Step 3 — the helper is exactly `FQuat::RotateVector`, and an identity quat is an exact
pass-through. [M], with a two-sided control.**
I transcribed all 73 instructions of `0x035F4620` into a faithful double-precision emulator
(`L1/quatemu.py`) and compared it against an independent reference
`T = 2*(Q x V); return V + W*T + (Q x T)`:

* **CONTROL 1 (positive):** max `|emu - reference|` over **2000 random normalized quats x random
  vectors** = **0** (exact, not epsilon).
* **CONTROL 2 (negative):** a 90-degree-about-Y quat gives `emu((1,2,3)) = (3.0, 2.0, -1.0000000000000007)`
  != `(1,2,3)` ⇒ the emulator is **not** a trivial pass-through, so CONTROL 1 is not vacuous.
* With `Q = identity`: input `(0,0,Z)` -> output `(0,0,Z)` with `OUT.Z == IN.Z` **bit-exactly** for
  `Z` in `{0, -4000, 123.456, -0.03}`.

**⇒ Under default gravity (gravity-down = world -Z ⇒ both quats identity), the round trip is a
pass-through and `0x035ED9C3` writes back the ORIGINAL `Velocity.Z` unchanged — a no-op.**

**Under a NON-identity gravity quat** the site is still not a zeroing: it is a **projection of
Velocity onto the gravity axis**. Measured with the same emulator at 30 degrees about X, input
`(0,0,-4000)` -> `(0.0, 2000.0, -3464.1016151377544)`. So world `Velocity.Z` *changes*, but never to
zero unless the gravity-space Z was already zero.

**⇒ The SizeSq2D clamp kills horizontal motion ONLY. It cannot explain a zero or non-falling
`Velocity.Z`.**

### 3.1 The gate constant — **the seed is right, `docs/s140-t2-armj-THE-BOT-WALKS.md` is wrong**

`.rdata 0x077F5180` = `00 00 00 cc 4d 62 50 3f` = **`0.0009999999747378752`**.

* `(double)(float)1e-4 * 10.0` = `0.0009999999747378752` -> **EQUAL**
* `(double)(float)1e-3` = `0.0010000000474974513` -> **NOT EQUAL**

⇒ it is `UE_KINDA_SMALL_NUMBER (float) x 10`, matching stock UE's
`if (Velocity.SizeSquared2D() <= UE_KINDA_SMALL_NUMBER * 10.f)`.
Escape threshold `|V_xy| > sqrt(gate)` = **0.031622776202254524**.
Sanity against the two flown sentinels: `2^-10` -> SizeSq `9.5367e-07` = **0.00095x** the gate
(zeroed); `600` -> SizeSq `360000` = **3.6e8x** the gate (kept). Both retrodicted.

### 3.2 Guard structure of the clamp — [M]
`0x035ED996 ja` is the sole entry: every node in `0x035ED998..0x035ED9C3` has **exactly one
predecessor**, and `0x035ED9C8` has exactly two (`0x035ED996` skip-arm, `0x035ED9C3` fallthrough).
A clean single-entry/single-exit diamond.

---
## 4. Q4 — the block at `0x035ED941..0x035ED94E`

```
0x035ED931  movups xmm0,[rax]              ; rax = &[rbp+0x2b0]  OR  &[rbp+0x2c8]
0x035ED934  movss  xmm13,[rip] = 1e-4f     ; *** float 9.999999747378752e-05 ***
0x035ED93D  comiss xmm9, xmm13             ; SINGLE-precision compare, xmm9 vs 1e-4f
0x035ED941  movsd  xmm1,[rax+0x10]
0x035ED946  movups [rsi],xmm0              ; Velocity.X, Velocity.Y
0x035ED949  movsd  [rsi+0x10],xmm1         ; Velocity.Z
0x035ED94E  ja     0x35EDAAE
```

**It is NOT a second copy of the clamp. [M] Three independent differences:**

1. **The writes are UNGUARDED by that compare.** `movups`/`movsd` do not touch EFLAGS, so the flags
   consumed by `ja` at `0x035ED94E` are those set by `comiss` at `0x035ED93D` — the two stores sit
   *between* the compare and its branch and execute on **both** arms. This is the compiler hoisting
   the compare, not a gate.
2. **Different constant, different precision, different operand.** `1e-4f` (**not** `1e-4*10`), a
   `comiss` (float) not `comisd` (double), against `xmm9` — a scalar float remaining-time/threshold
   value — not against a computed `SizeSq2D`.
3. **Different value written.** It writes a *whole* 3-component vector from a stack FVector at `rax`,
   one of two candidates selected by `0x035ED8C7 jne`:
   * `rax = rbp+0x2b0` — a component-wise **difference** (`subsd xmm6,xmm13` / `subsd xmm7,xmm12` /
     `subsd xmm8,xmm2` at `0x035ED8D9`/`0x035ED8E7`/`0x035ED8C2`);
   * `rax = rbp+0x2c8` — `{ [rsi] , [rdi+0xf0] , xmm8 }` i.e. `{Velocity.X, Velocity.Y, xmm8}`.

   The clamp, by contrast, writes a **constant zero** into X,Y and passes Z through.

**⇒ Q4 is a plain "assign this computed FVector to Velocity" (a velocity *recompute* from actual
displacement), and the neighbouring `comiss` belongs to the *following* branch.** Reading it as a
second clamp would be a real error: it would predict a zeroing that does not occur.

---
## 5. Q3 — WHY DOES A `MOVE_Falling` PAWN WITH `GravityScale 1.000` NOT FALL?

### 5.1 Where gravity is integrated — [M]

**`GetGravityZ`, vtable disp `0x4C0`, is called EXACTLY ONCE** (`0x035ECC21`), and
**`NewFallVelocity`, disp `0x7A0`, EXACTLY TWICE** (`0x035ECCEF`, `0x035ED617`).
Counts verified two ways: the CFG call map, and an independent raw byte scan for
`ff 9x a0 07 00 00` / `ff 90 c0 04 00 00` over the pdata span. Both agree.

> **CORRECTION TO `CLAUDE.md`.** It states *"`CalcVelocity` is called up to FOUR times per
> `PhysFalling` ... and `NewFallVelocity` (disp `0x7A0`) **THREE** times."* `CalcVelocity` is 4 —
> confirmed at exactly `0x035ECB75, 0x035ECBD8, 0x035ED549, 0x035ED5D5`. **`NewFallVelocity` is 2,
> not 3.** Two instruments, same answer.

The gravity vector is built at `0x035ECC05..0x035ECC75`:
```
0x035ECC05  movups xmm6,[rdi+0x1d8]     ; GravityDirection.X , .Y
0x035ECC12  movsd  xmm7,[rdi+0x1e8]     ; GravityDirection.Z
0x035ECC21  call   [rax+0x4c0]          ; GetGravityZ() -> float
0x035ECC31  cvtss2sd xmm1,xmm0
0x035ECC4D  mulsd xmm0,xmm1 / 0x035ECC51 mulsd xmm6,xmm1 / 0x035ECC55 mulsd xmm7,xmm1
0x035ECC59  xorps xmm0,xmm11 / 0x035ECC5D xorps xmm6,xmm11 / 0x035ECC71 xorps xmm7,xmm11  ; xmm11=-0.0 => NEGATE
0x035ECC61/69/75  movsd [rbp+0x108/0x110/0x118]      ; Gravity
```
i.e. **`Gravity = -GravityDirection * GetGravityZ()`**, the stock UE 5.4 line. `xmm11 = -0.0` holds on
all three predecessors of `0x035ECC05` (`0x035EC970` and `0x035ECBFC` both load it). `[rbp+0x108]` is
passed as `r9` to `NewFallVelocity` at `0x035ECCEF`.

### 5.2 **[M] THE GRAVITY APPLICATION IS UNCONDITIONAL.**

Writes 11/12 (`0x035ECCFB`, `0x035ECD06`) — the only place a `NewFallVelocity` result reaches
`Velocity` — are dominated by exactly **six** conditional branches, of which **four are reconverging
diamonds** (their other successor still reaches the write, and their targets `0x35EC9A5`, `0x35ECA3A`,
`0x35ECC05`, `0x35ECCD1` are all forward and *before* the write, so reconvergence is genuine and not
via the loop back-edge). Only **two** are true exits:

| guard | test | meaning |
|---|---|---|
| `0x035EC881 jb 0x35EE577` | `comiss xmm6, 1e-6f` (`0x035EC873`) | bail if `DeltaTime < MIN_TICK_TIME` |
| `0x035EC97C jge 0x35EE507` | `cmp r12d, [rdi+0x3e4]` | bail if `Iterations >= MaxSimulationIterations` |

**Neither depends — directly or transitively — on horizontal velocity, on the `SizeSq2D` gate at
`0x035ED98E`, or on `Acceleration`.** The `SizeSq2D` gate is ~3.3 KB *downstream* of the gravity write
and cannot reach it except through the loop back-edge `0x035ED9E8 jmp 0x35EC967`, which re-enters at
the loop head *above* the gravity site — so even on a second iteration gravity is applied again
before the clamp.

**The second `NewFallVelocity` (`0x035ED617`) never touches `Velocity`. [M]** Its result is copied to
a stack buffer (`0x035ED64B movups xmm3,[rax]` -> `0x035ED64E movups [rsp+0x78],xmm3`) and `Velocity`
is immediately **restored** from the snapshot at `0x035ED490`/`0x035ED494` (writes 25/26). That is the
`VelocityNoAirControl` computation. *I initially mislabelled `0x035ED658` "GRAVITY#2"; reaching-defs
on `xmm13`/`xmm14` refuted it.*

### 5.3 ⇒ **NOTHING IN THIS FUNCTION EXPLAINS THE NON-FALL.** Where to look next.

I checked the two Loki overrides on the gravity path rather than merely naming them:

**(a) `ULokiCMC::GetGravityZ` `0x055AB8C0` (REAL, 45 insns) — NOT the cause at `MOVE_Falling`. [M]**
It has a `return 0.0f` arm, but it is gated on `cmp byte [rcx+0x231], 7` — **`MovementMode ==
MOVE_Custom`** (this build's `MOVE_Custom == 7`; `CMC+0x231` is corroborated as `MovementMode` by
CLAUDE.md's `IsDashing 0x035E6810 = cmp byte [rcx+0x231],6`). With `MovementMode == 3` the very first
branch `0x055AB8D4 jne 0x55AB929` takes the **general path**, which tail-computes the engine value
`0x035E3650` and returns it unmodified (the second `cmp byte [rbx+0x231],7` at `0x055AB933` also
falls to the plain return). **Loki does not zero gravity while falling.**

**(b) `ULokiCMC::NewFallVelocity` `0x055B6AD0` (REAL, 26 insns) — a PASS-THROUGH at `MOVE_Falling`. [M]**
`0x055B6AEC call 0x035E8B00` does the engine work, then `0x055B6AF1 cmp byte [rdi+0x231],7` /
`jne 0x55B6B2E` -> `mov rax,rbx; ret`. The only Loki-specific clamp (a `minsd`/`maxsd` on Z using
`[rdi+0x1140]`) is behind `MovementMode==7 && CustomMovementMode==1`. **Not reached at mode 3.**

**⇒ RANKED SURVIVORS (all outside engine `PhysFalling`):**

1. **`GravityDirection` at `CMC+0x1D8` (X), `+0x1E0` (Y), `+0x1E8` (Z) — FVector of doubles.**
   `Gravity = -GravityDirection * GetGravityZ()`. **If `GravityDirection == (0,0,0)` then
   `Gravity == (0,0,0)` and a `MOVE_Falling` pawn with `GravityScale 1.000` does not fall — while
   every other measurement stays exactly as observed.** Stock UE default is `(0,0,-1)`.
   **This is a single read-only RPM read and it appears NOWHERE in `CLAUDE.md`.**
   Grade of the *identity*: **[I, strong]** — derived from the arithmetic shape matching UE 5.4's
   `-GetGravityDirection() * GetGravityZ()`, not from a UHT property record. Settle it by looking up
   `GravityDirection` in `UCharacterMovementComponent`'s `PropPointers`, or read it live.

2. **Engine `UMovementComponent::GetGravityZ` `0x035E3650` has a `return exactly 0.0f` branch that is
   NOT recorded anywhere in this repo. [M]**
   ```
   0x035E365C  call [rax+0xce0]      ; virtual -> bool
   0x035E3662  test al,al / je 0x35E3678
   0x035E3666  cmp byte [rbx+0x1001],0 / jne 0x35E3678
   0x035E366F  xorps xmm0,xmm0 ; ret          <-- ZERO GRAVITY
   0x035E3678  call 0x03632E20 ; mulss xmm0,[rbx+0x1a0]   <-- normal: worldGravityZ * GravityScale
   ```
   Two cheap reads settle it: `byte [CMC+0x1001]`, and what vtable disp `0xCE0` returns.
   (`CMC+0x1A0` is the float multiplied in — consistent with `GravityScale`.)

3. **Whether engine `StartNewPhysics`'s jump table actually dispatches case 3 to `PhysFalling`.**
   **Scope caveat that matters:** S140 Tier 2 measured *`ULokiCMC::StartNewPhysics` runs* via the
   payload write at `0x055C244F`, which is at the **top of the Loki wrapper**, *before* it calls the
   engine Super. **That measurement does not establish that engine `StartNewPhysics` reached case 3
   and called `PhysFalling`.** If `PhysFalling` is never entered, every result in this lane is
   vacuous for the live pawn — and that would also explain the non-fall with no other assumption.
   `call [rax+0x830]` occurs **0 times** inside `PhysFalling` itself (checked), so the dispatch lives
   entirely in `StartNewPhysics` — another lane's function, but this is the load-bearing hand-off.
   **Exact target, verified this lane:** the 8-entry table at `.text 0x03600BF8` holds absolute RVAs;
   **case 3 = `0x03600AC5`**, and the sole `call [rXX+0x830]` in engine `StartNewPhysics` is at
   **`0x03600AD1`** (12 bytes into that case body). That single call is the entry to everything
   analysed here.

**A constraint any successor hypothesis must satisfy:** S140 flight 3 showed that after ONE write of
`Velocity=(600,0,0)` the pawn fell at terminal velocity (`Vz` pinned `-4000`). So gravity is
demonstrably **non-zero** in that state. Hypotheses 1 and 2 (a statically-zero gravity vector) do not
by themselves explain that reversal; **hypothesis 3 does** — if a zero `Velocity` prevents
`PhysFalling` from being entered at all, the kick is exactly what lets the whole chain run.
**⇒ I rank hypothesis 3 highest despite it being outside my function.**

---
## 6. Q5 — SOUND EXIT / EARLY-OUT ENUMERATION

Backward reachability `R` over the instruction graph; exits = edges `u->v` with `u` in `R`, `v` not in
`R`, `u` not a call. Computed for three targets:

| target | size of R | exit edges | **backward exit edges** | dead-ended nodes in R |
|---|---:|---:|---:|---:|
| first Velocity write `0x035ECA2C` | 1418 | **15** | **0** | 0 |
| gravity site `0x035ECCEF` | 1418 | **15** | **0** | 0 |
| clamp write `0x035ED9BB` | 1418 | **15** | **0** | 0 |

The 15 exits (identical for all three, because the whole body is one loop reachable from the back-edge
`0x035ED9E8 jmp 0x35EC967`):

`0x035EC881 jb ->0x35EE577` · `0x035EC97C jge ->0x35EE507` · `0x035ED27D je ->0x35EE507` ·
`0x035ED2AC jne ->0x35EE4B7` · `0x035ED303 jne ->0x35EE492` · `0x035ED3E5 jne ->0x35EE433` ·
`0x035ED415 je ->0x35EE507` · `0x035ED429 je ->0x35EE507` · `0x035ED9DB jb ->0x35EE507` ·
`0x035EDB8A jne ->0x35EE479` · `0x035EDBAD je ->0x35EE507` · `0x035EDBC1 je ->0x35EE507` ·
`0x035EE125 jne ->0x35EE45B` · `0x035EE16F jne ->0x35EE45B` · `0x035EE181 je ->0x35EE45B`

**[M] ZERO backward exit edges** — every bail jumps forward into the epilogue region
`0x035EE433..0x035EE577`. The function has exactly **2** backward edges total, and neither is an exit
(they are the substep loop back-edges).

**Do not confuse the two questions.** `R`-based exits answer *"what can bail anywhere in the loop"*
(15). **Dominance** answers *"what must be passed to reach this write"* — and for the gravity write
that is only **2** (§5.2). Because `MaxSimulationIterations` is measured **= 1**, the loop body
executes at most once per call, so the dominance answer is the operative one.

---
## 7. CORRECTIONS THIS LANE PRODUCES

1. **`docs/s140-t2-armj-THE-BOT-WALKS.md` / `CLAUDE.md`: the gate constant identity is wrong.**
   `.rdata 0x077F5180` = `0.0009999999747378752` = `(double)(float)1e-4 * 10`, **not**
   `(double)(float)1e-3` (= `0.0010000000474974513`). The escape threshold `0.0316227762...` is
   unaffected.
2. **`CLAUDE.md`: "`NewFallVelocity` (disp `0x7A0`) THREE times" -> it is TWO** (`0x035ECCEF`,
   `0x035ED617`), by CFG and by independent byte scan. `CalcVelocity` = 4 is correct.
3. **Only ONE of the two `NewFallVelocity` calls reaches `Velocity`.** The other feeds
   `VelocityNoAirControl` on the stack and `Velocity` is restored immediately after.
4. **New, unrecorded: engine `GetGravityZ 0x035E3650` has a `return 0.0f` arm** gated on virtual disp
   `0xCE0` + `byte [CMC+0x1001]`.
5. **New, unrecorded: `GravityDirection` at `CMC+0x1D8/+0x1E0/+0x1E8`** is the other multiplicand of
   the gravity vector and has never been read.
6. **Scope caveat on S140 Tier 2:** "StartNewPhysics runs" was measured at the *Loki wrapper*, which
   does not establish that engine `StartNewPhysics` dispatched case 3 into `PhysFalling`.

## 8. NOT ESTABLISHED
* Whether `PhysFalling` is entered at all on the live pawn. **Settles it:** determine whether engine
  `StartNewPhysics 0x03600990` reaches `0x03600AC5 call [rax+0x830]` (case 3 of the table at
  `0x03600BF8`), or instrument the entry.
* Live values of `GravityDirection` (`CMC+0x1D8..0x1E8`), `byte [CMC+0x1001]`, and the disp-`0xCE0`
  virtual's return. **All three are read-only RPM, no injection.**
* Whether the gravity quats (`CMC+0x1F0..0x208`, `+0x210..0x228`) are identity live. Q2's answer is
  proven for identity and characterised (a gravity-axis projection, still not a zeroing) otherwise.
* Why write 18 (`0x035ECFE2`) leaves `Velocity.Z = 0` with no restore on its arm; it is on the
  air-control path, which needs non-zero `FallAcceleration` to be reached.
* Callee identity for the 43 indirect calls other than those resolved via the two vtables.
