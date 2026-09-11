# L5 — T3-B part 3: image-wide census of Velocity writers + the Loki side

**Image:** `dumps/merged14.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (va==praw on all 10 sections, verified).
**Offline only.** Zero launches, zero injection, zero live-process reads.
**Tools written this lane:** `scratchpad/s141/tools/{controls,storescan2,storescan3,extents,cmcfilter3,cmcfilter4,vt2,namefns,overrides,halfb_names}.py`

---

## 0. MANDATORY CONTROLS — ALL PASS

```
[CTRL-DARK] 0x5A6AC40 ULokiRespawnComponent::Respawn  page_nonzero = 0/4096      PASS
[CTRL-FOLD] 0x0f7ec20 c20000    PASS      0x0f7eb50 33c0c3   PASS
            0x0f7eb60 32c0c3    PASS      0x0b9e1f0 b001c3   PASS
            0x0fc6cf0 0f57c0c3  PASS
[CTRL-LIT ] 0x35ec850 ENGINE PhysFalling           3610/4096  PASS
            0x55b89f0 ULokiCMC::PhysFalling        3578/4096  PASS
            0x55c2430 ULokiCMC::StartNewPhysics    3626/4096  PASS
            0x35d5d20 ENGINE CalcVelocity          3660/4096  PASS
            0x55b6ad0 ULokiCMC::NewFallVelocity    3781/4096  PASS
            0x55ab8c0 ULokiCMC::GetGravityZ        3749/4096  PASS
            0x530abf0 ULokiCMC disp 0xA50          3883/4096  PASS
            0x55ac9f0 GAS +0xC00 slot              3729/4096  PASS
```

**Extra identity control (unprompted, and it is load-bearing):** the function at ULokiCMC vtable
**disp 0x3B8** references the literal **`&ULokiCharacterMovementComponent::UpdateFeatureToggles`**.
So `.rdata 0x088F8570` **is** `ULokiCharacterMovementComponent`'s vtable — measured, not assumed.

**Denominator for every count below:** `.text` = **30,281 pages, 16,816 decrypted (55.53 %)**.
**Everything in HALF A is a FLOOR over that 55.53 %.**

---

## 1. INSTRUMENT DEFECT I FOUND IN MY OWN FIRST SCANNER (recorded because it produced a wrong answer)

v1 anchored on the disp32 bytes `e8 00 00 00` and walked candidate instruction starts
`back = 3..15`, taking the **first** decode that produced a MEM-first operand with that
displacement. That systematically prefers the **shortest, misaligned** decode.

Concretely: `f2 0f 11 93 f8 00 00 00` = `movsd [rbx+0xf8], xmm2` at `0x35D6527` was **lost**,
because back=3 first decoded `0f 11 93 f8 00 00 00` = `movups [rbx+0xf8], xmm2` at `0x35D6528`
— a valid-looking, entirely fictitious instruction — and `break`ed. The pdata boundary filter then
correctly rejected the fake, so the real store vanished from the result set entirely.

**Caught only by a self-check against a KNOWN store** (`CalcVelocity`'s zeroing pair, from the
seed). **v2/v3 replaced the whole approach:** prefilter by bytes, then **fully decode the
containing function from its true entry**, then keep only instructions on real boundaries.
Self-checks now pass.

Rule for successors: *an anchor-and-walk-backwards decoder is biased toward short misaligned
decodes. Seed from a function entry, or you will silently drop instructions with prefixes.*

**Second defect, same lane:** pdata rows are **chained** — `CalcVelocity` occupies rows
`0x35d5d20..` through `..0x35d6786`. A per-ROW attribution put its stores in an unnamed function
and it never reached Tier A. `extents.py` chains rows where `B[i] == E[i-1]`:
**382,704 rows to 235,280 function extents.**

---

## 2. HALF A — IMAGE-WIDE STORE CENSUS

### 2.1 Raw counts (all FLOORS over 55.53 % decrypted `.text`)

| stage | count |
|---|---|
| byte-pattern sites `disp32 in {0xE8,0xF0,0xF8}` on lit pages, inside a pdata extent | 17,308 candidate functions |
| byte-pattern sites on lit pages with **NO pdata row** (invisible to stage 2) | **4,267** |
| **REAL store instructions to `[reg+0xE8/0xF0/0xF8]`** (operands[0].type == MEM) | **12,883** |
| distinct containing functions | **6,549** |

By displacement: `0xF0` 5,110 · `0xE8` 3,967 · `0xF8` 3,806.
By mnemonic: `mov` 10,193 · `movups` 950 · `movaps` 747 · `movsd` 610 · `movss` 156 ·
RMW (`and/inc/or/dec/xchg`) 112.
By base register: `rbx` 3,509 · **`rbp` 3,185** · **`rsp` 3,126** · `rdi` 1,308 · `rcx` 605 ·
`rsi` 466 · others 684. (rsp, and rbp where the function uses rbp as a frame pointer, are
**stack frames, not objects** — excluded from every filtered tier below.)

Writes were classified from `operands[0].type == MEM`, **never** from capstone `regs_access`
(the S140T2 trap: capstone 5.0.7 reports `movups` stores as reads).

### 2.2 What this scan is STRUCTURALLY BLIND TO — state this with any use of the numbers

1. **`lea`-based writes.** Engine `PhysFalling` does `lea rsi,[rdi+0xe8]` once (`0x035EC9AC`) and
   thereafter writes `movups [rsi], xmm0` / `movsd [rsi+0x10], xmm1` — **displacement 0 and 0x10**.
   Those are the two most important Velocity stores in the whole investigation and **this scan
   cannot see them.** Verified: `0x35ED9BB` and `0x35ED9C3` are absent from the hit set, correctly.
2. **`memcpy` / `rep movs` / any register-computed address.**
3. **The dark 44.47 % of `.text`.**
4. **The 4,267 byte-pattern sites with no pdata row** (`pdataunion.py` drops size<=1 placeholder
   rows *by construction*, so it is blind exactly where pages are dark).
5. **Indexed addressing** (`[reg + idx*n + 0xE8]`) — deliberately excluded to cut array noise.

### 2.3 Filtered to plausible CMC targets

Filter criteria, applied to the **chained function extent**, with stack-frame stores excluded:

* **TIER A** — the function is on the ULokiCMC (`0x088F8570`) or engine-CMC (`0x07FBED58`) vtable.
* **TIER B** — the function touches a RARE CMC field (`+0x12B0` TimeSinceFallingStart,
  `+0x16B0` VelSnapshot, `+0x16C8` VelSnapFlag) on a non-stack base.
* **TIER C** — 2 or more medium CMC fields, or calls `GetLokiCharacterMovement 0x55AC8E0`.

| tier | functions | object-field stores |
|---|---|---|
| **A** | **25** | 115 |
| **B** | 3 | 6 |
| C | 92 | 219 |

Tier C is noisy (`+0x328`/`+0x290`/`+0x458` are common displacements) and is **not** asserted to
be CMC. Only A and B are claimed.

### 2.4 TIER A — the 25 CMC-vtable Velocity writers, with vtable displacement

`[M]` naming where the dispatch table or a shipped string settles it; `[I]` otherwise.

| disp | Loki impl | Engine impl | name | evidence |
|---|---|---|---|---|
| 0x4D8 | 0x32C9DD0 | *(same)* | **`UMovementComponent::StopMovementImmediately`** | [M] its registered impl `0x332DA08` is the stub `mov rax,[rcx]; jmp [rax+0x4D8]`; body sets `Velocity=(0,0,0)` then `[vt+0x518]` then tail-`jmp [vt+0x5C0]` |
| 0x748 | 0x35E7340 | *(same)* | **`UCharacterMovementComponent::Launch(FVector const&)`** | [M,strong] writes `PendingLaunchVelocity` +0x5C8/+0x5D8 and nothing else; sits one slot before HandlePendingLaunch |
| **0x750** | **0x55AEB60** | 0x35E60F0 | **`HandlePendingLaunch`** — **LOKI OVERRIDE, WRITES VELOCITY** | [M] see 2.5 |
| 0x790 | 0x35D4210 | *(same)* | [I] a move/replay applier (6 stores) | — |
| 0x7B0 | **0x35D5D20** | *(same)* | **`CalcVelocity`** — **22 Velocity stores, the most of any function in the image** | [M] seed |
| 0x828 | 0x3600C20 | *(same)* | [I] `PhysWalking`-family helper (9 stores) | — |
| **0x830** | **0x55B89F0** | 0x35EC850 | **`PhysFalling`** — **BOTH sides write Velocity** | [M] StartNewPhysics jump table case 3 |
| 0x880 | 0x35F2560 (eng) | Loki 0x55BDDA0 | [I] | — |
| 0x900 | 0x35F9B30 | *(same)* | [I] | — |
| 0x978 | 0x35EEA50 | *(same)* | **`PhysNavWalking`** | [M] jump-table case 2 **and** its own string *"using cached navmesh location! (bProjectNavMeshWalking = %d)"* |
| 0x980 | 0x35EE5A0 | *(same)* | **`PhysFlying`** | [M] jump-table case 5 (MOVE_Flying) |
| **0x990** | **0x55B88E0** | 0x35EB850 | **`PhysCustom`** — **LOKI OVERRIDE, ZEROES VELOCITY** | [M] jump-table case 7 |
| 0x9A8 | 0x35E7880 | *(same)* | **`StepUp`** | [M] strings `"+ StepUp (ImpactNormal %s, Normal %s"` / `"- StepUp ..."` |
| 0x9B8 | 0x35E7600 | *(same)* | [I] | — |
| 0x9D0 | 0x35D4810 | *(same)* | [I] | — |
| 0xA80 | 0x35D2E90 | *(same)* | [I] a state-restore virtual — writes Velocity **and all three pending vectors** from a source struct, then calls disp 0xA50 | — |
| 0xAC0 | 0x35FD420 | *(same)* | **`SimulatedTick`** | [M] string `"UCharacterMovementComponent::SimulatedTick"` |
| 0x678 | Loki 0x55B7BF0 | **0x35E9240** | **`SetMovementMode`** — the ENGINE body writes Velocity (7 stores) | [M] string `"New Movement Mode Not Applicable"` |
| 0x6C0 | 0x35E9B20 | *(same)* | [I] | — |
| 0x730 | Loki 0x55A8110 | **0x35DEAD0** | [I] an "apply base / root-motion velocity" virtual: reads `[this+0x198]`, calls `[vt+0x738]` for an FVector, sets `Velocity = *that`, then `SetMovementMode(3)` | — |
| 0x760 | 0x35E7010 | *(same)* | [I] | — |
| 0xCB8 | Loki 0x55C25B0 | **0x3603010** | [I] 11 Velocity stores — a network-smoothing / client-adjust body | — |
| 0xE48 | — | 0x35DB4A0 | [I] | — |
| 0x4F0 | 0x35F1320 | *(same)* | [I] | — |

The `Phys*` naming above is [M] because it comes from the **StartNewPhysics dispatch table**,
read this lane (engine `StartNewPhysics 0x03600990`, `cmp esi,7 / ja`, table at `.text 0x03600BF8`,
8 absolute-RVA entries):

| MovementMode | case | branch | vtable disp |
|---|---|---|---|
| 0 MOVE_None | 0 | 0x3600BA8 | *(no call)* |
| 1 MOVE_Walking | 1 | 0x3600A97 | **0x970** |
| 2 MOVE_NavWalking | 2 | 0x3600AAE | **0x978** |
| 3 MOVE_Falling | 3 | 0x3600AC5 | **0x830** |
| 4 MOVE_Swimming | 4 | 0x3600AF3 | **0x988** |
| 5 MOVE_Flying | 5 | 0x3600ADC | **0x980** |
| 6 MOVE_Dashing (Loki) | 6 | 0x3600B0A | **0xCC8** |
| 7 MOVE_Custom | 7 | 0x3600B21 | **0x990** |

### 2.5 THE HEADLINE OF HALF A — `HandlePendingLaunch` is the game's own native "kick"

`disp 0x750`, engine `0x35E60F0`, **Loki override `0x55AEB60`.** Transcribed in full:

```
if (PendingLaunchVelocity(+0x5C8,+0x5D0,+0x5D8) == (0,0,0)) return false;   // 0x55AEB6C..0x55AEB88
if (!HasValidData() /* [vt+0x6B8] */)                        return false;   // 0x55AEB91
Velocity(+0xE8) = PendingLaunchVelocity;      // 0x55AEBB4 movups + 0x55AEBC0 movsd
if (!IsDashing() /* [vt+0xCE0] */)
        SetMovementMode(MOVE_Falling = 3);    // 0x55AEBE2 call [vt+0x670], edx = 3
PendingLaunchVelocity = ZeroVector;           // 0x55AEBF6 / 0x55AEC0C
[this+0x2E9] |= 8;                            // bForceNextFloorCheck
<visual-logger call through [[this+0x198]+0x990] with rdx = &Velocity>
return true;
```

The engine body is the same minus the `IsDashing` guard and the logger call.

**And the setter is `disp 0x748 = 0x35E7340` — `Launch(FVector const&)`, NOT Loki-overridden:**

```
if (MovementMode(+0x231) == MOVE_None) return;   // 0x35E734A
if (!([this+0xB2] & 8))                return;   // 0x35E7359
if (!HasValidData())                   return;   // 0x35E7365
[this+0x574] = 1.0f;                             // 0x35E736F
PendingLaunchVelocity = LaunchVel;               // 0x35E737C movups [+0x5C8] ; 0x35E7388 movsd [+0x5D8]
```

So **the whole "kick" is: write 24 bytes at `CMC+0x5C8`.** `HandlePendingLaunch` is called from
`PerformMovement` (measured running every frame, S140 T2), it sets `Velocity`, it forces
`MOVE_Falling`, and it clears the field behind itself. **No authority check anywhere on the path.**
This is a strictly smaller and more game-native intervention than S140's external `Velocity` write.

### 2.5b SETTLED IN-LANE: `HandlePendingLaunch` IS CALLED EVERY FRAME ON BOTH COMPONENTS [M]

I ran the CFG pass rather than leaving this open. Sound recursive descent over engine
`PerformMovement 0x035E9EC0` (`scratchpad/s141/tools/cfg.py`, its own fold + dark controls passing):

```
engine PerformMovement 0x35E9EC0: 1461 insns, 148 calls, 0 indirect jumps, 0 decode failures
  0x035EA160  call qword ptr [rax + 0x750]   <- HandlePendingLaunch
  0x035EB13A  call qword ptr [rax + 0x720]   <- StartNewPhysics
R (can reach the StartNewPhysics call) = 1075 insns; sound exits = 6 (+ the call's own fallthrough)
```

**Instrument control:** those figures — 1461 / 1075 / 0 indirect / 0 decode failures / exactly the
six exits `0x035E9F1F, 0x035E9F28, 0x035E9F97, 0x035E9FA4, 0x035E9FBD, 0x035EA25D` — **reproduce
S140 Tier 1 exactly**, from an independently-run walk on a different image (`merged14` vs
`merged13`). That is a passing positive control on the whole instrument.

**Dominance test (node removal, the only sound form):**

```
forward-reachable from entry            : 1461
forward-reachable with 0x035EA160 REMOVED:  181
StartNewPhysics call reachable normally : True
StartNewPhysics call reachable w/o HPL  : False
=> 0x035EA160 DOMINATES 0x035EB13A
```

**[M] `HandlePendingLaunch`'s call site DOMINATES the `StartNewPhysics` call site.**
S140 Tier 2 MEASURED that `ULokiCMC::StartNewPhysics` runs essentially every frame on **both** the
bot's and the player's movement component (pre-poisoned payload, 396/400). A dominator of a site
that provably executed also executed.

⇒ **`ULokiCMC::HandlePendingLaunch` (`0x55AEB60`) is entered every frame on the bot, today.**
It reads `PendingLaunchVelocity` first thing and returns false because it is `(0,0,0)`.

⇒ **THE KICK IS: WRITE 24 BYTES AT `CMC+0x5C8`.** Within one frame the game's own code will
`Velocity = PendingLaunchVelocity`, `SetMovementMode(MOVE_Falling)`, set `bForceNextFloorCheck`,
and zero the field behind itself. No `.text` write, no PI hook, no reflected call, no authority
check anywhere on the path, and it is self-clearing so there is nothing to restore.

⚠ The Loki `PerformMovement` half of the chain is the seed's [M]: `ULokiCMC::PerformMovement
0x055B8370` reaches its Super unconditionally (|R| = 142 of 322, zero edges leaving the set).

### 2.6 `ULokiCMC::PhysCustom` (`0x55B88E0`, disp 0x990) ZEROES VELOCITY — new, and NOT our wall

```
if (MovementMode(+0x231) != 7 /*MOVE_Custom*/) return;      // 0x55B88E6
switch (CustomMovementMode(+0x232)) {          // 7-entry table at .text 0x55B89C8, values 1..7
  case k: PhysFalling();                                     // call [vt+0x830]
          if ([this+0x1318] != 0) {
              Velocity.X = 0; Velocity.Y = 0;                // 0x55B8951 / 0x55B895C
              Velocity.Z = max(Velocity.Z, 0.0);             // 0x55B8958 maxsd / 0x55B8963
          }
  case j: [vt+0x5C0](); Velocity.Z = 0;                      // 0x55B898C
  ...
}
```

**[M] It cannot fire on a `MOVE_Falling(3)` pawn** — the first instruction gates on `+0x231 == 7`.
Record it; do not chase it for the current wall.

### 2.7 TIER B (3 functions, not on either CMC vtable, touch rare CMC fields) — UNRESOLVED

`0x298A890` (VelSnapshot) · `0x559E180` (VelSnapshot + VelSnapFlag) · `0x55C00C0` (VelSnapFlag).
Plausibly CMC-adjacent but none is on either vtable and none was named.
**NOT ESTABLISHED.** Settled by resolving each through the `.data` `{name,thunk,impl}` table, or by
finding a caller that provably passes a CMC pointer.

---

## 3. FREE BY-PRODUCTS THAT BEAR DIRECTLY ON THE FIXED-POINT STORY

### 3.1 `PhysFalling` deliberately zeroes `Velocity.Z` and RESTORES it around `CalcVelocity` [M]

```
0x35ECBD1  mov   qword [rdi+0xf8], r13     ; r13 = 0   ->  Velocity.Z = 0
0x35ECBD8  call  qword [rax+0x7b0]         ; CalcVelocity
0x35ECBDE  movsd qword [rdi+0xf8], xmm14   ; Velocity.Z = OldVelocity.Z   (RESTORED)
```

This is stock UE's `Velocity.Z = 0; CalcVelocity(...); Velocity.Z = OldVelocity.Z;` idiom.
A second occurrence at `0x35ED5CE` zeroes Z and calls `[vt+0x7B0]`; **its restore was not located
in the window I read — [I], not [M].**

So the `CalcVelocity` input clamp (`0x035D6520 movups [rbx+0xe8], ZeroVector` +
`0x035D6527 movsd [rbx+0xf8], xmm2`) is **bracketed by a Z save/restore when called from
`PhysFalling`** — on the falling path it is, in effect, a **horizontal** clamp.

This tightens the S141 headline: the fixed point being chased is a **horizontal** fixed point;
`Velocity.Z` on the falling path is governed by `NewFallVelocity` + the restore, not by that clamp.
It also creates an **open tension** with the observed no-fall: if Z is restored and gravity added,
Z should grow negative. **NOT ESTABLISHED which of the two is wrong.** Settled by reading whether
`0x35ED5CE`'s branch restores Z, and by locating `PhysFalling`'s call site of disp 0x7A0
(`NewFallVelocity`) and its guard.

### 3.2 The `PhysFalling` `SizeSq2D` block does **NOT** zero `Velocity.Z` [M, structure]

The seed flagged as `[I]` whether Z is zeroed at `0x035ED9C3`. Reading the block:

```
0x35ED998  xorps  xmm0, xmm0
0x35ED9AC  movups [rbp+0x168], xmm0      ; <-- 16 BYTES: gravity-space X and Y ONLY.
                                         ;     [rbp+0x178] (gravity-space Z) is UNTOUCHED.
0x35ED9B3  call   0x35F4620              ; rotate gravity-space -> world (returns the OUT buffer in rax)
0x35ED9BB  movups [rsi], xmm0            ; Velocity.X, Velocity.Y
0x35ED9C3  movsd  [rsi+0x10], xmm1       ; Velocity.Z  <- xmm1 = [rax+0x10], the ROTATED Z
```

So `Velocity.Z` **is** written, but with the rotation of `(0, 0, Z_gravityspace)`. With an identity
gravity quat (gravity straight down) that is the pre-existing Z, unchanged.
**[M]** for the structure (a 16-byte store leaves Z alone); **[I, strong]** for "Z is preserved when
the gravity quat is identity" — a live read of the quat at `CMC+0x1F0..0x208` makes it [M].

### 3.3 The gate constant — the seed is right and `docs/s140-t2-armj-THE-BOT-WALKS.md` is wrong

`.rdata 0x077F5180 = 0.00099999997473787516`, re-read this lane.
`(double)(float)1e-3 = 0.0010000000474974513` — a **different** value.
`0.00099999997473787516 == (double)(float)1e-4 * 10.0` = `UE_KINDA_SMALL_NUMBER(float) * 10`.
**The correction stands.**

---

## 4. HALF B — THE LOKI SIDE

### 4.1 `ULokiCMC::GetGravityZ` (`0x055AB8C0`, disp 0x4C0) — **CANNOT return 0 on a falling pawn** [M]

```
if (MovementMode(+0x231) == 7 /*MOVE_Custom*/) {           // 0x55AB8CA
    uint8 cm = CustomMovementMode(+0x232);
    if (cm == 3 || cm == 4)                  return 0.0f;   // 0x55AB8FA
    if (cm == 2 && [this+0x1318] != 0)       return 0.0f;
    if (cm == 5)  return engineGetGravityZ() * [this+0x14BC];
}
float g = engineGetGravityZ();                              // 0x55AB92E
if (MovementMode == 7 && CustomMovementMode == 7 && 0x55A4C40(this) <= 0)
    g = 0.0f;                                               // 0x55AB954
return g;
```

**Every zero-return arm is gated on `MovementMode == 7`.** The bot is `MOVE_Falling(3)`.
So **[M] on a `MOVE_Falling` pawn `ULokiCMC::GetGravityZ` is a pure pass-through to the engine
impl.** This closes the lane's assigned question: **the Loki gravity override does not explain the
no-fall phenomenon.**

**Engine `GetGravityZ` (`0x035E3650`) — the other candidate, also ruled out:**

```
if ( [vt+0xCE0]() && ![this+0x1001] ) return 0.0f;          // 0x35E365C .. 0x35E366D
return  0x3632E20(this) * GravityScale(+0x1A0);             // 0x35E3680 mulss xmm0,[rbx+0x1a0]
```

and **[M] `disp 0xCE0` = `0x035E6810` = `cmp byte [rcx+0x231], 6 ; sete al ; ret` = `IsDashing`**
(MOVE_Dashing == 6 in this build; the seed independently names `IsDashing 0x035E6810`).
On a `MOVE_Falling(3)` pawn `IsDashing()` is FALSE, so **the engine early-out does not fire either**.
Gravity is `worldGravity * GravityScale`, and the `mulss xmm0,[rbx+0x1a0]` independently
corroborates `GravityScale @ CMC+0x1A0`.

Side observation worth recording: **this build's "engine" `UCharacterMovementComponent` is itself
Loki-modified** — stock UE has no `IsDashing` virtual and no `MOVE_Dashing`. Do not treat the
`0x07FBED58` vtable as pristine engine code.

### 4.2 `ULokiCMC::NewFallVelocity` (`0x055B6AD0`, disp 0x7A0) — pass-through on MOVE_Falling [M]

```
engineNewFallVelocity(this, OUT, IN, Gravity, DeltaTime);      // 0x55B6AEC, UNCONDITIONAL
if (MovementMode == 7 && CustomMovementMode == 1)              // 0x55B6AF1 / 0x55B6AFA
    OUT->Z = max( -[this+0x1140], min(OUT->Z, 0.0) );           // 0x55B6B29
return OUT;
```

**[M] Loki adds nothing on `MOVE_Falling`.** Engine `0x035E8B00`:

* copies `IN` to `OUT` (`0x35E8B1D`/`0x35E8B20`);
* **`if (DeltaTime <= 0) return OUT` unchanged** (`0x35E8B31 comiss` / `0x35E8B34 jbe`);
* `OUT += Gravity * DeltaTime` on all three components (`0x35E8B5F` / `0x35E8B76` / `0x35E8B7B`);
* terminal-velocity clamp against `[GetPhysicsVolume()+0x3C8]` (`TerminalVelocity`).

Gravity arrives as a **three-component FVector in `r9`**, not as the scalar `GetGravityZ()` — so
`GetGravityZ` may not even be on the falling force path. **NOT ESTABLISHED** where `r9` comes from;
settled by reading `PhysFalling`'s call site of disp 0x7A0.

### 4.3 All ULokiCMC vtable overrides, graded

| | |
|---|---|
| common slots compared | **450** (Loki table 450 entries; engine table 471) |
| slots that differ | **70** |
| of which a genuine override | **69** — **68 REAL, 1 DARK** (`disp 0xCD8` slot 411, Loki `0x55A2290`, engine `0xB9E1F0` = return-true fold) |
| plus | **1 NULL slot** — `disp 0xE08` slot 449: the Loki table holds `0x0` where the engine has `0x35D0EF0`. Real, in the image, unexplained. |
| **overrides that write `[this+0xE8/F0/F8]` directly** | **exactly 3: `0x750` HandlePendingLaunch · `0x830` PhysFalling · `0x990` PhysCustom** |

Notable non-velocity rows: `disp 0x3B8` = `UpdateFeatureToggles` (names the class);
`disp 0x678` = `SetMovementMode`; `disp 0x918` (strings *"Parachuting"*, *"Mantling"*);
`disp 0x8F0` (*"CLIENT"*); `disp 0x540` (*"X=%3.3f Y=%3.3f Z=%3.3f"*, *"Unknown Actor"*).
Three slots where the **engine** side is a fold and Loki supplies a real body:
`0x668` (eng `0xF7EB60`), `0xAF0` (eng `0xB9E1F0`), `0xCD8` (eng `0xB9E1F0`);
and three where the engine is `0xF7EC20`: `0xAB0`, `0xAB8`, `0xC70`.

Full table: `scratchpad/s141/tools/loki_overrides.json`.

**[M] `CalcVelocity` (disp 0x7B0) is NOT in the override list** — Loki does not override it,
confirming the seed.

### 4.4 Knockback / launch / impulse UFunction census (`.data` `{name, thunk, impl}` record table)

**16,253 records scanned; 229 match the keyword set** {Knockback, Launch, Impulse, Push, Pull,
Dash, Blink, Displace, Teleport, Velocity, Fling, Yeet, Boop, Force}.
Grades: **REAL 186 · DARK 26 · FOLD(void ret0) 11 · FOLD(false) 6.**

The record table's negative half is **degenerate for Angelscript** — AS names have zero byte
occurrences in the image — so "no record" never means "does not exist" for an AS function.
My scanner is also a **floor**: `ACharacter::LaunchCharacter` **is present in the image**
(ASCII x2, UTF-16 x6, against a passing `ZZZ_NOT_A_REAL_NAME_CONTROL` = 0) but `recscan.py`
produced no record row for it. Do not read its absence as a fact.

**The ranked candidates, with UHT flags from `tools/re/out/uht_funcflags_tuthero.csv`:**

| owner :: function | thunk | impl | grade | flags | note |
|---|---|---|---|---|---|
| `UCharacterMovementComponent::AddImpulse` | 0x36068E0 | 0x3316AD8 | **REAL** | `RequiredAPI\|Native\|Public\|HasDefaults\|BlueprintCallable` | **no BlueprintAuthorityOnly.** Impl is the stub `mov rax,[rcx]; jmp [rax+0x928]`, so **vtable disp 0x928**; ULokiCMC overrides at **0x55A0ED0**, engine at **0x35D1E00** |
| `ULokiLaunchCharacterTask::LokiLaunchCharacter` | 0x53C3080 | **0x56F08A0** | **REAL** | `Final\|Native\|Static\|Public\|HasDefaults\|BlueprintCallable` | ability-task **factory**; see 4.6 |
| `ALokiCharacter::Dash` | 0x52FEAB0 | 0x55A7A40 | REAL | `Final\|Native\|Public\|HasOutParms\|BlueprintCallable` | on the hero itself, no authority flag |
| `ALokiBotController::TryToDash` | 0x52EED90 | 0x5570690 | REAL | `Final\|Native\|Public\|BlueprintCallable` | **on the bot controller** |
| `ALokiCharacter::StopDashByHandle` | 0x53041B0 | 0x55C25D0 | REAL | `Final\|Native\|Public\|BlueprintCallable` | |
| `ALokiCharacter::EnableDashGravity` | 0x52FEF30 | 0x32CE8EC | REAL | `Native\|Public\|BlueprintCallable` | impl is a dispatch stub |
| `UMovementComponent::StopMovementImmediately` | 0x365BF40 | 0x332DA08 | REAL | `RequiredAPI\|Native\|Public\|BlueprintCallable` | stub to **disp 0x4D8 = 0x32C9DD0**, which sets `Velocity = 0` |
| `ULokiGameplayStatics::LokiTeleportActor` | 0x537B570 | 0x56680F0 | **DARK** | `Final\|Native\|Static\|Public\|HasDefaults\|BlueprintCallable` | never executed in any captured image |
| `ULokiProjectileMovementComponent::SetVelocity` | 0x5448590 | 0x574B5B0 | REAL | `Final\|Native\|Public\|HasDefaults\|BlueprintCallable` | **projectile** movement component, not the character CMC |
| `AActor::AddImpulse` / `UPrimitiveComponent::AddImpulse` | — | 0x3316C58 / 0x207A000 | REAL | `RequiredAPI\|Native\|Public\|HasDefaults\|BlueprintCallable` | rigid-body physics, **not** the CMC path |
| `ALokiPlayerCheats::TeleportAlly` / `TeleportEnemy` / `TeleportNear` | **0x5254180** (91-way ICF) | **0x0F7EC20** | **FOLD(void ret0)** | — | dead |
| `ULokiTuningLibrary::GetTuningBooperKnockbackCoefficient` | 0x5490C90 | **0x0F7EC20** | **FOLD** | | dead |
| `AuthForceExplode`, `ForceComplexMovement`, `ForceDeath` | 0x5254180 | **0x0F7EC20** | **FOLD** | | FK-1 family |
| `ULokiGameplaySpell::AuthStopDash` | 0x535F240 | 0x5518930 | **DARK** | `Final\|Native\|Public\|BlueprintCallable` | |
| `ULokiAttributeSet::OnRep_KnockbackCoefficient` / `...ResistCoefficient` | — | 0x52AE904 / 0x3375780 | REAL | `Native\|Protected\|HasOutParms` | knockback is a **GAS attribute** in this game |

Full 229-row table: `scratchpad/s141/tools/halfb_hits.json`.

Engine `AddImpulse` (`0x35D1E00`) body, for completeness — note it shares `Launch`'s prologue exactly:

```
if (Impulse == (0,0,0))                return;   // 0x35D1E1B..0x35D1E37
if (MovementMode(+0x231) == MOVE_None) return;   // 0x35D1E3D
if (!([this+0xB2] & 8))                return;   // 0x35D1E4A
if (!HasValidData() /* [vt+0x6B8] */)  return;   // 0x35D1E5A
[this+0x574] = 1.0f;                             // 0x35D1E6D
if (!bVelocityChange) { if (Mass(+0x300) > SMALL) Impulse /= Mass; else UE_LOG(warn); }
...
PendingImpulseToApply(+0x3A0) += Impulse;        // 0x35D1F16 addsd / 0x35D1F2E movsd
```

The Loki override (`0x55A0ED0`) calls the engine body first (`0x55A0F1F`), then adds MOVE_Custom
special-casing and an extra instigator parameter it stores at `[this+0x1180]`.

### 4.5 CMC field offsets confirmed from the UHT property records (with passing controls)

Decoded from `FPropertyParams` dword[12] = `(Offset << 16) | ArrayDim`.
**Positive controls that pass, using values the seed already carries as [M]:**
`MinAnalogWalkSpeed = 0x290` · `Acceleration = 0x328` · `MaxSimulationTimeStep = 0x3E0` ·
`MaxSimulationIterations = 0x3E4` · `CustomMovementMode = 0x232`.
**Negative control:** `Force_NOT_REAL_CONTROL` -> string not found.

| field | offset | grade |
|---|---|---|
| **`PendingLaunchVelocity`** | **`CMC+0x5C8`** (X 0x5C8, Y 0x5D0, Z 0x5D8) | **[M]** — corroborated by `Launch` and `HandlePendingLaunch` reading exactly those |
| **`PendingImpulseToApply`** | **`CMC+0x3A0`** | **[M]** — corroborated by engine `AddImpulse`'s `addsd`/`movsd` at `0x35D1F16`/`0x35D1F2E` |
| **`PendingForceToApply`** | **`CMC+0x3B8`** | **[M]** |
| **`GravityScale`** | **`CMC+0x1A0`** | **[M]** — corroborated by `mulss xmm0,[rbx+0x1a0]` in engine `GetGravityZ` |
| `MaxAcceleration` | `CMC+0x28C` | [M] |
| `AnalogInputModifier` | `CMC+0x3D0` | [M] |
| `MaxWalkSpeed` | `CMC+0x278` | [M] |
| `GroundFriction` | `CMC+0x234` | [M] |
| **`ACharacter::CharacterMovement`** | **`ACharacter+0x458`** | **[M]** — `GetLokiCharacterMovement 0x55AC8E0` is `mov rbx,[rcx+0x458]` then an `IsA` check then `return rbx` |

**The bool trap fires here exactly as S132 documents:** `bJustTeleported` decodes to `off=0x1`,
which is nonsense — `FBoolPropertyParams` has a different layout with no `Offset` field.
**Only use this decode for non-bool properties.**

### 4.6 `LokiLaunchCharacter` — real, but a heavier route than it looks

`0x56F08A0`, 0x6BF bytes, page 3714/4096, REAL. From the register discipline:

* `rcx` = an owning `UGameplayAbility` (null-checked; if non-null, `StaticClass()` `0x4400850` then
  `Cast` `0x1364D40`, returning 0 if the cast fails);
* `r9` = an **`ALokiCharacter*`** — checked for `RF_Garbage` (`[r9+0xC] >> 30`), then
  `lea rcx,[rbx+0x7f0]` / `call [[rbx+0x7f0]+0x10]`, which is **the `IAbilitySystemInterface`
  secondary vtable whose slot +0x10 returns `char+0xF00`** — exactly the shape CLAUDE.md records.
  **If the ASC is NULL the function logs and returns nullptr** (`0x56F0952 jne` / fallthrough to
  the log block at `0x56F0954`);
* every failure path returns **0** — it is a **task factory**, so the launch itself happens in the
  task's `Activate()`, not here.

**[M] `LokiLaunchCharacter` requires (a) a valid owning `UGameplayAbility` and (b) a non-NULL ASC
at `ALokiCharacter+0xF00`.** ARM G already wires (b) on the bot; (a) is not satisfied by anything
we control. **Do not lead with this route** — `Launch` / `AddImpulse` / a direct
`PendingLaunchVelocity` write need neither.

---

## 5. RANKED SUCCESSOR ACTIONS (three of four fully offline)

1. **DONE IN-LANE (2.5b): write 24 bytes at `CMC+0x5C8`.** `HandlePendingLaunch`'s call site
   dominates the `StartNewPhysics` call site, and `StartNewPhysics` is measured running every
   frame, so the handler runs every frame and is waiting on exactly that field. **Fly it.**
   Pre-registration should include: `Velocity` becomes the written value **and** `MovementMode`
   becomes `3 (MOVE_Falling)` **and** `CMC+0x5C8` reads back `(0,0,0)` within one frame — three
   independent readouts from one write, all from `tools/re/cmc_earlyout_readout.py`-style RPM.
   The self-clearing behaviour is itself the receipt: **if `+0x5C8` is still non-zero, the handler
   did not run**, which separates "wrong offset" from "path not reached" without ambiguity.
2. **[offline, free] Finish `ULokiCMC::AddImpulse 0x55A0ED0` + engine `0x35D1E00`, and read the
   consumer of `PendingImpulseToApply @ +0x3A0`** (`ApplyAccumulatedForces`; candidate refs are
   already enumerated in this lane's data). `AddImpulse` is `BlueprintCallable` and **not**
   `BlueprintAuthorityOnly`, so the S55 direct-thunk primitive reaches it.
3. **[offline, free] Settle 3.1's tension**: does the branch at `0x35ED5CE` restore `Velocity.Z`
   after `CalcVelocity`, and where does `PhysFalling` call `NewFallVelocity` (disp 0x7A0)? If Z is
   restored and gravity added, the observed no-fall needs a different explanation than anything in
   this lane produced.
4. **[one read-only RPM] Read the gravity quat at `CMC+0x1F0..0x208`.** If it is identity, 3.2's
   "Velocity.Z is preserved by the SizeSq2D block" moves from [I, strong] to [M].

---

## 6. NOT ESTABLISHED

* ~~Whether `HandlePendingLaunch` is reached on the current bot route~~ — **SETTLED IN-LANE, see
  2.5b: its call site dominates the `StartNewPhysics` call site, which is measured running every
  frame. It runs.** What remains untested is only the write itself.
* The identity of Tier-A `disp 0xA80 / 0x790 / 0x828 / 0x9B8 / 0x9D0 / 0x760 / 0x4F0 / 0x6C0 /
  0x880 / 0x900 / 0xE48 / 0xCB8 / 0x730` — [I] only. Settled by the `.data` record table, or by
  matching the slot order against a UE 5.4 CMC vtable layout.
* All three Tier-B functions (2.7). Settled by resolving them through the record table.
* Why the Loki CMC vtable carries a **NULL** at `disp 0xE08` where the engine has `0x35D0EF0`.
  Settled by reading `0x35D0EF0` and identifying the slot.
* Whether the second `Velocity.Z = 0; CalcVelocity()` site (`0x35ED5CE`) restores Z (3.1).
* `LokiTeleportActor 0x56680F0` is **DARK** — its body has never been decrypted; nothing about it
  can be graded beyond "never executed within 55.53 % coverage".
* The meaning of `CMC+0x574` (set to `1.0f` by both `Launch` and `AddImpulse`) and `CMC+0xB2 & 8`
  (a mandatory gate on both). Settled by a UHT property-record lookup on the neighbouring names.
