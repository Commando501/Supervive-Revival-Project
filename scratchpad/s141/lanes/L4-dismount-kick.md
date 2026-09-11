# L4 — T3-B part 2: THE DISMOUNT. How a hero escaped the fixed point (S132), read from the bytes.

Image: `dumps/merged14.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (va==praw on all 10 sections).
Offline only: zero launches, zero injection, zero live-process access.
Tools written this lane: `scratchpad/s141/lanes/L4_{controls,dis,dis2,grade,vt,grav,writes}.py`.

---

## 0. CONTROLS (all PASS — run and printed before any analysis)

```
DARK negative control  0x5A6AC40 ULokiRespawnComponent::Respawn      page_nonzero =    0/4096   PASS
FOLDS byte-exact       0x0F7EC20 c20000    0x0F7EB50 33c0c3   0x0F7EB60 32c0c3
                       0x0B9E1F0 b001c3    0x0FC6CF0 0f57c0c3                    5/5 PASS
LIT positive controls  0x55CCCB0 detach (TARGET)            3689/4096   LIT
                       0x55D89F0 GetLandingTeleportLocation 3732/4096   LIT
                       0x5599040 SetPredropHidden           3726/4096   LIT
                       0x339A550 SetActorEnableCollision    3708/4096   LIT
                       0x55AC8E0 GetLokiCharacterMovement   3729/4096   LIT
                       0x035EC850 ENGINE PhysFalling        3610/4096   LIT
                       0x055C2430 ULokiCMC::StartNewPhysics 3626/4096   LIT
```

---

## HEADLINE

**[M] The dismount contains NO velocity write of any kind. It restored `GravityScale` — and
`GravityScale` was `0.0` only because OUR OWN STAGING SHIM (`sp`) sets it to zero on every
sitting.** The S132 free fall is pure gravity, switched back on by
`0x55CCDC9  mov dword [r14+0x1a0], 0x3f800000`, where **`CMC+0x1A0` is
`UCharacterMovementComponent::GravityScale`**.

**[M] And the S140 "fixed point" gate does NOT zero `Velocity.Z`.** The zeroing store at
`0x035ED9AC` is a **16-byte `movups`** — it zeroes gravity-space X and Y only; gravity-space Z at
`[rbp+0x178]` is never written and is round-tripped back into `Velocity.Z`. This settles the open
`[I]` in CLAUDE.md ("whether `Velocity.Z` is zeroed too … it would explain the no-fall phenomenon")
**in the negative: it does not, so it does not explain it.**

---

## Q1 — THE FUNCTION, FROM THE BYTES

### 1.1 Extent [M]
`ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable` = **`0x55CCCB0 .. 0x55CCE67`
inclusive of the `ret`**, i.e. `0x1B8` = **440 bytes**, matching the S132 record exactly. Read to
the `ret`: `0x55CCE67 c3`. The next function (`AuthPlayerEnterWorld`, `0x55CCE70`) begins after
8 bytes of padding/ICF debris. Confirmed by reading to the `ret`, not only from pdata.

### 1.2 Call inventory [M]
**16 call instructions = 15 direct + 1 indirect. 14 distinct direct targets: 13 REAL, 1 FOLD, 0 DARK.**

| site | target | grade | identity |
|---|---|---|---|
| `0x55CCD32` | `0x56BE0D0` | REAL (pg 3764) | `PS->GetLokiCharacter()` — `push rbx; sub rsp,0x20; mov rbx,[rcx+0x430]` |
| `0x55CCD46` | `0x54F8DC0` | REAL (pg 3960) | `IsChildOfUsingStructArray` -> GATE 6 `IsA(ALokiHeroCharacter)` |
| `0x55CCD5B` | `0x0F7EC20` | **FOLD** | `c2 00 00` = `ret imm16 0`, **VOID no-op** (does NOT zero eax); return never tested |
| `0x55CCD75` | `0x1138DD0` | REAL (pg 3860) | `FName` ctor (`r8d=1`), literal at `rip+0x354E883` |
| `0x55CCD89` | `0x10FF910` | REAL (pg 3886) | array op on `hero+0x1F0` (`AActor::Tags`) — adds `MinionIgnore` |
| `0x55CCD93` | `0x339A550` | REAL (pg 3708) | `SetActorEnableCollision(dl=1)` — **CONFIRMS S132** |
| `0x55CCD9D` | `0x5599040` | REAL (pg 3726) | `SetPredropHidden(edx=0)`; prologue is literally `cmp byte [rcx+0x1be8], dl` — **CONFIRMS the `hero+0x1BE8` byte** |
| `0x55CCDA5` | `0x5586530` | REAL (pg 3906) | unnamed; see §1.4 |
| `0x55CCDAD` | `0x55AC8E0` | REAL (pg 3729) | `GetLokiCharacterMovement()` — `mov rbx,[rcx+0x458]` — CONFIRMED |
| `0x55CCDC2` | **indirect** `[vtbl+0x3E0]` -> `0x35BC510` | REAL | **`UActorComponent::SetComponentTickEnabled(true)`** — see §1.3 |
| `0x55CCDE2` | `0x55D89F0` | REAL (pg 3732) | `GetLandingTeleportLocation(&out, hero, LandingActor)` — CONFIRMED |
| `0x55CCDFA` | `0x339A7A0` | REAL (pg 3708) | `SetActorLocation(&out, bSweep=0, Hit=0, Teleport=0)`; `mov rcx,[rcx+0x1b0]` = RootComponent |
| `0x55CCE05` | `0x54537C0` | REAL (pg 3906) | `MulticastOnPlayerEnteredWorld(PS)` |
| `0x55CCE0D` | `0x55C6E80` | REAL (pg 3938) | returns object; `if (o) o->[0xD0] = 1` |
| `0x55CCE32` | `0x11F3860` | REAL (pg 3854) | `TArray::Remove` on `comp+0x130` — CONFIRMED |
| `0x55CCE4E` | `0x0F7EC20` | **FOLD** | VOID no-op, `(PS, dl=3, r8d=0)` |

=> **Every item in the S132 record is CONFIRMED. Nothing is REFUTED.** The two folds are exactly
where S132 said (`0x55CCD5B`, `0x55CCE4E`) and neither return is tested, so neither gates anything.

### 1.3 [M] The virtual at CMC vtable disp `0x3E0` is `UActorComponent::SetComponentTickEnabled(bool)`
`ULokiCMC` vtable `.rdata 0x088F8570` disp `0x3E0` (slot 124) = `0x35BC510`, **identical to the
engine `UCharacterMovementComponent` vtable (`0x07FBED58`) at the same disp — NOT Loki-overridden.**
Comparator control: slots 119 and 122 in the same 0x3A0..0x428 window DO differ between the two
vtables (`0x3D0`/slot 122 = `TickComponent`, loki `0x55C2B90` vs engine `0x3603780`), so the
comparison can distinguish — a "SAME" reading is informative, not a degenerate one.

```
035bc510  test byte [rcx+0x4a], 2      ; PrimaryComponentTick(+0x40) + flags(+0x0A), mask 0x02 = bCanEverTick
035bc51e  movzx edi, dl                ; the bool arg
035bc524  je   skip
035bc526  mov  edx, 0x30
035bc52b  call 0x1368b60               ; IsTemplate(RF_ClassDefaultObject|RF_ArchetypeObject)
035bc532  jne  skip
035bc534  lea  rcx, [rbx + 0x40]       ; &PrimaryComponentTick
035bc53c  call 0x3ef73b0               ; FTickFunction::SetTickFunctionEnable(bool)
```
Four independent structural confirmations, none of which is a name guess:
1. `+0x4A` = `UActorComponent+0x40` (`PrimaryComponentTick`, [M] S139) + `FTickFunction+0x0A`
   (flags, [M] S139), mask `0x02` = **`bCanEverTick`**.
2. `0x1368B60` reads `ObjectFlags@+0xC` and walks `Outer@+0x28` — that is
   `UObjectBaseUtility::IsTemplate`; `edx = 0x30` = `RF_ClassDefaultObject(0x10)|RF_ArchetypeObject(0x20)`,
   the stock default argument.
3. `0x3EF73B0` operates on `[rcx+0x20]` (`FTickFunction::InternalData`, [M] S139), reads and writes
   `[rdi+0x0B]` (`TickState`, [M] S139), and on the disabled branch writes
   `[InternalData+0x24] = 0xBF800000 = -1.0f` — i.e. **`LastTickGameTimeSeconds = -1.0`**, the exact
   value S139 measured on both pawns.
4. `SetComponentTickEnabled(bool bEnabled)` is `UActorComponent` reflected method index **21**
   (`tools/asdump/out/binds_members.csv:21310`), so the name exists on this class.

This is a byte-exact match for stock UE's
`if (PrimaryComponentTick.bCanEverTick && !IsTemplate()) PrimaryComponentTick.SetTickFunctionEnable(bEnabled);`

=> **the dismount does `mv->SetComponentTickEnabled(true)`. It does NOT seed velocity.**

### 1.4 `0x5586530` is not a velocity writer, and its `+0xE8` is a decoy [M]
```
05586534  mov rax,[rcx+0x460]
05586541  movups xmm2,[rax+0x240] ; unpckhpd/minsd -> min of a double pair
05586557  mulss  xmm0,[rax+0x6c4]
0558655f  mov rax,[rcx+0x1978]
05586566  addss  xmm0,[rcx+0x196c]
0558656e  movss  [rax+0xe8], xmm0     <-- 4-byte float, on the object at hero+0x1978
05586576  mov rcx,[rcx+0x1980]
05586583  mov  dword [rcx+0xe8], eax  <-- 4-byte int,   on the object at hero+0x1980
0558658f  jmp  qword [rax+0xc68]
```
**WARNING: `+0xE8` here is NOT `CMC+0xE8` Velocity.** The CMC is `hero+0x458`; these two objects are
`hero+0x1978` and `hero+0x1980`, different pointers. Velocity is three **doubles** (24 B); these are
4-byte stores. **Not a velocity write.** (CLAUDE.md's recorded crash hazard for this function —
unchecked `hero+0x460 / +0x1978 / +0x1980` — is confirmed: no null test on any of the three.)

### 1.5 [M] EXHAUSTIVE WRITE SCAN — the decisive negative
Classified from `operands[0].type == MEM` (**never** `regs_access`, per trap S140T2 — capstone
5.0.7 reports `movups` stores as reads).

The whole 440-byte function contains **9 memory-operand-destination instructions**: 6 stack
(5 register spills + `mov byte [rsp+0x20],0`, an outgoing stack argument), 1 misclassified indirect
`call [r8+0x3e0]` (a vtable READ, not a write), and **exactly TWO direct object writes**:

```
055ccdc9  mov dword ptr [r14 + 0x1a0], 0x3f800000    ; CMC+0x1A0 = 1.0f
055cce1c  mov byte  ptr [rax + 0xd0],  1             ; on the object returned by 0x55C6E80(PS)
```

=> **ZERO writes to `CMC+0xE8/0xF0/0xF8` (Velocity), ZERO to `CMC+0x231` (MovementMode), ZERO to
`CMC+0x328` (Acceleration).** Hypothesis (a) is refuted exhaustively, not by sampling.
Scope caveat: this is *direct* writes only. Callees write more (the `Tags` array, `hero+0x1BE8`,
collision state, the actor transform) — but none of those objects is the CMC.

---

## Q2 — WHAT PUT A VELOCITY INTO THE PAWN? **ANSWER: (d), and nothing else did.**

### 2.1 [M] `CMC+0x1A0` is `GravityScale` — read from its own consumer
Engine `UCharacterMovementComponent::GetGravityZ` (engine CMC vtable disp `0x4C0` = `0x35E3650`):
```
035e3678  mov  rcx, rbx
035e367b  call 0x3632e20                      ; Super::GetGravityZ()  (UMovementComponent)
035e3680  mulss xmm0, dword ptr [rbx + 0x1a0] ; <-- * GravityScale
035e368d  ret
```
That is stock UE's `return Super::GetGravityZ() * GravityScale;` verbatim.
Second, independent instrument: `binds_members.csv` gives `UCharacterMovementComponent` **property
index 0 = `float32 GravityScale`**. Third: the shim resolves the offset BY NAME at runtime and
prints `GravityScale@0x1A0` in every staged marker. **Three agreeing instruments; grade [M].**

The Loki override `ULokiCMC::GetGravityZ 0x055AB8C0` calls the engine one and only zeroes the result
for `MovementMode(+0x231)==7 (MOVE_Custom)` with specific `CustomMovementMode(+0x232)` values.
**For `MOVE_Falling(3)` it is a pass-through** => `GetGravityZ() = Super * GravityScale`.

### 2.2 [M] THE PRE-STATE WAS `GravityScale = 0`, AND WE SET IT
`tools/sigbypass-mod/tutorial_launch.cpp:12877-12890`, the `sp` stager's **LIFT-TO-SEE** block:
```cpp
// LIFT-TO-SEE: ... Kill the hero's gravity + teleport it WAY up so the camera rises above the terrain
*(float*)(cmc+gsOff) = 0.0f;   Markerf("[LIFT] gravity OFF (CMC=0x%llX GravityScale@0x%X)\r\n", ...);
... NL[2] = HL[2] + 1800.0;    // lift 1800 up, teleport, no sweep
```
**That block changes exactly TWO things: `GravityScale = 0.0f` and an actor teleport. It does not
touch MovementMode, Velocity, the tick function, or anything else.**

`[LIFT] gravity OFF` is present at **line 24 of every staged `sp` marker in the repo** — s112c-ctl-18,
s112c-trt-08, s112p2-foSTD-05, wp2r2, s137, s138-f2/f3/f4/f6/f7. And it is measured live:

| source | object | GravityScale @+0x1A0 |
|---|---|---|
| `docs/s138-f9-mm-BASELINE.txt:16` | PLAYER hero (sp-staged, Z=13240) | **0.000** |
| `docs/s138-f9-mm-COMPARISON.txt:16` | BOT (SpawnAIFromClass) | 1.000 |
| `docs/s138-f9-mm-COMPARISON.txt:28` | PLAYER hero | **0.000** |
| `docs/s138-f9-mm-COMPARISON.txt:40` | other hero #1 | 1.000 |

### 2.3 The chain, end to end [M, strong]
```
sp stages hero  ->  GravityScale = 0  ->  ULokiCMC::GetGravityZ() = Super * 0 = 0
                ->  gravity contributes nothing in PhysFalling  ->  Velocity.Z stays 0 forever
                ->  hero hangs motionless at (0, 0, 13240)                       [S132's "before"]

detach 0x55CCDC9 writes GravityScale = 1.0f
                ->  GetGravityZ() != 0  ->  NewFallVelocity accumulates -Z each frame
                ->  X,Y frozen (nothing ever gave them a horizontal component)
                ->  Z accelerating                                                [S132's "after"]
```
S132 measured `Z = -117,462.8 -> -121,560.9` over 4.0 s with **X and Y frozen and identical**.
That is *pure gravity* and nothing else in the function can produce it.

### 2.4 The rival hypotheses, each closed
- **(a) something wrote Velocity — REFUTED [M].** Exhaustive write scan, §1.5: two object writes,
  neither to the CMC's velocity / mode / acceleration fields.
- **(b) the teleport seeded velocity — REFUTED [M], by the measurement itself.** The call passes
  `bSweep = 0` and `ETeleportType::None` (`[rsp+0x20] = 0`), and a depth-1 write scan of `0x339A7A0`
  shows only stack traffic plus an `FHitResult`-shaped 0x70-byte init at `[rbx+0x00..0x60]` — no
  write at disp `0xE8/0xF0/0xF8/0x231/0x1A0/0x328`. I did **not** exhaust the deep `MoveComponent`
  chain, so that half alone would be [I]. **But the observation closes it outright:** the teleport
  displaced the hero by ~1.45 **million** uu in +X. Any displacement-derived velocity would be
  overwhelmingly +X — and S132 measured **X frozen**. A teleport-seeded velocity is inconsistent
  with the data.
- **(c) `vt[+0x3E0](true)` — IDENTIFIED, and it does not seed velocity [M].**
  `UActorComponent::SetComponentTickEnabled(bool)` (§1.3). Its only effect is
  `PrimaryComponentTick.TickState`. It is a genuine *enabler* (a disabled tick cannot simulate), but
  it writes no motion state. Whether it was a **necessary** condition here is NOT ESTABLISHED — §2.5.
- **(d) `[mv+0x1A0] = 1.0f` — CONFIRMED [M, strong]: it is `GravityScale`, and the pre-state was 0.**
- **(e) different starting state — this IS (d).** The "different starting state" is real and it is
  ours: `GravityScale = 0`, applied by our own stager.

### 2.5 NOT ESTABLISHED — the honest residual
The S132 hero's **pre-dismount `PrimaryComponentTick.TickState` was never read**, so I cannot rule
out that `SetComponentTickEnabled(true)` was *also* necessary. Two facts bound it:
- The `sp` LIFT block does not disable any tick, so nothing in our staging is known to have
  disabled it.
- S139 measured `TickState = Enabled` on both bot and player CMCs, which makes the call a likely
  no-op — but that is a *different* sitting and a different hero.

**The read that settles it:** on a staged client, before injecting anything, read
`CMC+0x40+0x0B` (`PrimaryComponentTick.TickState`, 0=Disabled 1=Enabled) and
`CMC+0x40+0x20` (`InternalData`; NULL => never registered) on the sp-staged hero.
`scratchpad/s139/ticksniff.py` already decodes exactly this.

---

## Q3 — REACHABLE WITHOUT A DROP POD? **YES. BOTH. AND ONE IS ALREADY IMPLEMENTED.**

The detach as a whole is gated on `PlayersAttached` (`comp+0x130` Data / `+0x138` Num / `+0x13C` Max)
being non-empty and containing the PlayerState — which S132 had to build by hand. **Neither of the
two payload actions needs any of that.**

| action | route without a pod | risk class |
|---|---|---|
| **(d) `GravityScale = 1.0f`** | one aligned 4-byte float store at `CMC+0x1A0`, offset resolvable **by name** (`PropOffsetSuper(ClassOf(cmc),"GravityScale")`) | **ONE ALIGNED DATA WRITE on a live instance** — this project's safest measured class (nothing 0/22). Readback-verifiable. **NOT a CDO poke, NOT a `.text` write.** |
| **(c) `SetComponentTickEnabled(true)`** | call CMC vtable slot 124 (disp `0x3E0`) directly: `void __fastcall(UActorComponent*, bool)`. Also reflected (`UActorComponent` method 21), so the S55 direct-thunk route works too. | **CALL-ONLY** — we write nothing; the callee writes only `PrimaryComponentTick.TickState` (plus `LastTickGameTimeSeconds` on the disable path). |

**The code for (d) already exists in this repo, twice.**
`tutorial_launch.cpp:2998` writes `GravityScale = 1.0f` (the `WM` path, marker
`[WM] GravityScale=1.0 set`), and `:12882` writes `0.0f` (the `sp` LIFT). **The cheapest possible
experiment is to stop zeroing it, or to re-write `1.0f` after staging** — a one-line, single-variable,
readback-verified change with a `[LIFT]`-style marker already in place.

Consequence to expect, not a defect: with gravity restored the sp-staged hero at Z ~ 13,240 will
**fall ~13 km**. On the tutorial island that ends in a landing (S140 flight 3 landed a bot at
`Z = 90.150`); off the island it ends in an unbounded fall (S132 flight 1). If the LIFT's camera
purpose still matters, restore gravity *after* the camera is settled rather than never.

---

## Q4 — WHAT DOES `[mv+0x1A0]` READ ON A HERO TODAY? **ESTABLISHED — 0.000 on the player.**

Not "not established" — the repo already measured it, on **2026-08-23**, with a read-only RPM probe
(`tools/re/movementmode_readout.py`) that resolves the offset **by name**:

```
docs/s138-f9-mm-BASELINE.txt:16     PLAYER hero  GravityScale = 0.000   [by name @+0x1A0]
docs/s138-f9-mm-COMPARISON.txt:16   BOT          GravityScale = 1.000   [by name @+0x1A0]
docs/s138-f9-mm-COMPARISON.txt:28   PLAYER hero  GravityScale = 0.000   [by name @+0x1A0]
docs/s138-f9-mm-COMPARISON.txt:40   other hero#1 GravityScale = 1.000   [by name @+0x1A0]
```
Both files carry the same PID (46044) and base, one minute apart — a within-run, same-instrument,
two-sided reading, with the by-name resolution as its own control.

### THIS CORRECTS A RECORDED CLAIM
CLAUDE.md and `docs/s139-flight1-the-bot-is-not-special.md` state that bot and player
*"read IDENTICALLY on EVERY structural field"* and list ~19 fields
(`UpdatedComponent, Mobility, Role, RemoteRole, Controller, RF_Garbage, MovementMode,
MaxAcceleration, bCharacterMovementEnabled, Acceleration, AnalogInputModifier, +0x16C8,
bCanEverTick, TickState, Prerequisites.Num, InternalData, bRegistered, bIsActive,
AttributeSetStorage`). **`GravityScale` is not among them** — and it is the one field that governs
falling. `grep GravityScale docs/s139-flight1-the-bot-is-not-special.md` returns 2 hits, both
referring to the bot's 1.000, none to the player's 0.000 measured the day before.

=> **The bot and the player are NOT identical: `GravityScale` is 1.000 vs 0.000.** The correct
statement is *"identical on every structural field that was read"*.

### AND IT CLOSES A RECORDED PHENOMENON
The S141 handoff records that the untreated **player**, given an injected 600 uu/s, *"moved only 795
uu and never fell."* The "never fell" half needs no explanation beyond this: **the player's
`GravityScale` is 0**, set by our own `sp` stager. That half of the observation is self-inflicted,
not a game property.
Scope it precisely: this explains the **player's** non-fall. It does **not** explain the **bot's**
non-fall — the bot reads `GravityScale = 1.000`. Those are two different phenomena and merging them
would repeat this project's recorded error of pooling distinct mechanisms under one label.

---

## FREE BY-PRODUCTS (offline, this lane, all verified)

### A. [M] The S140 gate does NOT zero `Velocity.Z` — CLAUDE.md's open `[I]` is SETTLED, negatively
```
035ed961  mov r8, rsi                     ; IN  = &Velocity
035ed964  lea rdx, [rbp+0x168]            ; OUT = gravity-space buffer
035ed96e  call 0x35f4770                  ; world -> gravity space
035ed973  movups xmm0,[rbp+0x168] / movsd xmm1,[rbp+0x170] / mulsd / mulsd / addsd   ; SizeSq2D = X^2+Y^2
035ed98e  comisd xmm1, [.rdata 0x077F5180]
035ed996  ja  0x35ed9c8                   ; above gate -> skip
035ed998  xorps xmm0, xmm0
035ed9ac  movups [rbp+0x168], xmm0        ; *** 16 BYTES *** -> zeroes GS.X and GS.Y ONLY
035ed9b3  call 0x35f4620                  ; gravity -> world, IN=[rbp+0x168], OUT=[rbp+0x638] (ret in rax)
035ed9b8  movups xmm0,[rax]      / movups [rsi], xmm0        ; Velocity.X, Velocity.Y
035ed9be  movsd  xmm1,[rax+0x10] / movsd  [rsi+0x10], xmm1   ; Velocity.Z
```
**The only store into `[rbp+0x168..]` between the two rotations is the single 16-byte `movups` at
`0x035ED9AC`.** Gravity-space Z at `[rbp+0x178]` is never written, so `xmm1` at `0x035ED9C3` is the
**preserved** vertical component rotated back to world.
=> **The fixed point at `0x035ED98E` is a HORIZONTAL-ONLY damper.** Vertical escape is entirely
unprotected by it. CLAUDE.md's hope that this "would explain the no-fall phenomenon" is **refuted**.
=> The bot's non-fall must come from gravity never being **added** to `Vz`, not from `Vz` being zeroed.

### B. [M] The gate constant identity — the seed's correction is confirmed
`.rdata 0x077F5180` bytes `000000cc4d62503f` = `0.00099999997473787516`
= `(double)(float)1e-4 * 10.0` = `UE_KINDA_SMALL_NUMBER(float) * 10`.
It is **NOT** `(double)(float)1e-3` = `0.0010000000474974513`.
Escape threshold `|V_xy|` (gravity space) = `0.0316227762`.
=> `docs/s140-t2-armj-THE-BOT-WALKS.md`'s stated identity is wrong and should be corrected.

### C. [M] `ULokiCMC::NewFallVelocity 0x055B6AD0` is a pass-through for `MOVE_Falling`
Calls engine `0x35E8B00` unconditionally first, then clamps the result's Z **only** when
`MovementMode(+0x231)==7 && CustomMovementMode(+0x232)==1`. For `MOVE_Falling(3)` it returns the
engine value untouched. => **the Loki override is NOT the bot's blocker.** A clean elimination.

### D. NEW SUCCESSOR LEAD — a second, un-recorded gravity kill switch, two reads away
Engine `UCharacterMovementComponent::GetGravityZ 0x035E3650`:
```
035e3656  mov  rax,[rcx]
035e365c  call qword ptr [rax + 0xce0]     ; some bool query
035e3662  test al,al / je  0x35e3678
035e3666  cmp  byte ptr [rbx + 0x1001], 0
035e366d  jne  0x35e3678
035e366f  xorps xmm0, xmm0 / ret           ; *** RETURNS 0.0f ***
```
=> **`[vt+0xCE0]() == true && byte[CMC+0x1001] == 0`  =>  `GetGravityZ() == 0`**, independently of
`GravityScale`. Nothing in this repo has read `CMC+0x1001` or graded vtable disp `0xCE0`.
**On the bot (`GravityScale = 1.000`, `MOVE_Falling`, does not fall) this is the single best
candidate**, and settling it costs one read-only RPM byte plus one offline vtable lookup.
Grade the *naming* [S] — I have not identified `+0x1001` or disp `0xCE0`. The *structure* is [M].

### E. [M] Small confirmations banked
- `UActorComponent+0x40 = PrimaryComponentTick` re-confirmed from a second, independent site.
- `FTickFunction`: `TickState@+0x0B`, `InternalData@+0x20`, `InternalData+0x24 = LastTickGameTimeSeconds`
  (written `-1.0f` on disable) — re-confirmed from `0x3EF73B0`.
- `UObjectBaseUtility::IsTemplate` = `0x1368B60`; `ObjectFlags@+0xC`, `Outer@+0x28`.
- `hero+0x1BE8` (predrop-hidden byte) confirmed *inside* `SetPredropHidden`'s own prologue.
- `AActor::RootComponent@+0x1B0` confirmed inside `SetActorLocation`'s prologue.
- `ULokiCMC` vtable disp `0x3D0` (slot 122) = `TickComponent` `0x55C2B90`, engine `0x3603780`.

---

## RANKED HANDOFF

1. **Stop zeroing `GravityScale`** (or restore `1.0f` after staging). One line, already-written code
   at `tutorial_launch.cpp:2998`, one aligned data write, readback-verified, marker already exists.
   It removes a confound present in **every** staged sitting since ~S75.
2. **Read `byte[CMC+0x1001]` and grade CMC vtable disp `0xCE0`** — lead D. The bot's non-fall.
3. **Read `PrimaryComponentTick.TickState` / `InternalData` on the sp-staged hero** before injecting
   (§2.5), to close whether `SetComponentTickEnabled(true)` was necessary.
4. Correct `docs/s140-t2-armj-THE-BOT-WALKS.md`'s gate-constant identity (by-product B).
5. Correct the S139 "identical on EVERY structural field" claim to "every structural field read",
   and add `GravityScale` to that readout table.
