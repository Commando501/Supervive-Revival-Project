# S140 SHARED BRIEF — read this first. OFFLINE ONLY.

## Absolute rules
- **NO launches, NO injection, NO staging, NO writes to the game.** Static analysis only.
- Grade every claim `[M]` measured (with a stated positive control + its result) / `[I]` inferred
  (say from what, how strongly) / `[S]` speculation. **An [I] stated as [M] is this project's most
  costly error class.**
- **Record raw, derive afterwards.** A `set()` collapses `-0.0` and `0.0` and has destroyed a
  finding here. Print samples, not just verdicts.
- **Recompute every RVA with a machine.** Hand arithmetic has produced false findings here.
- Do not cross a function boundary with an inference. "X advances" inside a wrapper says nothing
  about the callee.

## Image
`dumps/merged13.dump.exe` — ImageBase `0x7FF608F40000`, **RVA == file offset (VERIFIED: all 10
sections have VirtualAddress == PointerToRawData).** `.text` ~55.5% demand-decrypted.
**An all-zero page is DARK = never executed. NOT "absent", NOT "stripped".** Grade FOLD/REAL/DARK.

Fold (stripped-stub) impls — an impl equal to one of these is an empty stub:

    0x00F7EC20  c2 00 00     ret 0    (VOID no-op; does NOT zero eax)
    0x00F7EB50  33 c0 c3     null/0
    0x00F7EB60  32 c0 c3     false
    0x00B9E1F0  b0 01 c3     true
    0x00FC6CF0  0f 57 c0 c3  0.0f

A SIXTH shape defeats a two-state test: `sub rsp,0x28; call <GetWorld>; xor eax,eax; ret`.
**A folded RVA names nothing** (`0xF7EC20` has ~165,789 references).
Known-DARK control (must read 0/4096): `0x5A6AC40` (ULokiRespawnComponent::Respawn).

## Shared instruments (already built + self-tested — USE OR REPLACE, but say which)
- `scratchpad/s140/tools/peimg.py` — `Img()` with `.read(rva,n)`, `.page_nonzero(rva)`, `.flat()`.
- `scratchpad/s140/tools/cfg.py` — recursive-descent `CFG(img, entry)` with `.insns`, `.succ`,
  `.pred`, `.calls`, `.indirect_jumps`, `.noreturn_candidates`, `.decode_failures`,
  `.reach_backward(t)`, `.exits_from(t)`. `python cfg.py` runs a 4-control self-test (PASSES).
  Validated: `CFG(im, 0x035E9EC0)` -> **1461 insns, 148 calls, 0 indirect jumps, 0 decode failures,
  0 noreturn candidates** — independently reproducing S139's recursive-descent count of 1461
  (a linear sweep decodes only 1074 and is UNSOUND here).

capstone 5.0.7 is installed. Write your own harness if you prefer — but then say so and show your
control results, because two instruments agreeing is worth far more than one.

## Verified this session (session lead, before fan-out) — do not re-derive, do not contradict silently

1. `ULokiCMC::PerformMovement`'s Super call at `0x055B85C1` = `e8 fa 18 03 fe` -> **`0x035E9EC0`**
   (machine-recomputed). Engine `PerformMovement` IS the callee. [M]

2. `ULokiCMC::StartNewPhysics 0x055C2430` disassembles as:

        0x055c2430  movaps xmm2, xmm1
        0x055c2433  test   r8d, r8d                    ; r8d = Iterations
        0x055c2436  jne    0x55c2475                   ; Iterations != 0 -> OTHER path, latch NOT written
        0x055c2438  cmp    byte [rcx+0x16c8], r8b      ; r8b==0 here => cmp latch, 0
        0x055c243f  je     0x55c2448                   ; already 0 -> skip redundant store
        0x055c2441  mov    byte [rcx+0x16c8], r8b      ; store 0 (redundant)
        0x055c2448  movups xmm0, [rcx+0xe8]            ; Velocity
        0x055c244f  movups [rcx+0x16b0], xmm0          ; Velocity snapshot
        0x055c2456  movsd  xmm1, [rcx+0xf8]
        0x055c245e  movsd  [rcx+0x16c0], xmm1
        0x055c2466  movaps xmm1, xmm2
        0x055c2469  mov    byte [rcx+0x16c8], 1        ; *** THE LATCH ***
        0x055c2470  jmp    0x3600990                   ; *** TAIL-JUMP to ENGINE StartNewPhysics ***
        0x055c2475  jle    0x55c2493
        0x055c2477  cmp    byte [rcx+0x231], 3         ; MovementMode == MOVE_Falling
        0x055c247e  jne    0x55c2493
        0x055c2480  movaps xmm0, xmm2
        0x055c2483  addss  xmm0, dword [rcx+0x12b0]    ; +0x12B0 writer #2

   => **the latch is written ONLY on the `Iterations == 0` path**, which is exactly the
   PerformMovement call. It is therefore SOUND for "did PerformMovement reach StartNewPhysics",
   but it is **NOT a pure sticky latch** — it is cleared-then-set within that call.
   WARNING: whether anything ELSE clears `+0x16C8` is an OPEN question assigned to lane A4.

3. Session lead's own `exits_from(0x035EB13A)` over engine PerformMovement returned **7 edges**:
   the six S139 named, plus the call node's own fallthrough edge `0x035EB13A -> 0x035EB140`
   (an artifact of including the target as a source). `|R| = 1075` of 1461. **No backward bail
   appeared.** THIS IS A PREVIEW, NOT THE ANSWER — your job is to confirm or refute it independently.

4. `0x055C2483 = f3 0f 58 81 b0 12 00 00` = `addss xmm0,[rcx+0x12b0]`, `0x055C248B = f3 0f 11 81 ...`
   = `movss [rcx+0x12b0],xmm0`. Writer #2 CONFIRMED present in raw bytes.

5. `0x055A74D6 = f3 0f 11 b6 b0 12 00 00` = `movss [rsi+0x12b0], xmm6`. Writer #3 CONFIRMED present.

## Key addresses (RVAs)

    engine PerformMovement        0x035E9EC0   StartNewPhysics call 0x035EB13A   ret 0x035EB1CA
            bail targets seen:    0x035EB1A7, 0x035EB7CF, 0x035EB150
            HasValidData          0x035E64C0  (vtable disp 0x6B8)
            ShouldSkipUpdate      0x0364BA80  (disp 0x4E0)
            ControlledCharacterMove 0x035DCD10  Accel store 0x035DCD6B, Analog 0x035DCD8F,
                                                PerformMovement call 0x035DCDAC (guarded cmp cl,3)
            StartNewPhysics       0x03600990   MIN_TICK_TIME comiss 0x036009A8 vs 1e-6f @0x076B8E74
                                               own IsSimulatingPhysics gate 0x036009D3/E4/EC
                                               log .rdata 0x07FC0670 (CharacterMovementComponent.cpp:3477)
                                               8-entry jump table 0x03600BF8, bounded cmp esi,7
    Loki    TickComponent         0x055C2B90  (disp 0x3D0)
            PerformMovement       0x055B8370  (disp 0xAA8)   Super call 0x055B85C1
              dt in xmm6 0x055B838D | HitStop call 0x055B83B5 | xorps xmm6,xmm6 0x055B83FA
              +0x12B0 accumulate 0x055B840C / store 0x055B8414
              fwd branches toward Super: 0x055B845E (test byte [CharacterOwner+0x580],8 / jne),
                                         0x055B846B (mov ebp,[rsi+0x1988]; sub ebp,1; js)
            StartNewPhysics       0x055C2430  (disp 0x720)   latch write 0x055C2469
            ControlledCharacterMove 0x055A7680 (disp 0x890)
            ConstrainInputAcceleration 0x055A75B0 (disp 0xA38)  IsStunned predicate 0x055B2930
            PhysFalling           0x055B89F0  (disp 0x830)
            GetMaxAcceleration    0x055AC910   GetMaxSpeed 0x055ACB90
    primitives: IsSimulatingPhysics disp 0x4C0 | GetBodyInstance disp 0x810 (= 0x03C91C60)
    ULokiCharacterMovementComponent vtable .rdata 0x088F8570, 413 slots, 64 overridden

## Live measurements already banked (S139 flights 1-4). Do NOT contradict silently.

Identity controls passed (`CMC+0x198 == pawn`, FTickFunction `Target == CMC`).

| field | offset | bot | player |
|---|---|---|---|
| UpdatedComponent | CMC+0xD0 | non-null CapsuleComponent | same |
| World | CMC+0xC0 | non-null | non-null |
| CharacterOwner | CMC+0x198 | == pawn | == pawn |
| MovementMode | CMC+0x231 | **3** (MOVE_Falling) | **3** |
| Mobility | UpdatedComponent+0x1BB | **2** (Movable) | **2** |
| WeldParent | UpdatedComponent+0x5F0 | **NULL** | — |
| bSimulatePhysics | BodyInstance(+0x3F0)+0x10 mask 0x01 | **0** | — |
| Role / RemoteRole | pawn+0x160 / +0x72 | **3** / 1 | 3 / 1 |
| Controller | pawn+0x400 | non-null | non-null |
| RF_Garbage | pawn ObjectFlags+0x0C bit30 | 0 | 0 |
| **latch** | **CMC+0x16C8** | **0** | **0** (and 0 on all 37 CMCs in the world) |
| Velocity | CMC+0xE8 | (0,0,0) | (0,0,0) |
| Acceleration | CMC+0x328 | input x 50000 after GAS port | 0 (untreated control) |
| MaxAcceleration | via GAS | 50000 after port | — |
| AnalogInputModifier | — | 0 | 0 |
| TimeSinceFallingStart | CMC+0x12B0 | advances 1.0x real time | advances 1.0x real time |
| tick | PrimaryComponentTick @UActorComponent+0x40 | bCanEverTick 1, TickState Enabled, Prerequisites.Num 1, **bRegistered False**, TaskPointer 0, LastTickGameTimeSeconds **-1.0** | identical |
| AttributeSetStorage | +0xF08 | NULL before port | non-null |
| AbilitySystemComponentStorage | +0xF00 | **NULL** | non-null (KWIREGAS) |

`FTickFunction` sizeof 0x28: TickGroup+0x08, EndTickGroup+0x09, flags+0x0A
(bTickEvenWhenPaused 0x01, bCanEverTick 0x02, bStartWithTickEnabled 0x04,
bAllowTickOnDedicatedServer 0x08), TickState+0x0B (0=Disabled 1=Enabled),
TickInterval+0x0C, InternalData+0x20 (**NULL == never registered**).

**This build's `EMovementMode` is MODIFIED: `MOVE_Dashing` inserted at index 6, so `MOVE_Custom==7`,
`MOVE_MAX==8`.** Any probe carrying stock UE's `MOVE_Custom==6` mis-decodes by one.

## The contradiction to attack

A written `Acceleration` proves `ControlledCharacterMove` ran (S139 flight 3: `Acceleration@CMC+0x328`
carried `ControlInputVector`'s SIGN in 22/22 samples — a signed zero; a never-written field is +0.0
forever and cannot track a sign). It calls `PerformMovement` at `0x035DCDAC` whenever
`Role==ROLE_Authority` (measured 3). Loki `PerformMovement` reaches its Super unconditionally.
Six engine exits, all inputs measured passing. **Yet the latch is 0 and the pawn moves 0.00 uu.**
Either an exit tests something other than what we measured, or the enumeration is incomplete,
or an upstream assumption is wrong.

## Traps that have each fired in this project

1. A linear disassembly sweep is not a CFG (1074 vs 1461 here).
2. `target > call` as an exit predicate is blind to BACKWARD bails.
3. A disp32 byte-pattern scan is a FLOOR and it desyncs (a prior attempt emitted
   `adc byte ptr [rbp+0x12b0]` and MISSED two instructions already known to exist).
   Take displacements from capstone operands, never from a byte search.
4. A rel32 caller scan over a 55%-decrypted `.text` is ALWAYS a floor. "Exactly one caller" is never
   a count.
5. A `set()` collapses -0.0 and 0.0.
6. A verdict line can lie — two S138/S139 probes printed verdicts contradicted by their own samples.
7. Do not cross a function boundary with an inference (this caused a retraction in S139).
8. `.rdata` class literals are UHT PREFIX-STRIPPED — bytes say `LokiHeroCharacter`, not
   `ALokiHeroCharacter`. Searching the prefixed form gives a false ABSENT.
9. Never read a mutable global out of a MERGED image's `.data` without saying so.
10. `tools/strxref/vtables.py`'s cached index is built on `merged2` (different image, different
    ImageBase). `.rdata` vtable STARTS are safe; **re-read every CODE grade from merged13.**

## Scope — do not overstate

This is NOT a bot. `ServerSetHeroClass` (`0x556DE43 -> 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 -> 0xF7EB60`) are stripped folds. The GAS fix that closed the input wall is a CDO poke —
process-wide, not undone, a diagnosis not a shipping fix. Nothing this session changes that.

---

# ★★★★★ ADDENDUM (session lead, added mid-flight) — READ `scratchpad/s140/LEAD-FINDINGS.md`

While the lanes ran, the session lead worked the same image in parallel. **LF-13 appears to overturn
the session's central premise.** Summary:

- `ULokiCMC` overrides vtable disp **`0xA50`** with `0x0530ABF0`, whose entire non-tail body is
  `cmp byte [rcx+0x16c8],0 / je / mov byte [rcx+0x16c8],0` then `jmp 0x35d6790`. It **clears
  `CMC+0x16C8` unconditionally**, `rcx = this`. `.rdata` stored-pointer occurrences: **1** (not folded).
- Engine `PerformMovement` **calls disp `0xA50` at `0x035EB569`**, dispatching through the Loki
  vtable (`mov rax,[rbx]`, `rbx = this`). [I, strong] it is `OnMovementUpdated(float, const FVector&
  OldLocation, const FVector& OldVelocity)` — arg shape matches, and both vectors are captured
  upstream at `0x035EA0FD` / `0x035EA113`.
- [M] that call is reachable **only AFTER** the `StartNewPhysics` call returns, is **not** in `R`,
  and is **not** reachable from any of the three bail blocks.

⇒ **`CMC+0x16C8 == 0` is the expected reading both when the physics step never runs AND when it runs
and completes.** The field is a transient in-progress flag, not a sticky latch, and S139's
*"StartNewPhysics has never run on either component"* must be retracted to **UNINTERPRETABLE**.

## Instruction to LANES still running (especially L6)

**Do NOT simply adopt this.** Your independent derivation is worth more than agreement. State
explicitly whether you **AGREE**, **DISAGREE**, or **FOUND IT INDEPENDENTLY**, and on what bytes.
If you can refute any step — the vtable read, the `rcx == this` claim, the reachability, or the
identification of disp `0xA50` — that is the most valuable thing you can return.

## Instruction to the SYNTHESIS agent

Adjudicate LF-13 yourself from the bytes before adopting it. If it stands, it is the headline and
section 5 ("what this means for the contradiction") must say the contradiction **DISSOLVES at the
instrument**, name everything that has to be re-graded, and reframe the open question as
**"why does a correct `Acceleration` produce no `Velocity`"** — which points at `CalcVelocity` /
`PhysFalling` (`0x055B89F0`, disp `0x830`), not at `PerformMovement`'s prologue gates.

Other session-lead results in `LEAD-FINDINGS.md` that the write-up should absorb:
LF-1/LF-2 (no backward bail anywhere; the call is not in a loop), LF-3/LF-4 (all six exits read, five
distinct predicates, `HasValidData` fully transcribed), LF-5 (vtable, 6/6 controls),
**LF-9 (exactly ONE gate between the Acceleration write and `PerformMovement`, measured passing on
the provably same object)**, **LF-11 (hop 5 has ZERO sound exits — and S139's two flagged branches
both jump to `0x055B85B4`, 13 bytes BEFORE the Super call, so they skip a LOOP, not the Super; that
was the S139 handoff's #1 ranked next move and it is refuted)**, and LF-8 (the full 7-hop chain).
