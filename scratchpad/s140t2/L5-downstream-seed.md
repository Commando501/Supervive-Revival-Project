# S140 TIER 2 — LANE 5: DOWNSTREAM SEED (PhysFalling / CalcVelocity / GetMaxSpeed)

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, flat (RVA == file offset).
Instrument: `scratchpad/s140t2/L5/pe5.py` — a from-scratch PE reader + capstone-5.0.7 recursive-descent
CFG written for this lane, importing **nothing** from `scratchpad/s140/syn/` or `tools/`.

---

## HEADLINE

**If `StartNewPhysics` runs, the wall is `CalcVelocity`'s input-acceleration clamp, and it is one
compare against `1.0e-4`.**

```
0x035D605B  mulss xmm11, [rbx+0x3d0]     ; MaxSpeed *= AnalogInputModifier
0x035D607A  maxss xmm11, xmm0            ; MaxInputSpeed = max(that, GetMinAnalogSpeed())
   ...
0x035D64F2  comisd xmm8, xmm9            ; NewMaxInputSpeed  vs  1.0e-4  (.rdata 0x076B49E8)
0x035D650F  jae 0x035D6534               ; >= 1e-4 -> normal clamp
0x035D6511  movups xmm1, [.data 0x99C86A0]   ; ZeroVector
0x035D6520  movups [rbx+0xe8], xmm1      ; *** Velocity.XY := 0 ***
0x035D6527  movsd  [rbx+0xf8], xmm2      ; *** Velocity.Z  := 0 ***
```

`MaxInputSpeed < 1e-4` ⇒ **`Velocity` is written to exactly `(0,0,0)` every frame, whatever
`Acceleration` is** — including immediately after the `Velocity += Acceleration*DeltaTime` store two
instructions earlier (`0x035D64F7/FF/07`). That is a complete mechanical account of S139 flight 4:
`Acceleration = ControlInputVector x 50000` and `Velocity == (0,0,0)`.

`MaxInputSpeed` has **three** inputs, and each is independently capable of being zero:

| term | address | how it can be 0 | measured? |
|---|---|---|---|
| `GetMaxSpeed()` | vt disp `0x4C8` → Loki `0x055ACB90` | **GAS-backed**: tail-jumps to `[Owner_vt+0xC00]`, which returns **`0.0f`** when `Character+0xF08 AttributeSetStorage == NULL` (`0x055ACB73 xorps xmm0,xmm0; ret`) | **NEVER READ LIVE** |
| `AnalogInputModifier` | `CMC+0x3D0` | `ComputeAnalogInputModifier()` returns 0 when `Acceleration==0` **or** `GetMaxAcceleration()<=1e-8` | **0** on bot AND player — but **S139 flight 1, i.e. BEFORE ARM G**. Post-ARM-G value UNKNOWN |
| `GetMinAnalogSpeed()` | vt disp `0x7C8` → `0x035E3D20` (**not** overridden) | returns `MinAnalogWalkSpeed @CMC+0x290` for MovementMode ∈ {1,2,3}; **MOVE_Falling(3) is in that set** | **NEVER READ LIVE** |

⇒ **Three free live reads settle whether this is the wall: `CMC+0x3D0`, `CMC+0x290`, and
`GetMaxSpeed()`'s inputs.** All are read-only, all fit in an existing probe. See §5.

---

## 0. CONTROLS (run before any analysis, my own code)

| control | result |
|---|---|
| PE flat (10/10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase from optional header | **`0x7FF608F40000`** |
| Known-DARK control `0x5A6AC40` page non-zero bytes | **0 / 4096** PASS |
| Five fold constants byte-exact (`c20000`/`33c0c3`/`32c0c3`/`b001c3`/`0f57c0c3`) | **5/5 PASS** |
| `ULokiCMC` vtable `.rdata 0x088F8570`, known disps `0xAA8 0x720 0x6B8 0x890 0xA50 0x678` | **6/6 PASS** (agree with Tier 1) |
| Engine `UCMC` vtable `.rdata 0x07FBED58`, same disps | **6/6 PASS** (two-sided: engine bodies at the same disps) |
| Every function transcribed below: page non-zero | 3567–4039 / 4096, all LIT |

⚠ **`.text` is 55.48 % decrypted in `merged13`. Every census here is a FLOOR.** Specifically: the
image-wide "who else calls disp `0x4C8`/`0x7D0`" question was **not** attempted, and any claim of the
form "nothing else writes X" in this file is bounded by decryption.

⚠ **Write classification is from `operands[0].type == MEM`, never `regs_access`** (S140 recorded
defect). The `movups [rbx+0xe8], xmm1` stores in §4 are exactly the ones a `CS_AC_WRITE` filter drops.

⚠ `tools/strxref/index/pdata_union.csv` was **not** used anywhere in this lane; every extent below
comes from recursive descent with a printed gap count.

---

## 1. TASK 1 — `ULokiCMC::PhysFalling`

### 1.1 The anchor is VERIFIED, two ways, and it is not what Tier 1 said it opens with

**[M] `ULokiCMC` vtable disp `0x830` → `0x055B89F0`; engine sibling `EngVT+0x830` → `0x035EC850`.**
Neighbour controls at `+0x820/+0x828/+0x838/+0x840` all read **identical** in both vtables, so `0x830`
is a genuine Loki override rather than a vtable-alignment artifact.

**Second, independent confirmation (§3): the engine `StartNewPhysics` 8-entry jump table's
index 3 (`MOVE_Falling`) dispatches through `call [rax+0x830]`.** So `0x830` *is* `PhysFalling`,
named from its dispatcher rather than from a repo memory.

⚠⚠ **CORRECTION to `docs/s140-tier1-cfg.md` §5 rank-5.** It says the slot's *"body opens
`cmp byte [rcx+0x231], 7`"*. **It does not.** `0x055B89F0` opens with a 13-instruction prologue and a
`call 0x035EC850`. The `cmp byte [rcx+0x231], 7` the lead saw belongs to a **different function** —
`0x055ACB90`, which is `GetMaxSpeed` (§4.1). `[rcx+0x231]==7` does appear inside Loki `PhysFalling`,
but at `0x055B8E50`, 0x460 bytes in and deep past the Super. Grade the Tier-1 line **REFUTED**.

### 1.2 CFG (my own recursive descent)

| quantity | value |
|---|---|
| instructions | **370** |
| extent | `0x055B89F0 .. 0x055B90F1` |
| span / covered / **gaps** | 1793 / 1793 / **0** |
| decode failures | **0** |
| indirect jumps | **0** |
| `ret` instructions | **1** (`0x055B90AD`) |
| direct call sites / distinct targets | 25 / **23** |
| indirect call sites | 2 |

**[M] 23/23 distinct direct targets are REAL (0 FOLD, 0 DARK).** Graded three-state against the five
known folds *and* by page population; the sixth stub shape (`sub rsp,0x28 / call GetWorld /
xor eax,eax / ret`) was watched for and **is not present** — no callee here matches it.

### 1.3 [M] IT CALLS THE ENGINE SUPER **UNCONDITIONALLY**

```
0x055B8A28  48 8b d9              mov  rbx, rcx
0x055B8A2B  e8 20 3e 03 fe        call 0x035EC850     ; UCharacterMovementComponent::PhysFalling
```

Sound proof, the same shape Tier 1 used for `PerformMovement`'s Super:

```
entry -> 0x055B8A2B is straight-line: 13 instructions, ZERO branches, lands exactly on it
|reach_backward(0x055B8A2B)| = 14      entry in R: True      exit edges from R: []   (EMPTY)
```

⇒ **`ULokiCMC::PhysFalling` is a post-Super decorator. The physics of falling are entirely the
engine's.** Anything that stops the pawn falling is *not* in the Loki override's guards.

### 1.4 Structure of the Loki body (after the Super)

| region | what it does |
|---|---|
| `0x055B8A30`–`0x055B8A64` | three silent bails: `CharacterOwner @+0x198 == NULL`; a class test `0x012C7DD0` on `&CharacterOwner`; owner NULL again. **All three jump to the epilogue `0x055B9087`.** |
| `0x055B8A6A` | `cmp byte [CharacterOwner+0x160], 2` / `jb 0x055B8E30` — **`Role < ROLE_AutonomousProxy`** skips the whole ledge/assist block. `Role` is **measured 3** on bot and player (S139 f1), so this passes. |
| `0x055B8A93`–`0x055B8E2B` | a timed, trace-driven assist (`[rbx+0x1618]` flag, `[rbx+0x162C]` countdown, `[rbx+0x1620/0x1624/0x1628]` params, one `0x035B2510` sweep with `TraceChannel = 3`, then a `maxsd` into **`Velocity.Z @+0xF8`** at `0x055B8F26`). Gated on `[rbx+0x162C] > 0`; the field is reset to **`-1.0f`** at `0x055B8E0B`, so it is normally OFF. |
| `0x055B8E30`–`0x055B8F36` | `0x0565E180(this, 0x23)` then a coyote-time / grace window using `[rbx+0x1600..0x1614]`, `IsStunned 0x055B2930`, `0x055AA870`. |
| `0x055B8F36`–`0x055B906D` | **a speed clamp** — see 1.5. |
| `0x055B907A` | `call 0x055B9100(this, dt, Iterations, CharacterOwner)` — a large Loki tail routine that is a **no-op unless `MovementMode == MOVE_Custom(7)` with `CustomMovementMode ∈ {2,3,5}`, or `CharacterOwner == NULL`** (`0x055B912D`–`0x055B9169`, all four paths → `0x055B9D5B`). In `MOVE_Falling` it does nothing. |

### 1.5 [M] Velocity-zeroing sites inside `ULokiCMC::PhysFalling` — and why neither fires today

```
0x055B8F36  movss  xmm2,[rbx+0x1678]     ; a speed cap
0x055B8F3E  comiss xmm2, xmm6(0.0)
0x055B8F52  jb 0x055B906D                ; cap < 0  -> SKIP EVERYTHING
0x055B8F58..0x055B8F7F                   ; speed = sqrt(Vel.X^2+Vel.Y^2); if speed <= cap -> 0x055B9063
0x055B8F9B  call 0x056FC1A0              ; interp the cap toward the target
0x055B8FA9  comisd xmm4, [.rdata 0x076B49E8 = 1.0e-4]
0x055B8FB1  jae 0x055B8FD2
0x055B8FBE  movups [rbx+0xe8], xmm1      ; *** Velocity.XY := 0  (Z preserved) ***
   ...
0x055B9063  mov dword [rbx+0x1678], 0xBF800000   ; cap := -1.0f  (the resting value)
```

**[I, strong] Neither fires in the observed state:** `[rbx+0x1678]` is written `-1.0f` by this same
function (`0x055B9063`) and `-1.0f < 0.0` takes the `jb` at `0x055B8F52` on the following frame. It is
a dash/knockback decay cap, not a general clamp. ⚠ **`CMC+0x1678` has never been read live** — it is a
cheap addition to any probe, and if it is ever `>= 0` this is a *second* velocity killer.

⚠ Note the shared constant: `1.0e-4` at `.rdata 0x076B49E8` is used **both** here and by
`CalcVelocity`'s clamp (§4) and by `ULokiCMC::PerformMovement`'s `+0x16D0` receipt guard (Tier 1 §2.2).
Seeing it in a listing does not identify which of the three you are in.

---

## 2. ENGINE `PhysFalling 0x035EC850` — where the falling actually is

CFG: **1482 instructions, extent `0x035EC850..0x035EE593`, span 7491, covered 7491, gaps 0, decode
failures 0.** 36 direct call sites / **13** distinct targets (all REAL), **43 indirect** sites.

**Loop-level early-outs [M]:**

```
0x035EC87E  comiss xmm6, [.rdata 0x076B8E74 = 1e-06]
0x035EC881  jb 0x035EE577                     ; deltaTime < MIN_TICK_TIME -> return
0x035EC967  mov eax, [rdi+0x3e4]              ; MaxSimulationIterations
0x035EC979  cmp r12d, eax
0x035EC97C  jge 0x035EE507                    ; Iterations >= MaxSimulationIterations -> EXIT LOOP
```

★★ **`CMC+0x3E4 MaxSimulationIterations` gates BOTH engine `StartNewPhysics` (`0x036009B5 cmp r8d,
[rcx+0x3e4]` / `0x036009BC jge`) AND this loop.** It is the single field whose being `<= 0` would
explain "no velocity" **and** "no falling" at once, with `Iterations == 0` on entry. Tier 1 ranked
reading it #3 / free; **Lane 5 raises it to joint-first**, because it is the only known single value
that closes both phenomena. **NEVER READ LIVE.**

**The stock UE structure, matched byte for byte:**

| stock line | site | vtable disp | Loki override? |
|---|---|---|---|
| `FallAcceleration = GetFallingLateralAcceleration(dt)` | `0x035EC8BB` | `0x838` → `0x035E3490` | no |
| `bHasLimitedAirControl = ShouldLimitAirControl(...)` | `0x035EC91B` | `0x840` → `0x035FC2C0` | no |
| `MaxDecel = GetMaxBrakingDeceleration()` | `0x035ECA58` | `0x7D8` → `0x035E3B10` | no |
| `HasAnimRootMotion()` / `CurrentRootMotion.HasOverrideVelocity()` | `0x035ECA5E` / `0x035ECA95` | `[rdi+0xF50]`, `0x037DD3E0` | — |
| `Velocity.Z = 0` | `0x035ECBD1 mov [rdi+0xf8], r13` (r13 = 0) | — | — |
| **`CalcVelocity(timeTick, FallingLateralFriction, false, MaxDecel)`** | `0x035ECBD8` (and `0x035ECB75`) | **`0x7B0` → `0x035D5D20`** | **NO — engine impl** |
| `Velocity.Z = OldVelocity.Z` | `0x035ECBDE movsd [rdi+0xf8], xmm14` | — | — |
| `Gravity = (0,0,GetGravityZ())` | `0x035ECC21` | `0x4C0` → **`0x055AB8C0`** | **YES** |
| **`Velocity = NewFallVelocity(Velocity, Gravity, GravityTime)`** | `0x035ECCEF` | `0x7A0` → **`0x055B6AD0`** | **YES** |
| `CharacterOwner->CheckJumpInput(timeTick)` | `0x035ECCC6` | character `0x970` | — |
| `ApplyRootMotionToVelocity(timeTick)` | `0x035ECD0F` | `0xC80` → `0x035D4580` | no |

**Argument proof for `CalcVelocity` = disp `0x7B0` [M]:** the call is bracketed by
`mov [rdi+0xf8], r13` (Velocity.Z := 0) and `movsd [rdi+0xf8], xmm14` (Velocity.Z := OldVelocity.Z);
`xmm2 = [rdi+0x2bc]` (**FallingLateralFriction**), `xmm1 = xmm10` (timeTick), `r9d = 0` (**bFluid**),
`[rsp+0x20] =` the value returned by `GetMaxBrakingDeceleration` (**BrakingDeceleration**). That is
stock `PhysFalling`'s Compute-Velocity block, term for term, with the MS-x64 slot mapping
(this=rcx, dt=xmm1, Friction=xmm2, bFluid=r9, BrakingDecel=[rsp+0x20]) all four accounted for.

### 2.1 [M] The two Loki overrides on the gravity path do **not** suppress gravity

```
ULokiCMC::GetGravityZ 0x055AB8C0
  if (MovementMode==7 && CustomMovementMode in {3,4} )                   -> return 0.0f
  if (MovementMode==7 && CustomMovementMode==2 && [this+0x1318]!=0)      -> return 0.0f
  else 0x055AB929: xmm6 = Super 0x035E3650(this);
       if (MovementMode==7 && CustomMovementMode==7 && 0x055A4C40(this) <= 0) xmm6 = 0
       return xmm6
```

```
ULokiCMC::NewFallVelocity 0x055B6AD0
  call 0x035E8B00                      ; the ENGINE impl, UNCONDITIONAL, instruction #6
  if (MovementMode==7 && CustomMovementMode==1)
      out->Z = max( -[this+0x1140], min(out->Z, 0.0) )    ; a terminal-velocity clamp
  return out
```

**In `MOVE_Falling(3)` both reduce to the engine behaviour.** ⇒ **gravity is not switched off by
Loki.** If the pawn does not fall, the cause is upstream (the step not running) or downstream (the
move being blocked), **not** these two.

---

## 3. TASK 2 — THE `StartNewPhysics` DISPATCH TABLE, VERIFIED

`0x03600A6C movzx esi, byte [rbx+0x231]` (MovementMode) · `0x03600A7B cmp esi, 7` ·
`0x03600A7E ja 0x03600B35` (default) · `0x03600A84 lea rdx,[rip-0x3600A8B]` (**rdx = ImageBase**) ·
`0x03600A8B mov ecx,[rdx + rsi*4 + 0x03600BF8]` · `0x03600A92 add rcx,rdx` · `0x03600A95 jmp rcx`.

⇒ **8 entries, stored as RVAs, at `.text 0x03600BF8`.** Raw bytes (32 B, followed by `cc` padding):

```
a8 0b 60 03  97 0a 60 03  ae 0a 60 03  c5 0a 60 03
f3 0a 60 03  dc 0a 60 03  0a 0b 60 03  21 0b 60 03
```

| idx | `EMovementMode` (this build) | table target | vtable disp | engine impl | **ULokiCMC impl** | override? |
|---|---|---|---|---|---|---|
| 0 | `MOVE_None` | `0x03600BA8` | — | — | — | joins the epilogue; **no `Phys*` call** |
| 1 | `MOVE_Walking` | `0x03600A97` | `0x970` | `0x035EF960` | `0x035EF960` | no |
| 2 | `MOVE_NavWalking` | `0x03600AAE` | `0x978` | `0x035EEA50` | `0x035EEA50` | no |
| **3** | **`MOVE_Falling`** | `0x03600AC5` | **`0x830`** | `0x035EC850` | **`0x055B89F0`** | **YES** |
| 4 | `MOVE_Swimming` | `0x03600AF3` | `0x988` | `0x035EF1D0` | `0x035EF1D0` | no |
| 5 | `MOVE_Flying` | `0x03600ADC` | `0x980` | `0x035EE5A0` | `0x035EE5A0` | no |
| 6 | **`MOVE_Dashing` (LOKI-INSERTED)** | `0x03600B0A` | `0xCC8` | `0x035EB870` | `0x035EB870` | no |
| 7 | `MOVE_Custom` | `0x03600B21` | `0x990` | `0x035EB850` | **`0x055B88E0`** | **YES** |

★ **CLAUDE.md's recorded "case 6 → disp `0xCC8` (PhysDashing), case 7 → disp `0x990` (PhysCustom)" is
CONFIRMED exactly**, and the `cmp esi,7` bound is confirmed. Two new facts:

- **[M] `MOVE_Dashing`'s slot `0xCC8` is present in the ENGINE vtable too, with the same target.**
  Loki added `PhysDashing` by forking the *engine*, not by overriding in `ULokiCMC`. (Consistent with
  `EMovementMode` itself having been modified — CLAUDE.md's three-instrument finding.)
- ⚠ **The table is not in address order** — idx 4 (`0x03600AF3`) sits *after* idx 5 (`0x03600ADC`) in
  memory. Reading the case bodies in address order and numbering them 0..7 mislabels Swimming and
  Flying. **Read the table, never the layout.**

**Engine `StartNewPhysics 0x03600990` early-outs, complete [M]:**

```
0x036009A8  comiss xmm6,[rip -> const]          / 0x036009AF jb  0x03600BE6   ; deltaTime < MIN_TICK_TIME
0x036009B5  cmp r8d,[rcx+0x3e4]                 / 0x036009BC jge 0x03600BE6   ; Iterations >= MaxSimulationIterations
0x036009C5  call [rax+0x6b8] HasValidData       / 0x036009CD je  0x03600BE6
0x036009E4  call [UpdatedComp_vt+0x4c0]         / 0x036009EC je  0x03600A57   ; IsSimulatingPhysics -> abort+log
0x036009EE  cmp byte [rip+0x6985473], 5         / 0x036009F5 jb  0x03600BE6   ; = .data 0x09F85E68, LogCharacterMovement verbosity
```

★ `.data 0x09F85E68` reproduces CLAUDE.md's recorded `LogCharacterMovement` category address exactly —
an unplanned control on both. ⚠⚠ **THE TWO `+0x4C0`s ARE DIFFERENT FUNCTIONS.** `[UpdatedComponent_vt
+0x4C0]` is `IsSimulatingPhysics` (a `UPrimitiveComponent`); `[CMC_vt + 0x4C0]` is **`GetGravityZ`**
(`0x035E3650` engine / `0x055AB8C0` Loki). Same displacement, unrelated hierarchies — a live
displacement scan that does not resolve the base object will fuse them.

---

## 4. TASKS 3 & 4 — `GetMaxSpeed`, `GetMaxAcceleration`, `CalcVelocity`

### 4.1 [M] `GetMaxSpeed` is vtable disp `0x4C8`, Loki impl `0x055ACB90` — VERIFIED

Verified three ways, not assumed: (a) `LokiVT+0x4C8 == 0x055ACB90` by an exhaustive scan of both
vtables for that pointer (exactly one hit, at `+0x4C8`); (b) the engine sibling `EngVT+0x4C8 =
0x035E3C20` is a `cmp eax,7`-bounded `MovementMode` switch whose walking case returns
`IsCrouching() ? [this+0x27C] : ...` — stock `GetMaxSpeed()`; (c) `CalcVelocity` calls disp `0x7D0`
then disp `0x4C8` back to back at `0x035D5DFA` / `0x035D5E09`, which is stock
`const float MaxAccel = GetMaxAcceleration(); float MaxSpeed = GetMaxSpeed();`.

```
ULokiCMC::GetMaxSpeed 0x055ACB90                      (REAL, page 3729/4096)
  0x055ACB96  cmp byte [rcx+0x231], 7        ; MOVE_Custom
  0x055ACBA2  cmp byte [rcx+0x232], 1        ; CustomMovementMode 1
  0x055ACBAB  movss xmm0, [.rdata 0x077C7718 = 300.0f]  ; -> return 300.0f
  0x055ACBBE  rdi/rbx = [rcx+0xB8]           ; UActorComponent::Owner  (S132: comp+0xB8)
  0x055ACBC8  if (!Owner) -> 0x055ACBED
  0x055ACBCD  call 0x054F8C40(Owner)         ; a class test (struct-array IsA family, cf. 0x054F8DC0)
  0x055ACBD4  if (!ok) -> 0x055ACBED
  0x055ACBE6  jmp qword [Owner_vt + 0xC00]   ; *** TAIL-CALL THE CHARACTER ***
  0x055ACBED: 0x055ACBFA  jmp 0x035E3C20     ; else the engine GetMaxSpeed
```

### 4.2 ★★★★★ [M] IT IS GAS-BACKED — THE **SAME** SLOT `GetMaxAcceleration` USES

```
ALokiCharacter vtable +0xC00  ->  0x055AC9F0        (Tier 1 §4.6 already identified this vtable)
  0x055AC9FA  rbx = [rcx + 0xF08]            ; *** AttributeSetStorage ***
  0x055ACA07  if (!rbx) -> 0x055ACB73
  0x055ACA0D  if (0x055B18E0(this)) -> 0x055ACB73
  0x055ACA1A  if ([this+0xB59] == 0) -> 0x055ACB73
  0x055ACA38  xmm6 = 0x055266E0(rbx)         ; base value
  0x055ACA3D  walk [this+0x16F0] .. Num [this+0x16F8], stride 0x38   ; modifier stack (4 kinds)
  0x055ACB0A  scale by [this+0x16CC]/[this+0x16D0]/[this+0x16E0] if [this+0x16D8] != NULL
  0x055ACB53  if (result <= 0) result = 0
  0x055ACB73:  xorps xmm0, xmm0 ; ret         ; *** RETURNS 0.0f ***
```

```
0x055266E0 :  min( 0x01F62B10(rbx+0xF0), 0x01F62B10(rbx+0x100) )
0x01F62B10 :  f3 0f 10 41 0c c3   =  movss xmm0,[rcx+0xC]; ret
```

★ **`0x01F62B10` reading `+0xC` is `FGameplayAttributeData::CurrentValue`** — it lands exactly on
CLAUDE.md's recorded ARM-G recipe *"write at `FGameplayAttributeData` `+0x8` **and** `+0xC`"*, from a
completely different direction. So the base value is **`min(AttrSet+0xF0, AttrSet+0x100)`** =
`min(MoveSpeed, MaxMoveSpeed)` — the exact two attributes ARM G writes as 500.

```
ULokiCMC::GetMaxAcceleration 0x055AC910   (vt disp 0x7D0)
  MovementMode == 1 (Walking):
      v = [Owner_vt+0xC00]();      if (v == 0.0f) -> 0x055AC9AE: return 0.0f
      rcx = [Owner + 0xF08];       if (!rcx) -> engine fallback
      return 0x01F62B10(rcx + 0x120)                       ; AttrSet+0x120 = MaxAcceleration attribute
  MovementMode == 3 (Falling) or 6 (Dashing):
      v = [Owner_vt+0xC00]();      if (v != 0.0f) -> 0x055AC9BC: jmp 0x035E3AD0   ; ENGINE
                                   else            -> 0x055AC9AE: return 0.0f
  otherwise: jmp 0x035E3AD0 (engine)
engine GetMaxAcceleration 0x035E3AD0:
      if ([vt+0xCE0]()) return [this+0x1040];  else return [this+0x28C]   ; MaxAcceleration
```

★★★★★ **THIS REPRODUCES S139 FLIGHTS 3 AND 4 EXACTLY, FROM THE BYTES, WITH NO FREE PARAMETERS.**
The bot is `MOVE_Falling(3)`:

- **Untreated** (`+0xF08 == NULL`) ⇒ `[Owner_vt+0xC00]` returns `0.0f` ⇒ `ucomiss` equal ⇒ fall through
  to `0x055AC9AE xorps xmm0,xmm0; ret` ⇒ **`GetMaxAcceleration() == 0`**. That is S139 flight 3's
  measured wall.
- **After ARM G** (`MoveSpeed = MaxMoveSpeed = 500`) ⇒ `0xC00` returns `500 != 0` ⇒
  `jne 0x055AC9BC` ⇒ engine ⇒ **`[CMC+0x28C] = MaxAcceleration`**, which CLAUDE.md records as live
  **50000**. That is S139 flight 4's measured `Acceleration = input x 50000`.

Two independently measured numbers (0 and 50000) both fall out of this one function. **[M]**

### 4.3 [M] `CalcVelocity` IS THE ENGINE'S — `ULokiCMC` DOES **NOT** OVERRIDE IT

**vtable disp `0x7B0`; `EngVT+0x7B0 == LokiVT+0x7B0 == 0x035D5D20`.**
CFG: **547 instructions, extent `0x035D5D20..0x035D6786`, span 2662, covered 2662, gaps 0, decode
failures 0, 1 direct callee (`0x03630250`), 11 indirect.**

**Early-outs, byte-exact, all four stock:**

```
0x035D5D53  call [rax+0x6b8] HasValidData     / je 0x035D676A
0x035D5D61  cmp byte [rbx+0xf50], 0           / jne 0x035D676A        ; HasAnimRootMotion
0x035D5D6E  comiss xmm10,[.rdata 0x076B8E74]  / jb 0x035D676A         ; DeltaTime < 1e-06
0x035D5D88  cmp byte [CharacterOwner+0x160],1 / (Role == ROLE_SimulatedProxy)
0x035D5D91  test byte [rbx+0x54f], 1          / je 0x035D676A         ; && !bWasSimulatingRootMotion
```

`Role @+0x160` is **measured 3** (S139 f1, bot and player) ⇒ the fourth gate passes.
`HasValidData` and `DeltaTime` are the same terms Tier 1 already measured passing upstream.

**Callee map (all confirmed against stock UE 5.4 `CalcVelocity` line for line):**

| site | disp | engine | Loki | stock line |
|---|---|---|---|---|
| `0x035D5DFA` | `0x7D0` | `0x035E3AD0` | **`0x055AC910`** | `MaxAccel = GetMaxAcceleration()` |
| `0x035D5E09` | `0x4C8` | `0x035E3C20` | **`0x055ACB90`** | `MaxSpeed = GetMaxSpeed()` |
| `0x035D5E6F` | `0x790` | `0x035D4210` | same | `ApplyRequestedMove(...)` |
| `0x035D6055` | `0x7C8` | `0x035E3D20` | same | `GetMinAnalogSpeed()` |
| `0x035D60BB`/`0x035D60EF` | `0x4D0` | `0x0363BA00` | same | `bVelocityOverMax = IsExceedingMaxSpeed(MaxSpeed)` |
| `0x035D6141` | `0x9D0` | `0x035D4810` | same | `ApplyVelocityBraking(...)` |
| **`0x035D6467`** | `0x4D0` | `0x0363BA00` | same | **`IsExceedingMaxSpeed(MaxInputSpeed)` — the input clamp** |
| `0x035D6604` | `0x4D0` | `0x0363BA00` | same | `IsExceedingMaxSpeed(RequestedSpeed)` — the *requested* clamp |

`IsExceedingMaxSpeed 0x0363BA00` is stock, byte-exact:
`Velocity.SizeSquared() > Square(max(0,MaxSpeed)) * 1.01f` (the `1.01` is `.rdata 0x07846530`).

`GetMinAnalogSpeed 0x035E3D20` is stock: `switch(MovementMode){ case 1,2,3: return [this+0x290]
(MinAnalogWalkSpeed); default: return 0.0f }`. **`MOVE_Falling(3)` is inside the returning set.**

### 4.4 ★★★★★ THE CLAMP — the answer to task 4

```
0x035D605B  mulss  xmm11, [rbx+0x3d0]                ; MaxSpeed *= AnalogInputModifier
0x035D6064  xorps  xmm8, xmm8
0x035D6068  ucomisd xmm8,[rbx+0x328] ...(+0x330,+0x338)  ; bZeroAcceleration = Acceleration.IsZero()
0x035D607A  maxss  xmm11, xmm0                       ; MaxInputSpeed = max(that, GetMinAnalogSpeed())
0x035D607F  movaps xmm7, xmm11
0x035D6083  maxss  xmm7, [rsp+0x44]                  ; MaxSpeed = max(RequestedSpeed, MaxInputSpeed)
   ... braking / friction branches ...
0x035D643A  movsd  xmm9, [.rdata 0x076B49E8 = 1.0e-4]
0x035D6443  test   r15b, r15b                        ; bZeroAcceleration
0x035D6457  jne 0x035D65C1                           ;   -> SKIP the input block
0x035D6460  movaps xmm1, xmm11                       ; MaxInputSpeed
0x035D6467  call [rax+0x4d0]                         ; IsExceedingMaxSpeed(MaxInputSpeed)
0x035D646F  je 0x035D64A3                            ;   false -> NewMaxInputSpeed = MaxInputSpeed
0x035D64A6  cvtss2sd xmm0, xmm11
0x035D64AB..0x035D64EA                               ; Velocity += Acceleration * DeltaTime
0x035D64F2  comisd xmm8, xmm9                        ; NewMaxInputSpeed  vs  1.0e-4
0x035D64F7  movsd [rbx+0xe8], xmm4                   ; store Velocity.X (the += result)
0x035D64FF  movsd [rbx+0xf0], xmm5                   ; store Velocity.Y
0x035D6507  movsd [rbx+0xf8], xmm6                   ; store Velocity.Z
0x035D650F  jae 0x035D6534                           ; >= 1e-4 -> the normal GetClampedToMaxSize
0x035D6511  movups xmm1, [.data 0x099C86A0]          ; ZeroVector
0x035D6518  movsd  xmm2, [.data 0x099C86B0]
0x035D6520  movups [rbx+0xe8], xmm1                  ; *** Velocity.XY := 0 ***
0x035D6527  movsd  [rbx+0xf8], xmm2                  ; *** Velocity.Z  := 0 ***
0x035D652F  jmp 0x035D65C9
```

This is stock `FVector::GetClampedToMaxSize`: `if (MaxSize < UE_KINDA_SMALL_NUMBER) return
ZeroVector;`. **[M] With `MaxInputSpeed == 0`, `Velocity` is written to exactly `(0,0,0)` on every
frame in which `Acceleration != 0`.**

⚠ Note the ordering: the `+=` result is committed to memory at `0x035D64F7/FF/07` **before** the zero
store at `0x035D6520/27`. An off-thread sampler that lands in that ~7-instruction window would read a
non-zero `Velocity`. Nobody has; but it means "Velocity is always (0,0,0)" is a *sampling* statement,
not a claim that the field is never written non-zero.

⚠⚠ **The block at `0x035D65F8..0x035D6727` is the *requested-acceleration* clamp, not this one.** It
is gated on `[rbp+0x80]` (the `ApplyRequestedMove` return, stored at `0x035D5E8E`) and uses
`[rsp+0x44] = RequestedSpeed`. On a pawn with no path-following request it is skipped entirely.
**Two nearly identical clamp blocks exist in this function; quoting the wrong one changes which
variable is on trial.** (I read the wrong one first; the discriminator is which register/stack slot
feeds `IsExceedingMaxSpeed` — `xmm11` = MaxInputSpeed vs `[rsp+0x44]` = RequestedSpeed.)

### 4.5 ★★ PRE-REGISTERED PREDICTIONS — write these down BEFORE the next flight

All follow from §4.1–§4.4 with no further assumption. `MinAnalogWalkSpeed @CMC+0x290` assumed at the
stock default `0.0f` (**assumption, not measured** — read it).

| # | quantity | UNTREATED player (`Char+0xF08 == NULL`) | TREATED bot after ARM G (`MoveSpeed = MaxMoveSpeed = 500`) |
|---|---|---|---|
| P1 | `[Owner_vt+0xC00]()` | **0.0** | **500.0** (x the `[+0x16F0]` modifier stack; empty ⇒ x1) |
| P2 | `GetMaxSpeed()` (disp `0x4C8`) | **0.0** | **500.0** |
| P3 | `GetMaxAcceleration()` (disp `0x7D0`) | **0.0** | **50000.0** = `CMC+0x28C` — already measured ✔ |
| P4 | `AnalogInputModifier @CMC+0x3D0` | **0.0** — already measured ✔ (S139 f1) | **≈ \|ControlInputVector\| ≈ 1.0**, because `ComputeAnalogInputModifier` = `clamp(\|Accel\|/MaxAccel,0,1)` and both terms are now non-zero |
| P5 | `MaxInputSpeed` | **0.0** ⇒ clamp fires ⇒ `Velocity := (0,0,0)` | **≈ 500** ⇒ clamp does **not** fire |
| P6 | consequence | Velocity 0 — but via the *braking* branch, since `bZeroAcceleration` is also true | **Velocity should be NON-ZERO.** If it is still `(0,0,0)`, §4 is NOT the wall and the step is not running |

★★ **P4 IS THE PIVOT AND IT HAS NEVER BEEN MEASURED IN THE TREATED STATE.** CLAUDE.md's
`AnalogInputModifier 0` is from **S139 flight 1**, an untreated bot — quoting it as the post-ARM-G
value would be a sample cited outside its arm, the same failure Tier 1 §3.2 recorded. **Grade "the
AnalogInputModifier is still 0 after ARM G" as [S], not [I].**

⚠ P4 also implies §4 may already be **CLOSED** by ARM G, in which case flight 4's null points back at
the step not running — i.e. straight to `MaxSimulationIterations`. **One read of `CMC+0x3D0` on a
treated bot discriminates the two, and it is free.**

★ Ordering note that makes P4 well-founded: `ControlledCharacterMove 0x035DCD10` stores
`Acceleration` at `0x035DCD6B` (S139 flight 3's signed-zero proof) and stores `AnalogInputModifier` at
`0x035DCD8F` — **36 bytes later, same function, same frame.** So the modifier is computed from the
Acceleration that ARM G made non-zero, not from a stale one.

---

## 5. TASK 5 — RANKED NEXT READS

Every row is read-only unless marked. Addresses are exact.

| # | read / transcribe | address | what it settles | cost |
|---|---|---|---|---|
| **1** | **`CMC+0x3E4 MaxSimulationIterations`** (int32) | `CMC+0x3E4` | `<= 0` explains **no velocity AND no falling with one value**: it bails engine `StartNewPhysics` at `0x036009BC` *and* skips `PhysFalling`'s loop at `0x035EC97C` with `Iterations == 0`. **Never read live.** | free — one dword |
| **2** | **`CMC+0x3D0 AnalogInputModifier`** (f32) on a **TREATED** bot | `CMC+0x3D0` | P4 / P6. `0` ⇒ §4's clamp is the live wall even post-ARM-G. `≈1` ⇒ §4 is closed and the wall is upstream (row 1). | free — one f32 |
| **3** | `CMC+0x290 MinAnalogWalkSpeed` (f32) | `CMC+0x290` | the third `MaxInputSpeed` term; `> 1e-4` **disarms** §4's clamp entirely and would refute this lane | free — one f32 |
| **4** | `GetMaxSpeed()` inputs on both pawns: `Char+0xF08`, `AttrSet+0xF0+0xC`, `AttrSet+0x100+0xC`, `Char+0xB59`, `Char+0x16F8` (modifier Num) | see §4.2 | P1 / P2 without calling anything | free — 5 reads |
| **5** | `CMC+0x1678` (f32) | `CMC+0x1678` | Loki `PhysFalling`'s own XY-zeroing cap (§1.5). Predicted `-1.0f`; anything `>= 0` is a **second** velocity killer nobody has looked for | free |
| 6 | `CMC+0x28C MaxAcceleration` / `CMC+0x3E0 MaxSimulationTimeStep` | — | `+0x28C` already measured 50000 (a passing control on this lane's model); `+0x3E0 <= 0` would collapse `timeTick` | free |
| 7 | **Transcribe `ApplyVelocityBraking` (disp `0x9D0` → `0x035D4810`)** | `0x035D4810` | the branch that runs *pre*-ARM-G (`bZeroAcceleration` true). Not overridden by Loki. Closes "why was Velocity 0 before ARM G" independently of §4 | offline |
| 8 | **Transcribe engine `NewFallVelocity 0x035E8B00`, `GetGravityZ 0x035E3650`, `GetFallingLateralAcceleration 0x035E3490`** | — | the gravity integrator, plus whether `AirControl == 0` makes `FallAcceleration` zero (which routes `PhysFalling` down the braking branch). §7 flags `0x035E3650` as the one un-transcribed gravity term | offline |
| 9 | Transcribe `ULokiCMC::PhysCustom 0x055B88E0` and the `MOVE_Dashing` slot `0x035EB870` | — | the two other Loki-touched movement modes; neither is on today's path but both are unread | offline |
| 10 | Resolve `0x054F8C40`'s target class (via the lazy `StaticClass` getter `0x052F01E0`) | — | if the owner is not that class, **both** Loki getters fall through to the engine and the entire GAS story in §4.2 is bypassed | offline |
| 11 | Transcribe `0x055B9100` past `0x055B9D5B` | `0x055B9100` | Loki `PhysFalling`'s tail routine; **[M] inert in `MOVE_Falling`**, so low value until a custom mode is in play | offline |
| — | ⛔ **Do NOT** pin `LogCharacterMovement` expecting the `StartNewPhysics` abort line | `.rdata 0x07FC0670` | it fires only when `IsSimulatingPhysics()` is TRUE, which S139 measured FALSE. Tier 1 already graded it negative-only | — |

★ **Rows 1–5 are nine scalar reads and they jointly decide between the two surviving worlds** (the step
does not run / the step runs and the clamp kills it). They cost one probe pass and no write, and they
are compatible with Tier 1's recommended `+0x16B0` sentinel poke in the same sitting.

---

## 6. CORRECTIONS AND NEW FACTS FOR `CLAUDE.md` / `docs/s140-tier1-cfg.md`

1. ⚠⚠ **`docs/s140-tier1-cfg.md` §5 rank-5 is REFUTED**: `ULokiCMC::PhysFalling 0x055B89F0`'s body does
   **not** open `cmp byte [rcx+0x231], 7`. It opens with a prologue and an unconditional
   `call 0x035EC850` (the engine Super). The `cmp` belongs to `GetMaxSpeed 0x055ACB90`.
2. ★ **NEW [M]: `ULokiCMC::PhysFalling` calls its Super unconditionally** — 13 straight-line
   instructions, `|reach_backward(Super)| = 14`, entry ∈ R, **exit edges = [] (empty)**.
3. ★ **NEW [M]: `CalcVelocity` is vtable disp `0x7B0` and is NOT overridden by `ULokiCMC`**
   (`EngVT+0x7B0 == LokiVT+0x7B0 == 0x035D5D20`). CLAUDE.md's S139 next-step line calls it a function
   "nobody has read"; it is now read (547 instructions, 0 gaps, 0 decode failures).
4. ★ **NEW [M]: `GetMaxSpeed` = disp `0x4C8`, Loki `0x055ACB90`, and it IS GAS-backed through the SAME
   `ALokiCharacter` vtable slot `0xC00` (`0x055AC9F0`) that `GetMaxAcceleration` uses**, which returns
   **`0.0f` at `0x055ACB73`** when `Char+0xF08 AttributeSetStorage == NULL`.
5. ★ **NEW [M]: the GAS base value is `min(AttrSet+0xF0, AttrSet+0x100)`** via
   `0x055266E0` → `0x01F62B10 = movss xmm0,[rcx+0xC]; ret`, independently confirming CLAUDE.md's
   ARM-G recipe (`FGameplayAttributeData` CurrentValue at `+0xC`).
6. ★ **NEW [M]: `MaxAcceleration @CMC+0x28C`** (engine `GetMaxAcceleration 0x035E3AD0` fallback) and
   **`MinAnalogWalkSpeed @CMC+0x290`** (`GetMinAnalogSpeed 0x035E3D20`) — adjacent, easily confused.
7. ★ **NEW [M]: `AnalogInputModifier @CMC+0x3D0`**, three agreeing sites: written by
   `ControlledCharacterMove` at `0x035DCD8F` (its **only** `+0x3D0` store), written `1.0f` by
   `CalcVelocity`'s `bForceMaxAccel` branch at `0x035D601D`, and multiplied into `MaxSpeed` at
   `0x035D605B`.
8. ⚠ **CLAUDE.md's `AnalogInputModifier 0` is an S139-flight-1 (UNTREATED) sample.** Do not carry it
   into any post-ARM-G statement.
9. ★ **NEW [M]: `CMC+0x3E4 MaxSimulationIterations` gates BOTH engine `StartNewPhysics` and
   `PhysFalling`'s loop.** Tier 1 found the `StartNewPhysics` half (§7 row 3) and did not connect the
   second; it is the only known single value that closes both open phenomena.
10. ⚠⚠ **`[UpdatedComponent_vt + 0x4C0] = IsSimulatingPhysics` and `[CMC_vt + 0x4C0] = GetGravityZ`**
    are different functions at the same displacement in different hierarchies. Tier 1 §1.5 uses the
    first; §2 above uses the second.
11. ★ **NEW [M]: Loki's `GetGravityZ 0x055AB8C0` and `NewFallVelocity 0x055B6AD0` both reduce to the
    engine behaviour in `MOVE_Falling`** — gravity is not switched off by a Loki override.
12. ⚠ The `StartNewPhysics` jump table is **not** in address order (idx 4 after idx 5). Reading case
    bodies in address order mislabels Swimming and Flying.
13. ★ CLAUDE.md's `MOVE_Dashing`-at-index-6 / `MOVE_Custom == 7` finding is **CONFIRMED by a fourth
    instrument** (the table read directly, with all 8 targets resolved to vtable displacements).

---

## 7. WHAT THIS LANE DOES **NOT** SHOW

- **Nothing here was flown.** Every claim is static analysis over `merged13` plus S139's banked live
  reads. The pawn still moves 0.00 uu.
- **It does not show `StartNewPhysics` runs.** Tier 1 removed the evidence against; this lane supplies
  none for. If it does not run, §4 is irrelevant and row 1 of §5 is the whole story.
- **It does not explain "a `MOVE_Falling` pawn with `GravityScale 1.000` does not fall."** §2.1 rules
  out the two Loki overrides on the gravity path, and §4 cannot do it either — `PhysFalling` restores
  `Velocity.Z` from `OldVelocity.Z` *after* `CalcVelocity` (`0x035ECBDE`), so the clamp's Z-zeroing is
  undone before gravity is applied. That leaves: the loop not running (row 1), engine `GetGravityZ
  0x035E3650` returning 0, or the move being blocked downstream. **`0x035E3650` was NOT transcribed.**
- **`0x054F8C40`'s target class is [I], not [M]** — it is the struct-array `IsA` family (same shape as
  `0x054F8DC0`, and it carries the `Mismatch NumStructBa…` diagnostic literal), but the class comes
  from a lazy `StaticClass` getter (`0x052F01E0`) that this lane did not resolve. If the owner is *not*
  that class, both Loki getters fall through to the engine and §4.2's whole GAS story is bypassed.
- **`bForceMaxAccel @CMC+0x2E9` bit `0x02`** (`0x035D5E75 test byte [rbx+0x2e9], 2`) was not read live.
  If it were set, `AnalogInputModifier` is forced to `1.0f` at `0x035D601D` and P4 is trivially true.
  ⚠ CLAUDE.md records `+0x2E9` bit `0x04` as `bForceNextFloorCheck` — **same byte, different bit**;
  do not conflate them.
- **All censuses are FLOORS** at `.text` 55.48 % decrypted. In particular no image-wide search for
  other writers of `CMC+0xE8/F0/F8`, `+0x3D0` or `+0x3E4` was run, and no attempt was made to find a
  `memcpy`/`rep movs`/register-computed writer.

**Harness:** `scratchpad/s140t2/L5/pe5.py` (read-only, offline, re-runnable).
All `.rdata`/`.data` reads above are from `merged13`, which is `.text`-only merged, so its `.rdata` and
`.data` come from one seed — but no **mutable global's value** is load-bearing in this file. The
`.data` addresses cited (`0x099C86A0`, `0x099C86B0`, `0x09F85E68`) are used as *addresses*, not values.
