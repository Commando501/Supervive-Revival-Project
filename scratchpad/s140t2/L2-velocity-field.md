# S140 TIER 2 — LANE 2: WHAT EXACTLY IS `CMC+0xE8`, AND IS THE SENTINEL SAFE?

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset (verified below).
All work done with lane-local instruments written from scratch for this lane
(`scratchpad/s140t2/pe.py`, `uht.py`, `walk.py`, `xdis.py`, `census.py`), importing none of
`scratchpad/s140/tools/*` or `tools/cfg.py`.

**Provenance of every read:** all bytes quoted below come from `.text` or `.rdata` of
`merged13.dump.exe` **except** four, which come from `.data` and are flagged inline:
the UHT `FStructParams` at `.data 0x099D14E8`, the `{name,thunk,impl}` triples at
`.data 0x09A7*/0x09BC*`, `FVector::ZeroVector` at `.data 0x099C86A0`, and the
`Z_Registration_Info` singleton at `.data 0x09DFD068`. `merged13` is a **`.text`-only** merge,
so its `.data` is a single-seed coherent snapshot — but these are *constant-initialised*
UHT tables, not mutable runtime state, and each is corroborated by `.text` disassembly.

> **`.text` is 55.48 % decrypted in `merged13`. Every census below is a FLOOR, never a count.**
> A call or a consumer sitting on a dark page is invisible to a rel32 scan (the bytes are zero),
> so "N sites" always means "at least N sites".

---

## HEADLINE

1. **[M] `CMC+0xE8` is `UMovementComponent::Velocity`, an `FVector` of THREE DOUBLES —
   `X@0xE8, Y@0xF0, Z@0xF8`, 24 bytes.** Four independent instruments, eight passing controls.
   CLAUDE.md's *"`Velocity` is `CMC+0xE8`, not the `+0xE0` one probe hardcoded"* is **CONFIRMED**.
2. **[M] `CMC+0x1A0` is `UCharacterMovementComponent::GravityScale` (float), NOT
   `ComponentVelocity`.** The brief's premise is a class mix-up: `ComponentVelocity` is `+0x1A0`
   **on `USceneComponent`**. Same number, different class — exactly CLAUDE.md's recorded
   "never sample a byte offset across unrelated vtables" trap.
3. **[M] Yes, something copies CMC `Velocity` out to the scene component every frame.**
   `UMovementComponent::UpdateComponentVelocity` = **vt disp `0x518` = `0x036523F0`** (not
   overridden by Loki), called **unconditionally** at `0x035D67B3` inside `0x035D6790`, which is
   the callee of vt disp `0xA50` — i.e. **the same tail call that clears the `+0x16C8` flag.**
4. ⚠⚠ **THE BRIEF'S SENTINEL `0.0009765625` (2^-10) IS NOT INERT. It trips a
   `Velocity.SizeSquared2D() >= 1e-8` gate inside `ULokiCMC::PerformMovement` — a function S139
   MEASURED to run every frame — by a factor of 95, and causes a write to the reflected
   UPROPERTY `ULokiCMC::LastNonZeroDirection2D @ CMC+0x12F0`.** It also sits within 2.3 % of a
   `1e-3` threshold and 4.6 % of a `1e-6` threshold. **Recommend ~2^-31 with a magic mantissa
   instead** (§5) — 1.5e10× below the nearest tolerance, still 96 bits of tag.
5. ⚠⚠ **THE TIER-1 DECISION RULE IS DEFECTIVE.** *"`+0xE8` no longer holds the sentinel ⇒ the
   probe's own control failed; the run is void"* is wrong: engine `PhysFalling` at
   **`0x035ED98E`** zeroes horizontal velocity when `SizeSquared2D <= 1e-3`, and the brief's
   sentinel is 1048× *below* that bar — so **"SNP ran" predicts the sentinel is erased from
   `+0xE8`**, and the rule declares the successful case VOID. Corrected table in §3.6.
6. ★★ **A STRICTLY BETTER ARM: pre-poke the snapshot `+0x16B0` with a *second, different* tag.**
   [M] the poked snapshot is **unreadable by any consumer** (proof in §4.3), and the second tag
   converts a two-state test into a three-state one that can detect an unknown writer. §5.3.

---

## 0. Controls run before any analysis (my own code)

| control | result |
|---|---|
| PE flat (all 10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase from optional header | **`0x7FF608F40000`** (agrees with Tier 1) |
| known-DARK control `0x05A6AC40` page non-zero bytes | **0 / 4096** PASS |
| every function disassembled below, page non-zero | 3454–3883 / 4096 PASS |
| capstone write-classification rule (`operands[0].type == MEM`) validated on a known store | PASS, §1.2 (ii) |

---

## 1. `CMC+0xE8` IS `UMovementComponent::Velocity`, THREE DOUBLES

### 1.1 Instrument A — the UHT `FPropertyParams` / `PropPointers` table (`.rdata`)

Search the image for the exact NUL-terminated literal `Velocity`, find every 8-aligned qword
pointer to it, decode the record. **Exactly one record in the whole image carries `Offset 0xE8`:**

```
rec .rdata 0x07FC7A90   name="Velocity"  ArrayDim=1  Offset=0x00E8
                        EPropertyGenFlags = 0x19 (Struct)
                        PropertyFlags = 0x0010000000000005
                        ScriptStructFunc = VA 0x7FF60A0E5E70 -> rva 0x011A5E70
```

Following the single 8-aligned pointer to that record lands inside a `PropPointers[]` array,
and walking the array gives **the complete property set of one class**:

```
.rdata 0x07FC7E50  [ 0] UpdatedComponent                    off=0x000D0  gen=Object|ObjectPtr
                   [ 1] UpdatedPrimitive                    off=0x000D8  gen=Object|ObjectPtr
                   [ 2] Velocity                            off=0x000E8  gen=Struct
                   [ 3] PlaneConstraintNormal               off=0x00100  gen=Struct
                   [ 4] PlaneConstraintOrigin               off=0x00118  gen=Struct
                   [ 5] bUpdateOnlyIfRendered                             gen=Bool
                   [ 6] bAutoUpdateTickRegistration                       gen=Bool
                   [ 7] bTickBeforeOwner                                  gen=Bool
                   [ 8] bAutoRegisterUpdatedComponent                     gen=Bool
                   [ 9] bConstrainToPlane                                 gen=Bool
                   [10] bSnapToPlaneAtStart                               gen=Bool
                   [11] bAutoRegisterPhysicsVolumeUpdates                 gen=Bool
                   [12] bComponentShouldUpdatePhysicsVolume               gen=Bool
                   [13] UnderlyingType                                    gen=Byte
                   [14] PlaneConstraintAxisSetting          off=0x00133  gen=Enum
```

That is **exactly stock `UMovementComponent`'s declared property set, in declaration order**.
⇒ **[M] `Velocity` is declared on `UMovementComponent`, not on `UCharacterMovementComponent`**,
which agrees with the independent declaration table
`tools/asdump/out/binds_members.csv:26201`:
`class,1427,UMovementComponent,/Script/Engine.MovementComponent,property,2,FVector Velocity`.

**Size, from the neighbours, two ways:**
`PlaneConstraintNormal(0x100) − Velocity(0xE8) = 0x18 = 24` and
`PlaneConstraintOrigin(0x118) − PlaneConstraintNormal(0x100) = 0x18 = 24`.
All three are the *same* struct type (identical `ScriptStructFunc`), so this is a
self-consistent 24-byte stride across a three-element run. **⇒ FVector is 24 B.**

**The struct is named and its members are typed [M].** `ScriptStructFunc 0x011A5E70` is the
standard UHT singleton:
```
0x011A5E80  lea rdx,[rip -> .data 0x099D14E8]   ; FStructParams
0x011A5E87  lea rcx,[rip -> .data 0x09DFD068]   ; Z_Registration_Info singleton
0x011A5E8E  call 0x0135FA90                     ; ConstructUScriptStruct
```
`FStructParams @ .data 0x099D14E8` → `NameUTF8 -> "Vector"`, `PropertyArray -> .rdata 0x076E8058`:
```
[0] X  off=0x00  gen=0x20 LargeWorldCoordinatesReal
[1] Y  off=0x08  gen=0x20 LargeWorldCoordinatesReal
[2] Z  off=0x10  gen=0x20 LargeWorldCoordinatesReal
```
**Stride 8 with three members ⇒ each is 8 bytes ⇒ `double`.** (`LargeWorldCoordinatesReal` is
UE5's LWC `FVector::FReal`; the *offsets* settle the width without needing to trust the name.)
The word at `FStructParams+0x2A` reads `0x0018` and `+0x2C` reads `8`, consistent with
`SizeOf 24 / Alignment 8` — ⚠ graded **[I]**, since I did not calibrate that struct's exact
field layout against a second known struct.

### 1.2 Instrument B — disassembly of three unrelated functions

Every one of these is a *different translation unit* from the UHT tables and from each other.

**(i) `UMovementComponent::UpdateComponentVelocity`, vt disp `0x518` = `0x036523F0`:**
```
0x036523F0  48 8b 81 d0 00 00 00        mov    rax,[rcx+0xD0]        ; UpdatedComponent
0x036523F7  48 85 c0 / 74 1e            test/je                       ; null guard
0x036523FC  0f 10 89 e8 00 00 00        movups xmm1,[rcx+0xE8]        ; Velocity.X , Velocity.Y   (16 B)
0x03652403  f2 0f 10 81 f8 00 00 00     movsd  xmm0,[rcx+0xF8]        ; Velocity.Z                (8 B)
0x0365240B  0f 11 88 a0 01 00 00        movups [rax+0x1A0],xmm1       ; ComponentVelocity.X , .Y
0x03652412  f2 0f 11 80 b0 01 00 00     movsd  [rax+0x1B0],xmm0       ; ComponentVelocity.Z
0x0365241A  c3                          ret
```
**16 + 8 = 24 bytes, `movsd` (scalar *double*) for the third component.** A 3×`float` FVector
would be copied `movsd`(8) + `movss`(4), or as one 12-byte access. This is the UE5 LWC idiom and
nothing else. The destination side (`+0x1A0` / `+0x1B0`, delta `0x10`) independently reproduces
the same 24-byte layout on `USceneComponent::ComponentVelocity`.

**(ii) `UMovementComponent::StopMovementImmediately`, vt disp `0x4D8` = `0x032C9DD0`** — the
write control:
```
0x032C9DD6  movups xmm0,[rip -> .data 0x099C86A0]   ; FVector::ZeroVector  (measured: 24 zero bytes)
0x032C9DE3  movups [rcx+0xE8],xmm0                  ; *** WRITE 16 B ***
0x032C9DEA  movsd  xmm0,[rip -> .data 0x099C86B0]
0x032C9DF2  movsd  [rcx+0xF8],xmm0                  ; *** WRITE 8 B ***
0x032C9DFA  call   [rax+0x518]                      ; UpdateComponentVelocity()
```
This is stock `StopMovementImmediately() { Velocity = FVector::ZeroVector; UpdateComponentVelocity(); }`
byte for byte. It also **validates the capstone write rule** the brief mandates: capstone reports
`movups [rcx+0xe8],xmm0` with `operands[0].type == MEM` (write), while `regs_access` would call
it a read. Rule PASSES on a known store.

**(iii) `APawn::GetVelocity` = pawn-family vtable `.rdata 0x088E5CA8 + 0x380` = `0x03BA9300`:**
```
0x03BA9310  mov  rcx,[rcx+0x1B0]        ; AActor::RootComponent
0x03BA9317  test/je -> fallback
0x03BA9326  call [rax+0x4C0]            ; IsSimulatingPhysics(edx=0)
0x03BA932E  je   -> fallback
0x03BA933D  call [rax+0x520]            ; RootComponent->GetComponentVelocity()
fallback:
0x03BA9357  call [rax+0x7B8]            ; GetMovementComponent()
0x03BA935D  test rax,rax / je
0x03BA9362  add  rax,0xE8               ; *** &MovementComponent->Velocity ***
```
`add rax, 0xE8` on a movement component, from a third TU. **[M]**
`AActor::GetVelocity` is vt disp `0x380` (resolved from the exec thunk `0x033A9350`, which does
`call [rax+0x380]` then copies the 16+8 out-param — **a fourth 24-byte confirmation**).

### 1.3 Passing positive controls (eight, all independent of the claim)

| control | source | expected (independently recorded) | measured here |
|---|---|---|---|
| `UMovementComponent::UpdatedComponent` | UHT array above | `0xD0` (S139 probe field list) | **0xD0** PASS |
| `UCharacterMovementComponent::CharacterOwner` | UHT | `0x198` (Tier 1 §4.6 disasm `mov r15,[rcx+0x198]`) | **0x198** PASS |
| `UCharacterMovementComponent::MovementMode` | UHT | `0x231` (CLAUDE.md `IsDashing 0x035E6810 = cmp byte [rcx+0x231],6`) | **0x231** PASS |
| `UCharacterMovementComponent::Acceleration` | UHT | `0x328` (CLAUDE.md S139) | **0x328** PASS |
| `UCharacterMovementComponent::MaxAcceleration` | UHT | `0x28C` (S139 probe list) | **0x28C** PASS |
| `UCharacterMovementComponent::LastUpdateVelocity` | disasm `execGetLastUpdateVelocity 0x03607470`: `movups xmm1,[rcx+0x378]` + `movsd xmm0,[rcx+0x388]` → out-param `[r8]`/`[r8+0x10]` | `0x378` (Tier 1 §2) | **0x378, and 16+8 out-param ⇒ FVector = 24 B again** PASS |
| `USceneComponent::RelativeLocation` | UHT | `0x158` (CLAUDE.md S131) | **0x158** PASS |
| `USceneComponent::Mobility` | UHT | `0x1BB` (S139 probe list) | **0x1BB** PASS |
| `AActor::RootComponent` | disasm `APawn::GetVelocity` `[rcx+0x1B0]` | `0x1B0` (CLAUDE.md S131) | **0x1B0** PASS |

**9 / 9 offsets agree with values recorded from disassembly or live RPM in earlier sessions.**

### 1.4 The `+0xE0` trap, named

`UpdatedPrimitive` ends at `0xE0`; `Velocity` starts at `0xE8`. The 8 bytes at `0xE0` are
`UMovementComponent`'s packed bitfields (`bUpdateOnlyIfRendered`, `bAutoUpdateTickRegistration`,
`bTickBeforeOwner`, `bAutoRegisterUpdatedComponent`, `bConstrainToPlane`, `bSnapToPlaneAtStart`,
`bAutoRegisterPhysicsVolumeUpdates`, `bComponentShouldUpdatePhysicsVolume`) plus padding.
**A probe hardcoding `+0xE0` reads a bitfield word as `Velocity.X` and `Velocity.X` as `.Y`.**
That is a byte-level explanation of the CLAUDE.md-recorded S138 defect.

⚠ **Writing 32 bytes at `+0xE8` instead of 24 would clobber `PlaneConstraintNormal.X @0x100`.**
Write **exactly 24 bytes**, as **three doubles**, at `0xE8 / 0xF0 / 0xF8`. A probe that writes
three *floats* at `0xE8/0xEC/0xF0` corrupts `X`'s mantissa and `Y`'s exponent and produces a
garbage magnitude — which would make the whole safety analysis below inapplicable.

---

## 2. WHAT IS `CMC+0x1A0`?

### 2.1 It is `GravityScale`, not `ComponentVelocity` — the brief's premise is a class mix-up

`GravityScale` has 9 UHT records image-wide. The one at `.rdata 0x07FAF510` reads
**`Offset = 0x1A0`, gen = Float**, and its `PropPointers` array (`.rdata 0x07FB1BB0`, **164
entries**) begins:
```
[0] CharacterOwner       off=0x198  Object|ObjectPtr    <- matches Tier 1's disasm
[1] GravityScale         off=0x1A0  Float
[2] MaxStepHeight        off=0x1A4  Float
[3] JumpZVelocity        off=0x1A8  Float
[4] JumpOffJumpZFactor   off=0x1AC  Float
...
    MovementMode         off=0x231  Byte                <- matches CLAUDE.md's IsDashing disasm
```
Two members of that array (`CharacterOwner@0x198`, `MovementMode@0x231`) are independently
pinned by disassembly, so the array is **[M] `UCharacterMovementComponent`'s**.
⇒ **[M] `CMC+0x1A0` = `UCharacterMovementComponent::GravityScale`, a `float`.**
(Consistent with S138/S139 reporting `GravityScale 1.000`.)

`ComponentVelocity` at `+0x1A0` belongs to a **different class**: its record `.rdata 0x07EDFD40`
(`Offset=0x1A0`, gen=Struct, same FVector `ScriptStructFunc`) sits in a **31-entry** array
(`.rdata 0x07EE0280`) beginning `PhysicsVolume, AttachParent, AttachSocketName, AttachChildren,
ClientAttachedChildren…` and containing `RelativeLocation@0x158` and `Mobility@0x1BB` — i.e.
**`USceneComponent`**.

> ⚠ Two classes, one offset. This is CLAUDE.md's recorded trap
> ("never sample a byte offset across unrelated vtables") in its purest form, and the brief
> walked into it. **`CMC+0x1A0` and `SceneComponent+0x1A0` are unrelated fields.**

### 2.2 Yes — `Velocity` is copied to the scene component every frame

`UpdateComponentVelocity` (§1.2 (i)) writes `UpdatedComponent->ComponentVelocity` from
`this->Velocity`. Its call site:

```
0x035D6790  (callee of ULokiCMC vt disp 0xA50 -> tail 0x0530AC00 jmp 0x035D6790)
0x035D679F  mov  rax,[rcx]
0x035D67B3  call [rax+0x518]           ; *** UpdateComponentVelocity, UNCONDITIONAL, first call ***
0x035D67B9  mov  rcx,[rbx+0x198]       ; CharacterOwner
0x035D67C3  je   -> skip
0x035D67CD  add  rcx,0x5E8             ; OnCharacterMovementUpdated
0x035D67FF  call 0x0352A490            ; broadcast
```
Tier 1 §4.3 measured `0x035EB569 call [rax+0xA50]` inside engine `PerformMovement`, on a path
the `StartNewPhysics` call site **dominates** and which **post-dominates** `0x035EB1CB`.

⇒ **[M] If engine `PerformMovement` reaches its tail, `UpdatedComponent->ComponentVelocity` is
overwritten with `this->Velocity` in the same call, immediately before the `+0x16C8` flag is
cleared.**

★ **Free consequence, and it is a bonus receipt:** a `Velocity` sentinel that survives to the
tail of `PerformMovement` is copied into `USceneComponent::ComponentVelocity @ +0x1A0`, which
**is a reflected UPROPERTY** and therefore readable by name with no offset guesswork.
Reading the sentinel there ⇒ the `0xA50` call ran ⇒ (Tier 1 §4.3 dominance) **the
`StartNewPhysics` call site at `0x035EB13A` ran.** That is a *stronger* claim than the `+0x16B0`
snapshot receipt and it needs no new write.
⚠ [I] not [M] on the converse: `ComponentVelocity` may have other writers on dark pages, and
`PhysFalling` may have zeroed `Velocity` before the tail (§3.4 T3), so **absence there is not
evidence.** Use it as a one-way positive only.

---

## 3. SAFETY: IS `(0.0009765625, 0, 0)` PHYSICALLY INERT?

### 3.1 Consumer census (a FLOOR)

Method: for every distinct target in the `ULokiCMC` vtable (`.rdata 0x088F8570`, 449 slots) and
the engine `UCharacterMovementComponent` vtable (`.rdata 0x07FBED58`, 471 slots) — 454 distinct
functions — recursive-descent the body and record every memory operand at displacement
`0xE8/0xF0/0xF8` with a non-`rsp/rbp/rip` base.

```
functions with a hit                                              : 59
total hits                                                        : 362
functions accessing BOTH 0xE8 and 0xF8 off the SAME base register : 44
```
**FLOOR** twice over: only the two CMC vtables' one-level closure, and only the 55.48 % of
`.text` that is decrypted. It also cannot see consumers that receive `Velocity` by value.

(Loki overrides **69 of 449** slots relative to the engine vtable; disp `0x518`
`UpdateComponentVelocity` and disp `0x4D8` `StopMovementImmediately` and disp `0x7B0`
`CalcVelocity` are **not** among the overrides.)

### 3.2 The measured tolerance constants

| `.rdata` | value | UE name |
|---|---|---|
| `0x0769E370` (f32) / `0x076A5918` (f64) / `0x0769E398` (f64) | `1e-8` | `UE_SMALL_NUMBER` |
| `0x076B498C` (f32) / `0x076B49E8` (f64) | `1e-4` | `UE_KINDA_SMALL_NUMBER` |
| `0x076B8E74` (f32) / `0x076B8EE8` (f64) | `1e-6` | `MIN_TICK_TIME` |
| `0x077F5180` / `0x077D8100` (f64) | `1e-3` | `KINDA_SMALL_NUMBER * 10` |
| `0x0768C4C8` (f64) | `1.0` | `GetSafeNormal`'s `SquareSum == 1` fast path |
| `.data 0x099C86A0` | 24 zero bytes | `FVector::ZeroVector` |

### 3.3 ⚠⚠ THE ONE THAT MATTERS: a `Velocity.GetSafeNormal(1e-8)` inside `ULokiCMC::PerformMovement`

`ULokiCMC::PerformMovement` (`0x055B8370`, vt disp `0xAA8`) — **the function S139 measured to run
every frame** (`+0x12B0` `TimeSinceFallingStart` accumulation at `0x055B840C`) — contains, *after*
its Super call at `0x055B85C1`:

```
0x055B873B  cmp   byte [rsi+0x1308], 0        ; a ULokiCMC gate flag (live value UNMEASURED)
0x055B8769  jne   0x055B8865                  ; skip whole block if set
0x055B876F  mov   qword [rsi+0x1310], 0
0x055B877A  xorps xmm5, xmm5                  ; 0.0
0x055B877D  movsd xmm6, [rsi+0xF0]            ; Velocity.Y
0x055B8785  movsd xmm4, [rsi+0xE8]            ; Velocity.X
0x055B8790  mulsd xmm0,xmm6 ; mulsd xmm1,xmm4 ; addsd xmm1,xmm0    ; SizeSquared2D = X*X + Y*Y
0x055B879F  movsd xmm0, [0x0768C4C8 = 1.0]
0x055B87A7  ucomisd xmm1, xmm0 / jne 0x055B87E4          ; SquareSum == 1 fast path
0x055B87AD  ucomisd xmm5, [rsi+0xF8]                     ; ... and Velocity.Z == 0
0x055B87E4  comisd  xmm1, [0x076A5918 = 1e-8]
0x055B87EC  jae   0x055B880F                             ; >= tolerance -> NORMALISE
0x055B87EE  movups xmm2,[.data 0x099C86A0]               ; <  tolerance -> FVector::ZeroVector
0x055B880F  sqrtsd xmm1,xmm1 ; divsd xmm3,xmm1           ; 1/|V|
0x055B8838  (three ucomisd vs 0.0: only if result != (0,0,0))
0x055B8856  movups [rsi+0x12F0], xmm2                    ; *** WRITE ***
0x055B885D  movsd  [rsi+0x1300], xmm0                    ; *** WRITE ***
```

`scratchpad/s140/tools/lokicmc_props.txt:48` names the target:
**`0x12F0 LastNonZeroDirection2D`** — a reflected `Struct` UPROPERTY of `ULokiCMC`.
(Tier 1 §2's ladder already listed `+0x12F0 / +0x1300` as *"USELESS in this state — skipped when
`Velocity == (0,0,0)`"*. This is the mechanism, and it is exactly the mechanism a non-zero
sentinel defeats.)

**[M] The gate is `Velocity.SizeSquared2D() >= 1e-8`.**

| sentinel `X` | `X²` | vs `1e-8` |
|---|---|---|
| **`2^-10 = 9.765625e-04` (the brief's)** | `9.536743e-07` | **95.4× ABOVE → BRANCH FLIPS** |
| `2^-20 = 9.5367431640625e-07` | `9.094947e-13` | 1.1e4× below — no flip |
| `~2^-31` (recommended, §5) | `6.5e-19` | 1.5e10× below — no flip |

⇒ **the brief's sentinel changes which branch of a live, every-frame function executes, and
causes a write of a unit direction into a reflected gameplay UPROPERTY that today holds a stale
value.** `LastNonZeroDirection2D` is, by its name and its 2D normalisation, the kind of field a
dash / mantle / wall-jump direction reads. **That is a gameplay perturbation, not a no-op.**

⚠ **Grade split:** [M] that the gate exists and that `2^-10` clears it by 95×.
**[I], not [M],** that the write *fires* in the staged world — the block is gated on
`byte [CMC+0x1308] == 0` and that byte has never been read.

### 3.4 The rest of the enumerated threshold branches

| # | site | quantity tested | threshold | `2^-10` | `~2^-31` |
|---|---|---|---|---|---|
| T1 | `0x055B87E4` `ULokiCMC::PerformMovement` (vt `0xAA8`) | `Vel.SizeSquared2D` (`GetSafeNormal`) | `1e-8` | **TRIPS (95×)** | safe (1.5e10×) |
| T2 | `0x035D5F6C` `CalcVelocity` (vt `0x7B0` = `0x035D5D20`, **not overridden by Loki**) | `Vel.SizeSquared` (`GetSafeNormal`) | `1e-8` | **TRIPS** | safe |
| T3 | `0x035ED98E` engine `PhysFalling` (vt `0x830` eng = `0x035EC850`) | `SizeSquared2D` of the gravity-transformed velocity → **`xorps` the vector if `<= 1e-3`** | `1e-3` | falls into the **ZERO** branch — self-healing, see §3.6 | same |
| T4 | `0x035EDBEE` engine `PhysFalling` | a `.Z` component vs `1e-3` (`jae` skip) | `1e-3` | Z=0 ⇒ same as today; a Z-carrying `2^-10` is **2.3 % under the bar** | safe |
| T5 | `0x055B8F7C` Loki `PhysFalling` (`0x055B89F0`) | `\|V2D\|` vs `[CMC+0x1678]` (a real speed cap) | runtime | safe — `sqrtpd` is above, the divide is *inside* the `ja` arm | safe |
| T6 | `0x055B8FFB` Loki `PhysFalling` | `SizeSq2D` vs `MaxSpeed²`, then `sqrtsd`/`divsd` on the `ja` arm | runtime | safe | safe |
| T7 | `0x035D5D6E` `CalcVelocity` entry | **DeltaTime** vs `1e-6` (`MIN_TICK_TIME`) | `1e-6` | not a velocity test | — |
| T8 | 5 sites — `0x035D483E`, `0x035D56E8`, `0x035E1D08`, `0x035E9B9D`, `0x035FC4A4` | **exact `Velocity.IsZero()`** (`xorps xmmN,xmmN; ucomisd xmmN,[b+0xE8/F0/F8]`) | exact `0` | **FLIPS** | **FLIPS** |
| T9 | `0x035FBF4C..0x035FBF78` | `LastUpdateVelocity(0x378/0x380/0x388) == Velocity(0xE8/F0/F8)`, exact, all three | exact | **FLIPS** | **FLIPS** |

**⇒ T8/T9 are the irreducible floor: ANY non-zero sentinel, of any magnitude, flips every exact
`IsZero()` / `==` test on `Velocity`.** That cannot be engineered away by choosing a smaller
value — only by not poking `Velocity` at all (§5.3). Observed consequences are branch selection
only (`setne`/`jne` into an alternative code path), with no arithmetic hazard at either site.

⚠ `0x035E1D08` tests `Acceleration.IsZero() && Velocity.IsZero()` together; the function is
unnamed here. `0x035D56E8` sits behind `cmp byte [CharacterOwner+0x160], 3`
(`Role == ROLE_Authority`), which **this client does satisfy** (CLAUDE.md S137: `Role@0x160 = 3`),
so it is reachable.
⚠ `0x035FC4A4` tests `+0xE0/+0xE8/+0xF0` off `rdi`; I did **not** establish that `rdi` is a CMC,
so that row is **[I]**, not [M].

### 3.5 Division / normalisation — no unguarded reciprocal found, but the census is bounded

`div*` / `sqrt*` counts in the biggest consumers: `CalcVelocity` 6 div + 9 sqrt;
engine `PhysFalling` (`0x035EC850`) 8 div + 3 sqrt; Loki `PhysFalling` (`0x055B89F0`)
3 div + 3 sqrt; `ULokiCMC::PerformMovement` 1 div + 1 sqrt.

I **read the guard at every div/sqrt site in `0x055B89F0` (5 sites), in `CalcVelocity` (4 sites),
and at 4 of the 11 sites in `0x035EC850`.** Every one inspected is guarded — either
`SizeSquared >= 1e-8` (the `GetSafeNormal` idiom: `sqrtsd` then `divsd` only on the `jae` arm),
or `|x| > 1e-8` (`andps` abs-mask then `comisd` then `ja`), or `SizeSq > MaxSpeed²`.
⇒ **[I, strong], NOT [M]: there is no unguarded `1/|Velocity|` on this path.** The unchecked
remainder is 7 div/sqrt sites in `0x035EC850` plus 40 unexamined consumer functions.

★ **A counter-argument that caps this whole risk class independently of the census:** today
`Velocity` is exactly `(0,0,0)` every frame. An unguarded `1/|V|` would therefore already produce
`±Inf` (or `NaN` from `0/0`) **every frame today**, and the process is demonstrably stable.
Substituting a finite `1/8.07e-10 = 1.24e9` is a *better-behaved* value than the `Inf` the code
already tolerates. (Note this argument is direction-neutral between candidate sentinels: a
*smaller* sentinel gives a *larger* reciprocal. It bounds the class; it does not rank the values.)

### 3.6 ⚠⚠ THE TIER-1 DECISION RULE IS DEFECTIVE — corrected interpretation table

Tier 1 §5 says: *"`+0xE8` no longer holds the sentinel ⇒ the probe's own control failed; the run
is void."*

**T3 refutes it.** `0x035ED98E` in engine `PhysFalling` compares a horizontal SizeSquared against
`1e-3` and, on the `jbe` arm, writes `xorps xmm0,xmm0` back over the vector
(`0x035ED998 xorps xmm0,xmm0 ; 0x035ED9AC movups [rbp+0x168],xmm0`). The brief's sentinel has
`SizeSq = 9.54e-7`, i.e. **1048× below `1e-3`** — so **the branch that zeroes it is exactly the
branch a running physics step takes.** In other words: *if `StartNewPhysics` runs, the expected
observation is `+0xE8` no longer holding the sentinel* — and the Tier 1 rule throws that away as
VOID.

**Corrected table (single Velocity poke, as Tier 1 proposes):**

| `+0x16B0` snapshot | `+0xE8` Velocity | reading |
|---|---|---|
| **== sentinel** | == sentinel | **SNP ran** [M]; nothing downstream rewrote Velocity |
| **== sentinel** | `(0,0,0)` or other | **SNP ran** [M] — *and* something downstream (T3 / `CalcVelocity`) wrote Velocity. This is an **expected** outcome, not a void run |
| `(0,0,0)` | == sentinel | **SNP did not run** [M] — but this state is degenerate under a single-poke design, see §5.3 |
| `(0,0,0)` | `(0,0,0)` | **AMBIGUOUS** — write never landed, or SNP ran and something else also fired |

⇒ **The probe's control must be an IMMEDIATE read-back of `+0xE8` right after the write, before
any wait — not a read-back after 3 frames.**

### 3.7 Blast radius outside the movement component

Because §2.2's copy is unconditional at the tail, and because `APawn::GetVelocity`
(§1.2 (iii)) falls through to `MovementComponent->Velocity` (S139 measured
`bSimulatePhysics == 0` and `WeldParent == NULL` on the hero capsule, so the
`IsSimulatingPhysics` arm is not taken), a `Velocity` sentinel is visible to:

- `USceneComponent::ComponentVelocity` (reflected) → `AActor::GetVelocity` (vt disp `0x380`);
- `APawn::GetVelocity()` → every AnimBP `Get Velocity` node, every AI/perception speed query,
  camera and HUD readers;
- `ULokiCMC::GetRecentVelocity` (§4) when the flag is 0, which *is* the between-frames state.

At `~2^-31` (≈1.6e-9 uu/s) every one of those reads a number that rounds to zero in any display,
in any comparison against a walk/run threshold, and on any blendspace axis. At `2^-10`
(≈1e-3 uu/s) it is still far below any locomotion threshold, but it is **above
`UE_KINDA_SMALL_NUMBER = 1e-4`, so any `IsNearlyZero()` in an AnimBP or AI predicate flips.**

⚠ I did **not** enumerate AnimBP/AI consumers — that is a Blueprint-corpus question and my
attempts to grep `tools/extractor/out` (**5.2 GB**) **timed out at 20 s and again at 120 s**.
Per CLAUDE.md's own recorded rule, **a timeout is not a negative**: this is **UNMEASURED**, not
"no consumers".

---

## 4. `GetRecentVelocity` AND ITS CONSUMERS

### 4.1 Identification (reproduces Tier 1 §4.5 with my own code)

`.data 0x09BC9AD0` = `{ NameUTF8 -> "GetRecentVelocity", 0x0530C7E0, 0x0530AC10 }`.
Passing control: `.data 0x09BC4B60` = `{ "GetLokiCharacterMovement", 0x05300710, 0x055AC8E0 }`,
whose impl matches the address already recorded in the repo, **and which I independently observe
being called at `0x0559C590`**.

```
0x0530AC10  80 b9 c8 16 00 00 00     cmp   byte [rcx+0x16C8], 0
0x0530AC17  b8 b0 16 00 00           mov   eax, 0x16B0        ; the snapshot
0x0530AC1C  41 b8 e8 00 00 00        mov   r8d, 0xE8          ; live Velocity
0x0530AC22  41 0f 44 c0              cmove eax, r8d           ; flag==0 -> Velocity ; flag!=0 -> snapshot
0x0530AC26  0f 10 04 08              movups xmm0,[rax+rcx]
```

### 4.2 The complete idiom census

Scanning `.text` for every encoding of `mov r32, 0x16B0` (`[41] b8..bf b0 16 00 00`) returns
**5 hits, of which 3 are the idiom** (the other 2, `0x014B8BD2` and `0x027D5270`, are byte-pattern
false positives — the real instructions there are `mov [rbp+0x16b0], reg`, i.e. stack
displacements in unrelated functions):

| site | context |
|---|---|
| `0x0530AC17` | `ULokiCMC::GetRecentVelocity` **impl** |
| `0x0530C7F1` | the **UHT exec thunk** `0x0530C7E0` — an inlined copy, so the Blueprint path never calls the impl |
| `0x0559C5A5` | inlined into an **`ALokiCharacter`** function (see below) |

**Callers of the impl and of the thunk (rel32 `call`/`jmp` scan over the whole `.text` buffer):**
```
rel32 -> 0x0530AC10 (impl)  : 0
rel32 -> 0x0530C7E0 (thunk) : 0
rel32 -> 0x0530ABF0 (vt A50): 0     (it is a vtable slot; expected)
stored qword ptr -> 0x0530AC10 : 1   (.data 0x09BC9AE0, the registration triple)
stored qword ptr -> 0x0530C7E0 : 1   (.data 0x09BC9AD8, the registration triple)
```
⇒ **[M, FLOOR] `GetRecentVelocity` has ZERO direct C++ callers in the decrypted image. Its only
reachable surface is the reflected thunk** (Blueprint / `CallFunctionByName` / the S55 primitive).
⚠ FLOOR: a call from a dark page is all-zero bytes and undetectable. Whether any shipped
Blueprint calls it is **UNMEASURED** (§3.7's timeout).

**The third site, `0x0559C59E`:**
```
0x0559C582  cmp  qword [rcx+0x1FA0], 0 / je
0x0559C590  call 0x055AC8E0                  ; GetLokiCharacterMovement()   <- the naming control
0x0559C598  test rax,rax / je
0x0559C59E  cmp  byte [rax+0x16C8], 0        ; <-- inlined GetRecentVelocity
0x0559C5A5  mov  ecx, 0x16B0
0x0559C5B2  mov  edx, 0xE8
0x0559C5BF  cmove ecx, edx
0x0559C5F0  movups xmm6,[rcx+rax]            ; recent velocity .X/.Y
0x0559C5E2  movsd  xmm0,[rcx+rax+0x10]       ; recent velocity .Z
0x0559C5E8  movups xmm9,[rax+0x378]          ; LastUpdateVelocity  (also consumed)
```

⚠ **SELF-CORRECTION, recorded because it nearly became a finding.** I first read the
`andps`/`comisd 1e-4` sequence at `0x0559C618..0x0559C654` as a component-wise
`IsNearlyZero(KINDA_SMALL_NUMBER)` **on the recent velocity**, which would have been a second
headline trip for the `2^-10` sentinel. **It is not.** The tested pointer is `rdi = rbx + 0x1F88`,
an `ALokiCharacter` field loaded at `0x0559C5CA` — not the velocity. **The claim is withdrawn**;
the `1e-4` test there is on a different vector.

### 4.3 ★★ Why a poked SNAPSHOT is provably unreadable

From Tier 1 §4.6 (reproduced independently below): the **only** writers of the flag `+0x16C8` are
the SNP reset `0x055C2441`, the SNP set `0x055C2469`, the `0xA50` clear `0x0530ABF9`, the
destructor `0x0530AB4C`, and the constructor `0x0559FDF4`.

⇒ **flag == 1 ⟺ `StartNewPhysics` executed `0x055C2469` and the `0xA50` clear has not yet run.**
And `0x055C244F` (the snapshot write, `snapshot ← Velocity`) precedes `0x055C2469` by `0x1A`
bytes **with no branch between them**.

⇒ **[M] whenever the flag is 1, the snapshot holds the live `Velocity`, never a poked value.**
And when the flag is 0, all three `cmove` consumers read `+0xE8` instead.
⇒ **A value poked into `+0x16B0` can never be observed by any consumer.** It is dead storage
until `StartNewPhysics` overwrites it. **This is what makes the snapshot poke physically inert in
a way the Velocity poke can never be.**

⚠ One bounded exception: an external `WriteProcessMemory` is not atomic against the game thread.
If a 24-byte write interleaves inside the ~6-instruction window `0x055C244F..0x0530ABF9`, a
consumer could see a torn snapshot for one frame. With a `~2^-31` payload the worst case is a
tiny velocity for one frame. Window ≈ 1e-7 of wall time.

### 4.4 Independent reproduction of Tier 1's `+0x16B0` writer claim

Censusing every memory operand with displacement in `[0x16B0, 0x16C7]` across all 454 CMC-vtable
functions (my code, my CFG):
```
fn 0x055C2430  0x055C244F  W  movups [rcx+0x16B0], xmm0
fn 0x055C2430  0x055C245E  W  movsd  [rcx+0x16C0], xmm1
total 2
```
⇒ **[M, FLOOR] the only CMC-side writer of the snapshot is `ULokiCMC::StartNewPhysics`.**
Agrees with Tier 1 §4.6, derived independently, on a differently-written instrument.

---

## 5. SENTINEL RECOMMENDATION

### 5.1 What the sentinel actually has to do

Exactly one thing: **be bit-distinguishable from `(0,0,0)` after an exact 24-byte copy.** Both
copies on the path (`movups`+`movsd` at `0x055C244F`/`0x055C245E`, and `movups`+`movsd` at
`0x036523FC`/`0x03652403`) are **data moves, not arithmetic** — they preserve bits exactly.
There is **no lower bound on magnitude** imposed by the measurement. There is an upper bound
imposed by every threshold in §3.4. **Therefore: as small as possible, as tagged as possible.**

### 5.2 Recommended value — pin the exponent tiny, put the magic in the mantissa

```
Velocity sentinel (write as three IEEE-754 binary64 values, little-endian):
    CMC+0xE8  X = 0x3E000000DEADBEEF   =  4.6566167359369849e-10
    CMC+0xF0  Y = 0x3E000000CAFEBABE   =  4.6566163944799538e-10
    CMC+0xF8  Z = 0x3E0000005AFE7E57   =  4.6566144515736723e-10
```

Properties, all computed:

| property | value |
|---|---|
| each component | **normal** double (biased exp `0x3E0` ⇒ 2^-31 × 1.0000005), **not** denormal ⇒ immune to FTZ/DAZ |
| `\|V\|` | `8.065e-10` uu/s |
| `\|V\|²` | `6.505e-19` |
| vs T1/T2 gate `1e-8` on SizeSquared | **1.54e10× BELOW** — no flip |
| vs `1e-4` on any component | 2.1e5× below — no flip |
| vs `1e-3` (T3/T4) | far below — same branch as `0.0` |
| vs `1e-6` | far below — same branch as `0.0` |
| displacement at 16.7 ms | **1.3e-11 uu** (≈ 1e-13 m) |
| tag width | **96 bits** of magic (3 × 32) + a pinned exponent ⇒ false-positive probability from heap garbage ≈ 0 |
| exactly representable / round-trippable | yes, by construction (it *is* a bit pattern) |

**Why not the brief's `2^-10 = 0.0009765625`:** it trips T1 and T2 by ~95×, sits **2.3 %** under
T4's `1e-3` bar and **4.6 %** under a `1e-6` bar on SizeSquared — margins thin enough that a
different component, a `Size` vs `SizeSquared` mix-up, or a slightly different value flips them.
It buys nothing: the receipt is a bit comparison either way.

**Why not something even smaller (e.g. `2^-1000`):** denormals begin near `2^-1022`, and UE
builds sometimes enable `_MM_FLUSH_ZERO` / DAZ; a denormal could be flushed to `0.0` by any
arithmetic op it passes through, silently destroying the receipt. `2^-31` is 991 binades clear of
that and still 15 orders of magnitude below the nearest live threshold.

⚠ If the operator prefers a "clean" constant over a tagged one, **`2^-20 = 9.5367431640625e-07`
(bits `0x3EB0000000000000`) is also acceptable** — SizeSq `9.09e-13`, still 1.1e4× under T1/T2 —
but it carries only ~1 bit of tag against a garbage read. The tagged form is strictly better.

### 5.3 ★★ THE BETTER ARM: pre-poke the snapshot too, with a *second* tag

**Write both, in one pass, snapshot first:**
```
    CMC+0x16B0 SX = 0x3E00000111111111
    CMC+0x16B8 SY = 0x3E00000122222222
    CMC+0x16C0 SZ = 0x3E00000133333333
    CMC+0xE8   X  = 0x3E000000DEADBEEF
    CMC+0xF0   Y  = 0x3E000000CAFEBABE
    CMC+0xF8   Z  = 0x3E0000005AFE7E57
    *** NEVER touch CMC+0x16C8, the flag byte. ***
```
Immediately read back all six as the probe's own control (§3.6). Wait ≥ 3 frames. Then read
`CMC+0x16B0..0x16C7`, `CMC+0xE8..0xFF`, and — free — `UpdatedComponent+0x1A0..0x1B7`.

| `+0x16B0` reads | verdict |
|---|---|
| **the VELOCITY tag** (`DEADBEEF/CAFEBABE/5AFE7E57`) | **`ULokiCMC::StartNewPhysics` ran with `Iterations == 0`** — [M], positive, 96-bit distinctive |
| **the SNAPSHOT tag** (`11111111/22222222/33333333`) | **`StartNewPhysics` did not run** — [M], and this now *excludes* the "an unknown writer zeroed it" alternative |
| **`(0,0,0)`** | **a THIRD state: something other than `0x055C244F` wrote the snapshot.** Under Tier 1's single-poke design this state is **indistinguishable from "unchanged"** and would be silently mis-read as "did not run" |
| anything else | torn write or instrument fault; re-run |

**That third state is the concrete methodological gain of the second tag.** Tier 1's design cannot
see it, because the snapshot's resting value *is* `(0,0,0)`. Given `.text` is only 55.48 %
decrypted, "the only writer is `0x055C244F`" is a FLOOR, so an unknown writer is exactly the
alternative that needs excluding.

Cross-checks available in the same read, at no extra cost:
- `UpdatedComponent+0x1A0` holding the **velocity** tag ⇒ engine `PerformMovement` reached the
  `0xA50` call at `0x035EB569` ⇒ (Tier 1 §4.3 dominance) the SNP call site ran. **Stronger than
  the snapshot receipt.** One-way only (§2.2).
- `CMC+0xE8` no longer holding the tag ⇒ the game wrote `Velocity` (T3 / `CalcVelocity`) —
  informative, **not** a void run (§3.6).
- `CMC+0x12F0` (`LastNonZeroDirection2D`) **must NOT change** with the recommended sentinel
  (T1 is not tripped). If it does change, the sentinel was mis-typed as floats or written at the
  wrong offsets. **That is a free negative control on the probe itself.**

### 5.4 Residual risks I cannot remove

1. **T8/T9 — the exact `IsZero()` / `==` tests flip for any non-zero value.** 6 known sites;
   observed consequences are branch selection only, no arithmetic hazard.
2. **7 unexamined div/sqrt guards in `0x035EC850` and 40 unexamined consumer functions** — §3.5
   is [I, strong], not [M].
3. **AnimBP / AI consumers of `APawn::GetVelocity()` are UNMEASURED** (grep timeout, §3.7).
4. **External `WriteProcessMemory` is a repo-recorded UNRESOLVED hazard** (S138, n=1, confounded
   by a high FK-32 base rate). Pair with a matched no-write sitting, per Tier 1.
5. **`byte [CMC+0x1308]`** (T1's gate) and `byte [CMC+0x16C8]` at the instant of the write are
   both unread; §4.3's interleaving analysis bounds but does not eliminate a torn frame.
6. The consumer census is bounded to the two CMC vtables' one-level closure. Anything holding a
   raw `UCharacterMovementComponent*` outside that closure is invisible to it.

---

## 6. WHAT THIS LANE MEASURED vs INFERRED

| claim | grade |
|---|---|
| `Velocity @ CMC+0xE8`, FVector, 3 doubles, `X/Y/Z @ 0xE8/0xF0/0xF8`, 24 B | **[M]** — 4 instruments, 9/9 controls |
| Declared on `UMovementComponent`, not `UCharacterMovementComponent` | **[M]** — UHT array + `binds_members.csv` |
| The struct is named `"Vector"`; members `LargeWorldCoordinatesReal` at stride 8 | **[M]** |
| `FStructParams.SizeOf == 0x18`, `Alignment == 8` | **[I]** — field layout not calibrated on a second struct |
| `CMC+0x1A0 == GravityScale` (float) | **[M]** |
| `USceneComponent+0x1A0 == ComponentVelocity` | **[M]** |
| `UpdateComponentVelocity` = vt `0x518` = `0x036523F0`, copies Velocity → ComponentVelocity | **[M]** |
| It is called unconditionally, first, from the `0xA50` callee `0x035D6790` | **[M]** |
| The `1e-8` SizeSquared2D gate in `ULokiCMC::PerformMovement` at `0x055B87E4` | **[M]** |
| `2^-10` clears it by 95× | **[M]** (arithmetic on measured constants) |
| That trip *fires* in the staged world | **[I]** — `byte [CMC+0x1308]` unread |
| `CMC+0x12F0 == LastNonZeroDirection2D` | **[M]** (props table + the write site) |
| `PhysFalling` zeroes horizontal velocity below `1e-3` at `0x035ED98E` | **[M]** on the compare + the `xorps` branch; **[I]** that the tested vector is `Velocity` after the gravity transform |
| Six exact `IsZero()`-style sites flip for any non-zero sentinel | **[M]** for 5; `0x035FC4A4` is **[I]** (base not proven to be a CMC) |
| No unguarded `1/\|Velocity\|` on the path | **[I, strong]** — 13 of ~20 div/sqrt guards read |
| `GetRecentVelocity` has 0 direct C++ callers; 3 idiom sites | **[M, FLOOR]** |
| A poked `+0x16B0` snapshot is unreadable by any consumer | **[M]**, modulo the ~1e-7 interleave window |
| Only CMC-side writer of `+0x16B0` is `0x055C244F` | **[M, FLOOR]** — reproduced independently |
| Blueprint consumers of `GetRecentVelocity` / `GetVelocity` | **UNMEASURED** — rg timed out twice on a 5.2 GB corpus; **not a negative** |

---

## 7. FILES

`scratchpad/s140t2/pe.py` (PE reader, written for this lane) ·
`uht.py` (FPropertyParams decoder + name→record lookup) ·
`walk.py` (PropPointers array walker) ·
`xdis.py` (capstone helpers) ·
`census.py` (recursive-descent per-function CFG + displacement census) ·
`vel_hits.pkl` (the 362-hit census).
All read-only; no game process touched; no `.text` written; zero launches.
