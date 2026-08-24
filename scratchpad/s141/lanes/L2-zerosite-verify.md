# S141 TIER 3 — LANE L2
# Independent re-derivation of the zero site, the gate constant, and the quat round trip

Image: `dumps/merged14.dump.exe` (ImageBase `0x7FF608F40000`, FLAT verified: RVA == file offset).
All work OFFLINE. Zero launches, zero injection, zero writes to any live process.

**Instruments are my own.** I wrote `scratchpad/s141/lanes/L2tools/l2pe.py` (PE reader) and
`l2dis.py` (recursive-descent CFG + linear reader) from scratch. I did **not** import
`peimg.py` or `cfg.py`. capstone 5.0.7.

---

## 0. MANDATORY CONTROLS — ALL PASS

```
[C0] flat: True   ImageBase 0x7FF608F40000   10 sections, .text va==praw==0x1000
[C1] DARK ctrl  ULokiRespawnComponent::Respawn 0x5A6AC40  page_nonzero = 0/4096   PASS (dark)
[C2] fold 0x0F7EC20 expect c20000   got c20000    PASS
[C2] fold 0x0F7EB50 expect 33c0c3   got 33c0c3    PASS
[C2] fold 0x0F7EB60 expect 32c0c3   got 32c0c3    PASS
[C2] fold 0x0B9E1F0 expect b001c3   got b001c3    PASS
[C2] fold 0x0FC6CF0 expect 0f57c0c3 got 0f57c0c3  PASS
[C3] LIT 0x035EC850 ENGINE PhysFalling           3610/4096  PASS
[C3] LIT 0x035ED973 the SizeSq2D block           3573/4096  PASS
[C3] LIT 0x035F4620 quat helper A                3687/4096  PASS
[C3] LIT 0x035F4770 quat helper B                3687/4096  PASS
[C3] LIT 0x055B89F0 ULokiCMC::PhysFalling        3578/4096  PASS
[C3] LIT 0x035D5D20 ENGINE CalcVelocity          3660/4096  PASS
[C4] .rdata 0x077F5180 page 1960/4096, section .rdata
```

**Extra structural control the seed did not ask for, and it passed:** my CFG of engine
`PhysFalling` from `0x035EC850` is fully contiguous — **1482 instructions, 0 undecodable,
0 non-contiguous joins, exactly ONE `ret` at `0x035EE592`.** `0x035EE592 + 1 = 0x035EE593`,
which reproduces the seed's stated pdata extent `0x35ec850..0x35ee593` **exactly**, from a
completely independent instrument. `.pdata` in this image is all zeros, so this was derived
without it.

---

## 1. Q1 — THE GATE CONSTANT. The session lead is RIGHT; the doc is WRONG.

Raw bytes at `.rdata 0x077F5180` (32):

```
00 00 00 cc 4d 62 50 3f | 00 00 00 00 80 84 0e 41 | 42 00 61 00 63 00 6b 00 ...
```

```
gate (double)  = 0.00099999997473787516356
bits           = 0x3F50624DCC000000
hex()          = 0x1.0624dcc000000p-10
```

Adjudication, arithmetic done with `struct`:

| candidate | value | bits | match |
|---|---|---|---|
| **(a)** `(double)(float)1e-3` | 0.0010000000474974513054 | `0x3F50624DE0000000` | **NO** |
| **(b)** `(double)(float)1e-4 * 10.0` | 0.00099999997473787516356 | `0x3F50624DCC000000` | **YES [M]** |
| (c) `double` literal `1e-3` | 0.0010000000000000000208 | `0x3F50624DD2F1A9FC` | NO |
| — `(double)(float)1e-4` alone | 9.9999997473787516356e-05 | `0x3F1A36E2E0000000` | (n/a) |
| — `(double)(float)(1e-4f*10.0f)` | 0.00099999993108212947845 | — | NO |

> **VERDICT: (b).** The constant is `UE_KINDA_SMALL_NUMBER` (the *float* 1e-4, promoted to
> double) multiplied by `10.0` **in double precision** — i.e. the C++ source is
> `UE_KINDA_SMALL_NUMBER * 10.` evaluated as a double. This is stock UE `PhysFalling`'s
> `Velocity.SizeSquared2D() <= UE_KINDA_SMALL_NUMBER * 10.f` guard.
>
> **`docs/s140-t2-armj-THE-BOT-WALKS.md`'s assertion that it is `(double)(float)1e-3` is
> REFUTED.** The two differ in the mantissa (`...DE0000000` vs `...DCC000000`) — a real
> numeric difference, not a formatting one. The recorded decimal string
> `0.0009999999747378752` in that doc is *correct*; only its **identification** is wrong.

**Free internal corroboration of (b) from the bit pattern alone:** `(double)(float)1e-4` has
its low **29** mantissa bits zero (the signature of a float widened to double). Multiplying by
10 (= 2·5, and 5 needs 3 bits) leaves the low **26** bits zero — and the measured constant is
`0x...CC000000`, exactly 26 trailing zero bits. Candidate (c), a true double literal, ends
`D2F1A9FC` with no trailing zeros at all. The bit pattern is self-identifying.

### Escape threshold

```
sqrt(gate) = 0.031622776202254523903      (approx 0.0316228 uu/s of horizontal speed)
```

Cross-checks against the two S140 flight observations, both retrodicted:

* `2^-10 = 0.0009765625` -> ratio to threshold **0.0309** -> BELOW -> zeroed. (ARM H's inert poison.)
* `600` -> ratio **18973.7** -> ABOVE -> kept. (Flight 3, the bot walked.)

### `0x077F5188` = `250000.0` (double) — and it IS referenced, once

The lead saw `250000.0` there; confirmed, `0x410E848000000000`. It is a **separate adjacent
constant-pool slot**, not part of the gate. It has **exactly one** validated reference in
decrypted `.text`: `0x01C3D460 f20f593d... mulsd xmm7, qword ptr [rip] -> 0x077F5188` — a
different subsystem entirely, ~28 MB away from `PhysFalling`. Nothing on the movement path
touches it. (The constant pool ends immediately after: `0x077F5190` begins the UTF-16 string
`"Backstop"`.)

### The gate slot is read as a DOUBLE by every real reference — 7/7

Full rip-relative reference scan over `.text` (vectorised; the `disp32` search is exact, then
each hit re-validated by decode):

```
0x01C33CB3  maxsd  xmm10, qword [rip]->0x077F5180    reads 8 bytes
0x035E428B  maxsd  xmm6,  qword [rip]->0x077F5180    reads 8 bytes
0x035E4297  maxsd  xmm7,  qword [rip]->0x077F5180    reads 8 bytes
0x035E43A2  maxsd  xmm1,  qword [rip]->0x077F5180    reads 8 bytes
0x035E43BA  maxsd  xmm1,  qword [rip]->0x077F5180    reads 8 bytes
0x035ED98E  comisd xmm1,        [rip]->0x077F5180    <-- THE GATE
0x03604476  movsd  xmm9,  qword [rip]->0x077F5180    reads 8 bytes  (inside engine StartNewPhysics)
```

Seven independent readers, every one an 8-byte scalar-double access. WARNING: **this is a
FLOOR** — `.text` is ~55 % decrypted, so dark code may hold more.

> WARNING **INSTRUMENT DEFECT I HIT AND CAUGHT — a disp32 back-scan validator strips SSE
> prefixes and reports the WRONG mnemonic and WRONG operand width.** My first pass reported
> those five as `maxps xmm, xmmword ptr` — i.e. **16-byte** reads, which would have made the
> slot look like a 4-float vector `(-3.355e7, 0.814, 0, 8.907)` and cast doubt on the whole
> double interpretation. Cause: scanning *backward* from the disp32 finds the shorter
> `0F 5F 35 ...` (`maxps`, 7 B) before the real `F2 0F 5F 35 ...` (`maxsd`, 8 B), and both
> "validate". Settled by a sound decode: at `0x035E428B` the real instruction is `maxsd`.
> **Fix: longest-match-wins, and confirm against a sound CFG.** The same alias made
> `comisd` (8 B, `66 0F 2F`) print as `comiss` (7 B, `0F 2F`) at `0x035ED98F` — one byte off,
> half the operand width, and it looks entirely plausible.

> WARNING **Second instrument note: capstone 5.0.7 mis-sizes `comisd` as `xmmword ptr` /
> `op.size == 16`.** Per the ISA, `66 0F 2F /r` is `COMISD xmm1, xmm2/m64` — it reads
> **8 bytes**. Do not quote capstone's operand size for `comis*`/`ucomis*`. It changes nothing
> here (only the low 8 bytes are compared, and they are the gate), but a successor reading
> "xmmword" could conclude the constant is 16 bytes wide.

---

## 2. Q2 — WIDTH OF THE ZEROING STORE. X and Y are zeroed. Z SURVIVES.

From the **encoding**, not the mnemonic string:

```
0x035ED9AC   0f 11 85 68 01 00 00     movups xmmword ptr [rbp+0x168], xmm0
             ^^^^^ 0F 11 /r  = MOVUPS xmm2/m128, xmm1   ->  m128  ->  16 BYTES
             op0 = MEM, size = 16, base = rbp, disp = 0x168
             (write classified from operands[0].type == MEM, NOT from regs_access)
```

The vector at `[rbp+0x168]` is an **`FVector` of doubles, 24 bytes**, proven from its own uses
in the same block:

```
0x035ED973  movups xmm0, [rbp+0x168]   ; 16 B load, only the LOW double is consumed
0x035ED97A  movsd  xmm1, [rbp+0x170]   ;  8 B load  -> Y is at +0x170, so doubles, stride 8
0x035ED982  mulsd  xmm0, xmm0          ; scalar-double  X*X
0x035ED986  mulsd  xmm1, xmm1          ; scalar-double  Y*Y
0x035ED98A  addsd  xmm1, xmm0          ; SizeSq2D = X*X + Y*Y   (no Z term)
```

and independently from the callee ABI (section 3): both quat helpers read `movups [r8]` (16 B)
**plus** `movsd [r8+0x10]` (8 B) = 24 bytes, and write 24 bytes.

Therefore:

| slot | component | zeroed by `0x035ED9AC`? |
|---|---|---|
| `[rbp+0x168]` | X | **YES** (bytes 0-7 of the 16) |
| `[rbp+0x170]` | Y | **YES** (bytes 8-15 of the 16) |
| `[rbp+0x178]` | **Z** | **NO — outside the store** |

**And nothing else touches it.** An exhaustive operand scan over all 1482 CFG instructions for
any `[rbp + 0x160..0x188]` reference gives, in the whole function, only:

```
0x035ED964  lea    rdx, [rbp+0x168]                       OUT ptr -> callee 0x35F4770
0x035ED973  movups xmm0, [rbp+0x168]        16 B  read
0x035ED97A  movsd  xmm1, [rbp+0x170]         8 B  read
0x035ED99B  lea    r8,  [rbp+0x168]                       IN  ptr -> callee 0x35F4620
0x035ED9AC  movups [rbp+0x168], xmm0        16 B  WRITE   <-- the only write
```

(`[rbp+0x160]`, `[rbp+0x180]`, `[rbp+0x184]` are unrelated neighbouring locals.)

> **[M] `[rbp+0x178]` is written by exactly one thing in the entire flow: the callee at
> `0x035F4770`, through its `rdx` out-pointer. No instruction of `PhysFalling` ever writes it,
> and the zeroing store provably cannot reach it.**

**Branch semantics of the gate** (`ja` = CF=0 and ZF=0, i.e. strictly-above-and-ordered):

| SizeSq2D | `ja` taken | effect |
|---|---|---|
| `0` (the fixed point) | no | **falls through -> the zeroing write EXECUTES** |
| just below gate | no | zeroing executes |
| **== gate exactly** | no | zeroing executes (the test is `<=`) |
| just above gate | yes | skipped, Velocity kept |
| **NaN** | no (comisd sets ZF=PF=CF=1) | **zeroing executes** |

---

## 3. Q3 — THE QUAT HELPERS. Offsets CONFIRMED; the seed's direction LABELS are REFUTED.

### 3.1 Both return their `rdx` out-buffer — CONFIRMED

Sound CFG of each: **73 instructions, 0 undecodable, single `ret`, no calls**, extents
`0x035F4620..0x035F476E` and `0x035F4770..0x035F48BE`.

Each has **exactly one** definition of `rax`, at instruction #3:

```
0x035F462E   48 8b c2   mov rax, rdx
0x035F477E   48 8b c2   mov rax, rdx
```

Nothing else writes `rax`. => **[M] both return the OUT buffer.** CONFIRMED.

### 3.2 Which quat each reads — CONFIRMED, matching the seed exactly

```
helper A  0x035F4620 : [rcx+0x1F0] [rcx+0x1F8] [rcx+0x200] [rcx+0x208]   (4 doubles = 32 B)
helper B  0x035F4770 : [rcx+0x210] [rcx+0x218] [rcx+0x220] [rcx+0x228]   (4 doubles = 32 B)
both      : read  movups [r8] (16 B) + movsd [r8+0x10] (8 B)  = 24 B IN vector
both      : write movsd [rdx], [rdx+8], [rdx+0x10]            = 24 B OUT vector
```

### 3.3 They are the SAME operation on different quats — [M] by byte diff

Over 335 bytes the two functions differ in **exactly 6 bytes**, and every one is a byte of a
quat displacement (`+0x015`, `+0x025`, `+0x04A/4B`, `+0x05C/5D`, each `+0x20` apart).
**The arithmetic is byte-identical.** => neither is `FQuat::UnrotateVector` (which negates the
vector part and would differ in the arithmetic); both are `FQuat::RotateVector`, on different
quats. The math is the standard `v + 2w(q x v) + 2(q x (q x v))`: `xmm11`/`xmm8`/`xmm5` are
built as the three components of `q_v x v`, doubled (`addsd xmm,xmm`), then combined with `w`.

### 3.4 Are these CMC fields? — YES, [M]

In engine `PhysFalling`, `rdi` has **exactly one definition**: `0x035EC87B mov rdi, rcx`
(plus `push rdi` / `pop rdi`). Both call sites do `mov rcx, rdi` immediately before the call
(`0x035ED96B`, `0x035ED9A9`). => `rcx` at the callee **is the CMC `this`**. So `+0x1F0` and
`+0x210` are `UCharacterMovementComponent` instance fields.

### 3.5 UPROPERTY names — they exist, and I MEASURED the offsets

`tools/asdump/out/binds_members.csv:28408-28409` declares both on
`UCharacterMovementComponent`:

```
property 4  FQuat WorldToGravityTransform
property 5  FQuat GravityToWorldTransform
```

Declaration order is not an offset. I decoded the UHT `FPropertyParams` records directly
(`ArrayDim` @ record+0x30 : u16, `Offset` @ record+0x32 : u16), and walked the **contiguous
record table** so that every row quoted comes from one table:

```
 -1  rec@0x07FAF660  GravityDirection            ArrayDim=1 Offset=0x1D8    (FVector, 24 B)
 +0  rec@0x07FAF6A0  WorldToGravityTransform     ArrayDim=1 Offset=0x1F0    (FQuat,  32 B)
 +1  rec@0x07FAF6E0  GravityToWorldTransform     ArrayDim=1 Offset=0x210    (FQuat,  32 B)
 +2  rec@0x07FAF720  MovementMode                ArrayDim=1 Offset=0x231
 +3  rec@0x07FAF760  CustomMovementMode          ArrayDim=1 Offset=0x232
 +5  rec@0x07FAF7E0  NetworkSmoothingMode        ArrayDim=1 Offset=0x233
 +6  rec@0x07FAF820  GroundFriction              ArrayDim=1 Offset=0x234
```

The layout closes perfectly: `0x1D8 + 24 = 0x1F0`; `0x1F0 + 32 = 0x210`; `0x210 + 32 = 0x230`.

**FIVE independent passing controls on the decoder, all from seed-known [M] offsets:**

| control | decoded | seed says | |
|---|---|---|---|
| `MinAnalogWalkSpeed` | `0x290` | `CMC+0x290` | PASS |
| `Acceleration` | `0x328` | `CMC+0x328` | PASS |
| `MaxSimulationTimeStep` | `0x3E0` | `CMC+0x3E0` | PASS |
| `MaxSimulationIterations` | `0x3E4` | `CMC+0x3E4` | PASS |
| `MovementMode` | `0x231` | `IsDashing 0x035E6810 = cmp byte [rcx+0x231],6` | PASS |

WARNING Name-collision hygiene: `MaxSimulationTimeStep` also appears at `0x198` and `0x1CC` in
**other** classes' record tables. Only the row in the CMC table is quoted. Same for
`Acceleration` (8 tables) and `GravityScale` (8 tables).

> ### [M] CONFIRMED: `helper A 0x035F4620` reads **`WorldToGravityTransform` @ CMC+0x1F0**;
> ### `helper B 0x035F4770` reads **`GravityToWorldTransform` @ CMC+0x210**.
>
> ### WARNING WARNING THE SEED'S PARENTHETICAL DIRECTION LABELS ARE BACKWARDS.
> The seed says: *"`0x35F4620` reads the quat at `[rcx+0x1F0..0x208]` (gravity->world),
> `0x35F4770` reads the quat at `[rcx+0x210..0x228]` (world->gravity)"*.
> **The OFFSETS are exactly right. The direction labels are swapped** relative to the names
> UHT gives those offsets. Consequently the call sequence, read by property name, is:
>
> ```
> 0x035ED96E   temp   = GravityToWorldTransform.RotateVector(Velocity)   ; helper B, quat @0x210
>              temp.X = temp.Y = 0                                       ; the 16-byte store
> 0x035ED9B3   Velocity = WorldToGravityTransform.RotateVector(temp)     ; helper A, quat @0x1F0
> ```
>
> i.e. the temp at `[rbp+0x168]` is, by the property names, **not** obviously "gravity space".
>
> **This is IMMATERIAL to every mechanical conclusion** (sections 4 and 5) — see 3.6 — but the
> seed should not be quoted with those labels, and `docs/s140-t2-armj-THE-BOT-WALKS.md`'s
> "gravity-space `SizeSq2D`" phrasing inherits the same uncertainty.
>
> **NOT ESTABLISHED:** whether this is a UE naming convention where `XToYTransform` means
> "the rotation *of* frame Y expressed in X" (in which case the code reads correctly and the
> intuitive label is the wrong one), or genuinely reversed usage. WARNING: UE's own helpers
> `RotateWorldToGravity` / `RotateGravityToWorld` are **not reflected** (0 rows in
> `binds_members.csv`), so the UHT oracle cannot settle it. **The exact read that settles it:**
> disassemble `UCharacterMovementComponent::SetGravityDirection` (declared,
> `binds_members.csv:28396`) and see which quat it assigns `FQuat::FindBetween(DownVector,
> GravityDir)` versus its inverse. I did not locate that function — a constrained
> displacement scan over the CMC code region returned 21/82/31 candidate stores dominated by
> misaligned-decode noise, and I stopped rather than guess.

### 3.6 Why the label does not matter: BOTH QUATS DEFAULT TO IDENTITY — [M]

I found the CMC constructor's initialisation block and read the constants it stores:

```
0x035CF866  movups xmm0, [rip]->0x09A75290      0x035CF86D  movups [rbx+0x1d8], xmm0   ; GravityDirection.XY
0x035CF874  movsd  xmm1, [rip]->0x09A752A0      0x035CF87C  movsd  [rbx+0x1e8], xmm1   ; GravityDirection.Z
0x035CF884  movaps xmm0, [rip]->0x099C88A0      0x035CF88B  movups [rbx+0x1f0], xmm0   ; WorldToGravity  lo
0x035CF892  movaps xmm1, [rip]->0x099C88B0      0x035CF899  movups [rbx+0x200], xmm1   ; WorldToGravity  hi
0x035CF8A0  movaps xmm0, [rip]->0x099C88A0      0x035CF8A7  movups [rbx+0x210], xmm0   ; GravityToWorld  lo
0x035CF8AE  movaps xmm1, [rip]->0x099C88B0      0x035CF8BC  movups [rbx+0x220], xmm1   ; GravityToWorld  hi
```

```
0x099C88A0 = 00000000 00000000 00000000 00000000   -> (0.0, 0.0)
0x099C88B0 = 00000000 00000000 00000000 0000f03f   -> (0.0, 1.0)
   => DEFAULT quat (x,y,z,w) = (0, 0, 0, 1)  = IDENTITY
0x09A75290 / 0x09A752A0                        -> GravityDirection = (0, 0, -1)  = world down
```

**Both quats are initialised from the SAME two constant slots.** => at construction they are
identical and both are the identity quaternion; `GravityDirection` is world-down.

=> Under default gravity the round trip in section 5 is the **identity map**, so the site
zeroes **world** `Velocity.X` and `Velocity.Y` and returns **world** `Velocity.Z` bit-exactly.
The direction labels are then irrelevant by construction.

WARNING **Grade honestly:** the *defaults* are **[M]**; that they are *still* identity in the
live tutorial world is **[I, strong]** (default gravity, `GravityScale 1.000`, and S140
flight 3 measured `Velocity.Z` pinned at exactly `-4000` on the world Z axis with X/Y motion
purely horizontal — which is what identity predicts). **One read-only RPM read of
`CMC+0x1F0..0x22F` (64 bytes) settles it.** WARNING also: `0x099C88A0` / `0x09A75290` are in
`.data`, and the repo rule says never read a mutable global from a merged image. These are
compiler **constant-pool** slots sourced by `movaps` (16-byte aligned, read-only by
construction) — and an exact identity quaternion plus an exact unit down-vector is
self-validating — but a single-state dump would remove even that caveat.

---

## 4. Q4 — `rsi == &Velocity`, INDEPENDENTLY CONFIRMED BY NODE-REMOVAL DOMINANCE

**Every definition of `rsi` in engine `PhysFalling`** (all 1482 instructions scanned; writes
taken from `regs_access` *and* cross-checked against `operands[0]` being register `rsi`):

```
0x035EC9AC   48 8d b7 e8 00 00 00      lea rsi, [rdi + 0xe8]      <-- the ONLY value-producing def
0x035EE519   48 8b b4 24 18 09 00 00   mov rsi, [rsp + 0x918]     <-- epilogue restore, AFTER every store
```

Exactly **two**. `rdi == rcx == this` (3.4), so `rsi = this + 0xE8 = &Velocity`.
There are **79 calls** in the function, and `rsi` is **non-volatile in the Win64 ABI**, so no
call can clobber it.

**Node-removal reachability** (remove the node, recompute reachability from the entry):

```
reachable from entry, nothing removed : 1482 nodes  (all four targets present)
remove 0x035EC9AC (lea rsi,[rdi+0xe8]):  93 nodes

  target 0x035ED9BB  still reachable: False  -> DOMINATED
  target 0x035ED9C3  still reachable: False  -> DOMINATED
  target 0x035ED946  still reachable: False  -> DOMINATED
  target 0x035ED949  still reachable: False  -> DOMINATED
```

> **[M] `0x035EC9AC` dominates all four Velocity stores.** With the sole `rsi`-defining node
> removed, the reachable set collapses 1482 -> 93 and none of the stores survives.
> **The lead's dominance claim is CONFIRMED**, by an independently written CFG.

---

## 5. Q5 — ADVERSARIAL: every way "Velocity.Z is NOT zeroed by this site" could be wrong

### 5.1 "Could the Z at `[rbp+0x178]` already be zero for another reason?"

**Traced.** `[rbp+0x168..0x17F]` is written **only** by the callee at `0x035ED96E`
(`0x035F4770`) through `rdx`, which writes exactly 24 bytes: `movsd [rdx]`, `movsd [rdx+8]`,
`movsd [rdx+0x10]` (3.1). So `[rbp+0x178]` holds `RotateVector(quat@0x210, Velocity).Z`.

* Under the identity default (3.6) that is **exactly `Velocity.Z`**.
* It is then read straight back by `0x035F4620` (`movsd xmm12, [r8+0x10]` at `0x035F4693`) and
  carried into the OUT buffer, whose `+0x10` becomes `Velocity.Z` at `0x035ED9C3`.
* **So Z is zero here only if `Velocity.Z` was already zero.** It is not "incidentally zero".

**=> ONE REAL CAVEAT, and it matters for the fixed-point argument:** at the fixed point
`Velocity == (0,0,0)`, `temp == (0,0,0)`, so the site *does execute* (SizeSq2D = 0 <= gate) and
writes `(0,0,0)` over `(0,0,0)`. That is **consistent with** the fixed point but is *not*
evidence of it — at exactly zero this site is a no-op-by-value, and it cannot be distinguished
from "no write happened" by observing `Velocity` alone. **The S140 T2 conclusion that something
writes `Velocity` when it holds a small non-zero value stands; this site cannot tell you what
happens at exactly zero.**

### 5.2 "Is the branch even reached — could `ja` skip it?"

`preds(0x035ED998) = { 0x035ED996 (ja 0x35ed9c8) }` — **exactly one predecessor**, so the
zeroing block is entered **only** by the fallthrough of the gate, uniquely attributable to it.
`preds(0x035ED9AC) = { 0x035ED9A9 }` and `preds(0x035ED9BB) = { 0x035ED9B8 }` (straight line);
`preds(0x035ED9C8) = { the ja, 0x035ED9C3 }` — the join. Clean.
And at SizeSq2D = 0 the `ja` is **not** taken (section 2), so the block runs.

### 5.3 "Is there a DIFFERENT site that zeroes Velocity.Z?" — the honest limit of this lane

Exhaustive scan for stores to `[rsi + 0..0x18]` in engine `PhysFalling`: **32 stores at 16
sites** (each site a `movups`+`movsd` pair, or a 3x`movsd` triple):

```
0x035ECA2C/A35   0x035ECB57/B5B/B61   0x035ECB9C/BA8/BB2   0x035ECCFB/D06
0x035ECFBE/FC6   0x035ECFD4/FD8/FDD   0x035ED49A/49D       0x035ED52B/52F/534
0x035ED658/65C   0x035ED946/949       0x035ED9BB/9C3       0x035EDAA6/AA9
0x035EDE15/E18   0x035EE3F9/408
```

> WARNING **I graded exactly TWO of those 16 sites. The other 14 are NOT graded by this lane.**
> "Velocity.Z is not zeroed" is established **for the `0x035ED9BB/9C3` site only**. Any of the
> other 14 could write Z, including zero. That is the single biggest residual here.

### 5.4 The UPPER block at `0x035ED946/949` — the lead says nobody has read its guard. There is none.

```
0x035ED903  jmp    0x35ed931                     <-- an alternate entry that SKIPS the fill below
0x035ED905  movsd  xmm0, [rsi]                   ; Velocity.X          (8 B, NOT movups)
0x035ED909  lea    rax, [rbp+0x2c8]
0x035ED910  movsd  xmm1, [rdi+0xf0]              ; Velocity.Y  (= CMC+0xF0)
0x035ED918  movsd  [rbp+0x2c8], xmm0             ; temp.X = Velocity.X
0x035ED920  movsd  [rbp+0x2d0], xmm1             ; temp.Y = Velocity.Y
0x035ED928  movsd  [rbp+0x2d8], xmm8             ; temp.Z = xmm8   <-- the only NEW value
0x035ED931  movups xmm0, [rax]                   ; temp.X, temp.Y
0x035ED934  movss  xmm13, [rip]->0x076B498C
0x035ED93D  comiss xmm9, xmm13
0x035ED941  movsd  xmm1, [rax+0x10]              ; temp.Z
0x035ED946  movups [rsi], xmm0                   ; Velocity.X,.Y   <-- WRITE
0x035ED949  movsd  [rsi+0x10], xmm1              ; Velocity.Z      <-- WRITE
0x035ED94E  ja     0x35edaae                     ; the branch is AFTER the write
```

`preds(0x035ED946) = { 0x035ED941 }` — a single, straight-line predecessor.

> **[M] The upper block's write is UNCONDITIONAL at that point. The `comiss` at `0x035ED93D`
> is NOT a guard on it — the `ja` consuming those flags is at `0x035ED94E`, two instructions
> *after* both stores.** And it is **not a zeroing site**: X and Y round-trip through the stack
> unchanged and Z is set from `xmm8`. It writes `Velocity = (Velocity.X, Velocity.Y, xmm8)`.
> WARNING `xmm8`'s provenance is NOT traced by this lane — if `xmm8` can be 0 this site *can*
> zero `Velocity.Z`, which would be a second, differently-guarded zeroing path.
> **NOT ESTABLISHED. The read that settles it: back-trace the definitions of `xmm8` reaching
> `0x035ED928`.**

> WARNING WARNING **INSTRUMENT NOTE, and it changed a reading:** a **linear sweep** starting at
> `0x035ED900` decoded `0x035ED906 movups xmm0, [rsi]` (16 B — X *and* Y). The **sound CFG**
> gives `0x035ED905 movsd xmm0, [rsi]` (8 B — X only). One byte of misalignment, and the
> difference is whether Y comes from `[rsi+8]` or from `[rdi+0xF0]`. This is the seed's
> "a linear sweep is not a CFG" rule biting inside the very block under study.

### 5.5 Other ways the conclusion could fail — checked

| # | objection | status |
|---|---|---|
| 1 | The store is really 32 B (`vmovups ymm`) | **NO.** `0F 11 /r`, no VEX, no `66` — `MOVUPS m128`, 16 B, and capstone reports `op0.size == 16`. |
| 2 | `rsi` is not `&Velocity` at the store | **NO.** Section 4, dominance, plus non-volatile ABI. |
| 3 | The vector is floats (so 16 B = all 3 + pad) | **NO.** `mulsd`/`addsd`/`movsd` are scalar-**double**; Y is at `+0x170` (stride 8); the helpers move 24 B. |
| 4 | `Velocity.Z` written from a zeroed source | **Only if `temp.Z` (= rotated `Velocity.Z`) was already zero.** 5.1. |
| 5 | A non-identity quat mixes the zeroed XY into Z | **Possible in principle**, excluded under the identity default (3.6). Under non-default gravity `Velocity.Z` is *not* preserved bit-exactly. |
| 6 | Another site zeroes Z | **NOT EXCLUDED** — 14 of 16 Velocity-store sites ungraded (5.3), plus `xmm8` untraced (5.4). |
| 7 | The block is unreachable / dead | **NO.** Single-predecessor chain from the gate; and S140 flight 3 measured both polarities live. |
| 8 | NaN velocity behaves differently | **Checked:** NaN -> `ja` not taken -> the zeroing **executes**. |
| 9 | `.text` is only ~55 % decrypted, so a dark writer exists | **True and unfixable offline.** Every enumeration here is a **FLOOR**. |

---

## 6. WHAT I CONFIRM / REFUTE, versus the seed

| # | seed claim | verdict |
|---|---|---|
| 1 | gate constant is `(double)(float)1e-4 * 10.0`, **not** `(double)(float)1e-3` | **CONFIRMED [M]**; the doc's (a) is **REFUTED** |
| 2 | escape threshold `0.03162277644...` | **CONFIRMED**, `0.031622776202254524` |
| 3 | `0x077F5188` = `250000.0` | **CONFIRMED**; +1 validated reference, unrelated subsystem |
| 4 | `movups` at `0x035ED9AC` zeroes only 16 B -> the frame's X and Y | **CONFIRMED [M]** from the encoding |
| 5 | the two callees are quat rotations returning `rdx` in `rax` | **CONFIRMED [M]**, `mov rax,rdx` sole `rax` def in each |
| 6 | `0x35F4620` reads `[rcx+0x1F0..0x208]`, `0x35F4770` reads `[rcx+0x210..0x228]` | **CONFIRMED [M]** |
| 7 | those direction labels — `0x1F0` = "gravity->world", `0x210` = "world->gravity" | **REFUTED as stated**: UHT names them `WorldToGravityTransform`@`0x1F0`, `GravityToWorldTransform`@`0x210` |
| 8 | `rsi = &Velocity` [M] by dominance, sole `lea` at `0x035EC9AC` | **CONFIRMED [M]** by node removal, 1482 -> 93 |
| 9 | engine `PhysFalling` extent `0x35ec850..0x35ee593` | **CONFIRMED**, sole `ret` at `0x035EE592` |
| 10 | "nobody has read the upper block's guard" | **READ. There is no guard** — the write is unconditional, the `ja` follows it, and it is not a zeroing site |
| 11 | *(new)* both quats default to **identity**, `GravityDirection = (0,0,-1)` | **NEW [M]** from the ctor at `0x035CF840` |
| 12 | *(new)* `MovementMode` @ `CMC+0x231` | **NEW [M]**, corroborates the seed's `IsDashing = cmp byte [rcx+0x231],6` |

---

## 7. NOT ESTABLISHED — and the exact read that settles each

1. **Which quat is semantically world->gravity.** -> disassemble
   `UCharacterMovementComponent::SetGravityDirection` (`binds_members.csv:28396`) and see which
   quat gets `FindBetween(DownVector, GravityDir)` and which gets its inverse. Or one live RPM
   read of `CMC+0x1F0..0x22F` in a world with non-default gravity.
2. **Are the quats identity in the LIVE tutorial world?** -> one read-only RPM read of 64 bytes
   at `CMC+0x1F0`. Expect `(0,0,0,1)` twice.
3. **Do any of the other 14 Velocity-store sites in engine `PhysFalling` zero `Velocity`?**
   -> grade each of the 16 sites listed in 5.3 for its guard and its source operand. Purely
   offline; every page is LIT.
4. **Can `xmm8` be 0 at `0x035ED928`?** (would make the upper block a second zeroing path)
   -> back-trace `xmm8` definitions reaching that point. Offline.
5. **Is `Velocity.Z` zeroed *anywhere* on the falling path outside `PhysFalling`?** -> the same
   grading over `CalcVelocity 0x035D5D20`, `NewFallVelocity 0x055B6AD0`, and
   `ULokiCMC::PhysFalling 0x055B89F0`. Not touched by this lane.
6. **Dark-code readers of the gate constant.** `.text` is ~55 % decrypted; the 7-reference
   count is a **FLOOR**. Unfixable offline.

---

## 8. Instrument defects found this lane (candidates for `docs/method-rules.md`)

* **L2-a — a disp32 back-scan reference validator strips SSE prefixes and reports the wrong
  mnemonic AND the wrong operand width.** `F2 0F 5F ...` (`maxsd`, m64) aliases to
  `0F 5F ...` (`maxps`, m128); `66 0F 2F ...` (`comisd`, m64) aliases to `0F 2F ...`
  (`comiss`, m32). Scanning backward finds the **shorter** alias first and it decodes cleanly.
  Here it turned five 8-byte double reads into 16-byte vector reads and would have cast doubt
  on the constant's identity. **Fix: longest-match-wins, and cross-check against a sound CFG.**
* **L2-b — capstone 5.0.7 mis-sizes `comisd` as `xmmword ptr` / `op.size == 16`.** Per the ISA
  it is `m64`. Do not quote capstone's operand size for `comis*`/`ucomis*`. (Companion to the
  recorded S140 `movups`-store/`regs_access` defect — capstone's operand metadata is
  unreliable in *both* directions on SSE.)
* **L2-c — a linear sweep misaligned by one byte inside the block under study**, turning
  `movsd xmm0,[rsi]` (8 B) into `movups xmm0,[rsi]` (16 B) and changing where `Velocity.Y`
  comes from. The seed's rule, demonstrated from inside the result.
* **L2-d — `.pdata` is all zeros in `merged14`**, so any pdata-seeded function lookup returns
  `NONE` — which reads exactly like "not a function". Seed from the vtable or from a CFG.
* **L2-e — UHT property-name lookups collide across classes.** `MaxSimulationTimeStep` has
  rows at `0x3E0`, `0x198` and `0x1CC` in three different classes. **Always confirm table
  membership by walking neighbours at the 0x40 stride**, never by name alone.

---

## 9. Tools written (read-only, re-runnable, all under `scratchpad/s141/lanes/L2tools/`)

`l2pe.py` (PE reader) - `l2dis.py` (linear + sound recursive-descent CFG) - `l2ctrl.py`
(controls) - `q1.py` - `q1tail2.py` (corrected rip-rel reference scan) - `q1alias.py` -
`q2.py` - `q3prop.py` / `q3prop2.py` (UHT offset decoder + controls) - `q3tail.py` -
`q3diff.py` - `q3callers.py` - `q4.py` (dominance) - `q5.py`.
